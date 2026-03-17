import sys
import os
import shutil
import subprocess
import json
import torch
import timm
import openvino
import openvino as ov
import nncf
from rich.progress import track
from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionValidator
from ultralytics.data.converter import coco80_to_coco91_class
from ultralytics.data.utils import check_det_dataset
from ultralytics.utils.metrics import ConfusionMatrix
from openvino import Core, serialize
from pathlib import Path

def get_model_type(model_name, mapping_path=None):  
    if mapping_path is None:
        mapping_path = os.path.join(os.path.dirname(__file__), "../configs/yolo_model_type_mapping.json")
    try:
        with open(mapping_path, "r") as f:
            mapping = json.load(f)
        print(f"[DEBUG] Loaded mapping: {mapping}")
        print(f"[DEBUG] Available keys: {list(mapping.keys())}")
        print(f"[DEBUG] Searching for model_name: '{model_name}'")
    except Exception as e:
        print(f"[ERROR] Could not load mapping file: {e}")
        return None
    # Try exact key
    if model_name in mapping:
        print(f"[DEBUG] Found model type for '{model_name}': {mapping[model_name]}")
        return mapping[model_name]
    # Try base name without extension
    base_name = os.path.splitext(model_name)[0]
    if base_name in mapping:
        print(f"[WARN] Model type for '{model_name}' not found, using base name '{base_name}': {mapping[base_name]}")
        return mapping[base_name]
    print(f"[ERROR] Model type for '{model_name}' not found in mapping.")
    return None

def export_yolo(model_name, output_dir):
    model_type = get_model_type(model_name)
    print(f"############ Exporting model_name == {model_name} of type model_type == {model_type} to {output_dir} ############")
    model_dir = os.path.join(output_dir, "object_detection", model_name)
    os.makedirs(model_dir, exist_ok=True)
    weights = model_name + ".pt"
    model = YOLO(weights)
    model.info()
    converted_path = model.export(format='openvino')
    converted_model = os.path.join(converted_path, model_name + '.xml')
    core = openvino.Core()
    ov_model = core.read_model(model=converted_model)
    if model_type in ["YOLOv8-SEG", "yolo_v11_seg"]:
        ov_model.output(0).set_names({"boxes"})
        ov_model.output(1).set_names({"masks"})
    ov_model.set_rt_info(model_type, ['model_info', 'model_type'])
    os.makedirs(os.path.join(model_dir, "FP32"), exist_ok=True)
    os.makedirs(os.path.join(model_dir, "FP16"), exist_ok=True)
    openvino.save_model(ov_model, os.path.join(model_dir, "FP32", model_name + ".xml"), compress_to_fp16=False)
    openvino.save_model(ov_model, os.path.join(model_dir, "FP16", model_name + ".xml"), compress_to_fp16=True)
    shutil.rmtree(converted_path)
    if os.path.exists(weights):
        os.remove(weights)

def quantize_age_gender_face_detection(model_name,output_dir):
    """Convert FP16 model to INT8"""
    print(f"Converting {model_name} to INT8...")
    fp16_xml = Path(f"{output_dir}/{model_name}/FP16/{model_name}.xml")
    int8_dir = Path(f"{output_dir}/{model_name}/INT8")
    int8_dir.mkdir(parents=True, exist_ok=True)
    int8_xml = int8_dir / f"{model_name}.xml"
    if int8_xml.exists():
        print(f"[INFO] INT8 model already exists: {int8_xml}")
        return
    if not fp16_xml.exists():
        print(f"[ERROR] FP16 model not found: {fp16_xml}")
        return
    try:
        core = Core()
        model = core.read_model(str(fp16_xml))
        try:
            compressed_model = ov.compress_model(model)
            serialize(compressed_model, str(int8_xml))
        except AttributeError:
            print(f"Using basic model copy (compression not available)")
            serialize(model, str(int8_xml))
        print(f"INT8 model saved: {int8_xml}")
    except Exception as e:
        print(f"Error converting {model_name} to INT8: {e}")

def quantize_yolo(model_name, dataset_manifest, output_dir):
    model_dir = os.path.join(output_dir, "object_detection", model_name)
    fp16_xml = os.path.join(model_dir, "FP16", model_name + ".xml")
    int8_dir = os.path.join(model_dir, "INT8")
    os.makedirs(int8_dir, exist_ok=True)
    validator = DetectionValidator()
    validator.data = check_det_dataset(dataset_manifest)
    validator.stride = 32
    validator.is_coco = True
    validator.class_map = coco80_to_coco91_class
    data_loader = validator.get_dataloader(validator.data["path"], 1)
    def transform_fn(data_item: dict):
        input_tensor = validator.preprocess(data_item)["img"].numpy()
        return input_tensor
    calibration_dataset = nncf.Dataset(data_loader, transform_fn)
    model = ov.Core().read_model(fp16_xml)
    quantized_model = nncf.quantize(model, calibration_dataset, subset_size=len(data_loader))
    def validate(model, data_loader, validator, num_samples=None):
        validator.seen = 0
        validator.jdict = []
        validator.stats = dict(tp=[], conf=[], pred_cls=[], target_cls=[], target_img=[])
        validator.end2end = False
        validator.confusion_matrix = ConfusionMatrix(validator.data["names"])
        compiled_model = ov.compile_model(model, device_name="CPU")
        output_layer = compiled_model.output(0)
        for batch_i, batch in enumerate(track(data_loader, description="Validating")):
            if num_samples is not None and batch_i == num_samples:
                break
            batch = validator.preprocess(batch)
            preds = torch.from_numpy(compiled_model(batch["img"])[output_layer])
            preds = validator.postprocess(preds)
            validator.update_metrics(preds, batch)
        stats = validator.get_stats()
        return stats, validator.seen
    def print_statistics(stats: dict, total_images: int):
        mp, mr, map50, mean_ap = (
            stats["metrics/precision(B)"],
            stats["metrics/recall(B)"],
            stats["metrics/mAP50(B)"],
            stats["metrics/mAP50-95(B)"],
        )
        s = ("%20s" + "%12s" * 5) % ("Class", "Images", "Precision", "Recall", "mAP@.5", "mAP@.5:.95")
        print(s)
        pf = "%20s" + "%12i" + "%12.3g" * 4
        print(pf % ("all", total_images, mp, mr, map50, mean_ap))
    fp_stats, total_images = validate(model, data_loader, validator)
    print("Floating-point model validation results:")
    print_statistics(fp_stats, total_images)
    q_stats, total_images = validate(quantized_model, data_loader, validator)
    print("Quantized model validation results:")
    print_statistics(q_stats, total_images)
    try:
        map50_drop = (fp_stats["metrics/mAP50(B)"] - q_stats["metrics/mAP50(B)"]) / fp_stats["metrics/mAP50(B)"] * 100
        map95_drop = (fp_stats["metrics/mAP50-95(B)"] - q_stats["metrics/mAP50-95(B)"]) / fp_stats["metrics/mAP50-95(B)"] * 100
        print(f"mAP@.5 accuracy drop: {map50_drop:.2f}%")
        print(f"mAP@.5:.95 accuracy drop: {map95_drop:.2f}%")
    except Exception as e:
        print(f"[WARN] Could not compute accuracy drop: {e}")
    quantized_model.set_rt_info(ov.get_version(), "Runtime_version")
    xml_path = os.path.join(int8_dir, model_name + ".xml")
    bin_path = os.path.join(int8_dir, model_name + ".bin")
    ov.save_model(quantized_model, xml_path, compress_to_fp16=False)
    fp16_bin = os.path.join(model_dir, "FP16", model_name + ".bin")
    if os.path.exists(fp16_bin) and not os.path.exists(bin_path):
        shutil.copy(fp16_bin, bin_path)
    for d in ["datasets", "runs"]:
        p = os.path.join(output_dir, d)
        if os.path.exists(p):
            shutil.rmtree(p)
        p2 = os.path.join(model_dir, d)
        if os.path.exists(p2):
            shutil.rmtree(p2)



def main():
    if len(sys.argv) < 2:
        print("Usage: model_convert.py <command> ...")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "export_yolo":
        if len(sys.argv) < 4:
            print("Usage: model_convert.py export_yolo <model_name> <output_dir>")
            sys.exit(1)
        export_yolo(sys.argv[2], sys.argv[3])
    elif cmd == "quantize_yolo":
        if len(sys.argv) < 5:
            print("Usage: model_convert.py quantize_yolo <model_name> <dataset_manifest> <output_dir>")
            sys.exit(1)
        quantize_yolo(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "quantize_age_gender_face_detection":
        if len(sys.argv) < 4:
            print("Usage: model_convert.py quantize_age_gender_face_detectio <model_name> <output_dir>")
            sys.exit(1)
        quantize_age_gender_face_detection(sys.argv[2], sys.argv[3])
    else:
        print(f"[ERROR] Unsupported command: {cmd}")
        sys.exit(2)

if __name__ == "__main__":
    main()
