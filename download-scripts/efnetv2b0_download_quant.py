import os
import subprocess
import sys
from pathlib import Path
import urllib.request
import numpy as np
from openvino.runtime import Core, serialize
from nncf import Dataset, quantize
import shutil
import tensorflow_datasets as tfds
import tensorflow as tf

try:
    from nncf.quantization.advanced_parameters import AdvancedQuantizationParameters
except ImportError:
    try:
        from nncf.parameters import QuantizationParameters
        AdvancedQuantizationParameters = QuantizationParameters
    except ImportError:
        AdvancedQuantizationParameters = None

# === Update for EfficientNetV2-B0 ===
# Accept model name and models path from command line arguments
MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "efficientnet-v2-b0"
MODELS_BASE_PATH = sys.argv[2] if len(sys.argv) > 2 else "models"
INPUT_SIZE = 224
PRECISIONS = ["FP32", "FP16"]

MOUNTED_MODELS_DIR = Path(MODELS_BASE_PATH)
BASE_DIR = MOUNTED_MODELS_DIR / "object_classification" / MODEL_NAME
DOWNLOAD_DIR = BASE_DIR / "omz_download"
CACHE_DIR = BASE_DIR / "omz_cache"
OUTPUT_DIR = BASE_DIR
INT8_DIR = BASE_DIR / "INT8"

# Create necessary subdirectories (but not the main models dir)
BASE_DIR.mkdir(parents=True, exist_ok=True)
INT8_DIR.mkdir(parents=True, exist_ok=True)

EXTRA_FILES = {
    #f"{MODEL_NAME}.txt": "https://raw.githubusercontent.com/open-edge-platform/edge-ai-libraries/main/libraries/dl-streamer/samples/labels/imagenet_2012.txt",
    #f"{MODEL_NAME}.json": "https://raw.githubusercontent.com/open-edge-platform/edge-ai-libraries/main/libraries/dl-streamer/samples/gstreamer/model_proc/public/preproc-aspect-ratio.json"

    f"{MODEL_NAME}.txt": "https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/tags/v2025.2.0/samples/labels/imagenet_2012.txt",
    f"{MODEL_NAME}.json": "https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/tags/v2025.2.0/samples/gstreamer/model_proc/public/preproc-aspect-ratio.json"
}

def run_downloader():
    model_dir = DOWNLOAD_DIR / "public" / MODEL_NAME
    if model_dir.exists() and any(model_dir.rglob("*")):
        print("[INFO] Model already downloaded. Skipping.")
        return
    elif any(CACHE_DIR.glob(f"{MODEL_NAME}*")):
        print("[INFO] Model already cached. Skipping.")
        return
    print("[INFO] Downloading model...")
    subprocess.run([
        "omz_downloader",
        "--name", MODEL_NAME,
        "--output_dir", str(DOWNLOAD_DIR),
        "--cache_dir", str(CACHE_DIR)
    ], check=True)

def run_converter(precision):
    source_dir = OUTPUT_DIR / "public" / MODEL_NAME / precision
    target_dir = OUTPUT_DIR / precision
    ir_xml = target_dir / f"{MODEL_NAME}.xml"
    ir_bin = target_dir / f"{MODEL_NAME}.bin"

    if ir_xml.exists() and ir_bin.exists():
        print(f"[INFO] IR already in {precision}. Skipping.")
        return

    print(f"[INFO] Converting to IR ({precision})...")
    subprocess.run([
        "omz_converter",
        "--name", MODEL_NAME,
        "--precision", precision,
        "--download_dir", str(DOWNLOAD_DIR),
        "--output_dir", str(OUTPUT_DIR)
    ], check=True)

    target_dir.mkdir(parents=True, exist_ok=True)
    for file in source_dir.glob("*"):
        file.rename(target_dir / file.name)

    print(f"[DONE] Moved {precision} IR to: {target_dir.resolve()}")

def preprocess_image(image):
    image = tf.image.resize(image, [INPUT_SIZE, INPUT_SIZE], method='bilinear')
    image = tf.cast(image, tf.float32) / 255.0
    mean = tf.constant([0.485, 0.456, 0.406])
    std = tf.constant([0.229, 0.224, 0.225])
    image = (image - mean) / std
    return image

def load_imagenet_validation_images(input_key, limit=600):
    dataset_names = ['imagenet2012', 'imagenet_v2', 'imagenet_resized/32x32']
    dataset = None
    for name in dataset_names:
        try:
            if name == 'imagenet2012':
                dataset = tfds.load(name, split='validation', shuffle_files=True, download=True)
            else:
                dataset = tfds.load(name, split='test', shuffle_files=True, download=True)
            break
        except:
            continue
    if dataset is None:
        return load_cifar100_images(input_key, limit)
    count = 0
    for example in tfds.as_numpy(dataset):
        if count >= limit:
            break
        img = example['image']
        if len(img.shape) != 3 or img.shape[2] != 3:
            continue
        img_tensor = tf.constant(img)
        img_processed = preprocess_image(img_tensor)
        img_array = img_processed.numpy().transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)
        yield {input_key: img_array}
        count += 1

def load_cifar100_images(input_key, limit=600):
    train_ds = tfds.load('cifar100', split='train', shuffle_files=True)
    test_ds = tfds.load('cifar100', split='test', shuffle_files=True)
    combined_ds = train_ds.concatenate(test_ds)
    count = 0
    for example in tfds.as_numpy(combined_ds):
        if count >= limit:
            break
        img = example['image']
        img_tensor = tf.constant(img, dtype=tf.uint8)
        img_processed = preprocess_image(img_tensor)
        img_array = img_processed.numpy().transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)
        yield {input_key: img_array}
        count += 1

def quantize_model():
    fp32_path = OUTPUT_DIR / "FP32" / f"{MODEL_NAME}.xml"
    int8_xml = INT8_DIR / f"{MODEL_NAME}.xml"
    int8_bin = INT8_DIR / f"{MODEL_NAME}.bin"
    if int8_xml.exists() and int8_bin.exists():
        print("[INFO] INT8 model already exists. Skipping quantization.")
        return fp32_path, OUTPUT_DIR / "FP16" / f"{MODEL_NAME}.xml", int8_xml

    core = Core()
    model = core.read_model(fp32_path)
    input_key = model.inputs[0].get_any_name()
    dataset = Dataset(load_imagenet_validation_images(input_key, limit=600))

    try:
        quantized_model = quantize(
            model=model,
            calibration_dataset=dataset,
            subset_size=600,
            model_type="transformer",
            fast_bias_correction=True
        )
    except:
        quantized_model = quantize(model=model, calibration_dataset=dataset, subset_size=600)

    serialize(model=quantized_model, xml_path=str(int8_xml), bin_path=str(int8_bin))
    return fp32_path, OUTPUT_DIR / "FP16" / f"{MODEL_NAME}.xml", int8_xml

def download_extra_files():
    downloaded_paths = {}
    for filename, url in EXTRA_FILES.items():
        print(f"[INFO] Downloading extra file:================================= {filename}...")
        dest_path = BASE_DIR / filename
        if not dest_path.exists():
            urllib.request.urlretrieve(url, dest_path)
        downloaded_paths[filename] = dest_path.resolve()
    return downloaded_paths

def clean_temp_dirs():
    for folder in [DOWNLOAD_DIR, CACHE_DIR, OUTPUT_DIR / "public"]:
        if folder.exists() and folder.is_dir():
            shutil.rmtree(folder)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 efnetv2b0_download_quant.py <model_name> <models_path>")
        print("Example: python3 efnetv2b0_download_quant.py efficientnet-v2-b0 /workspace/models")
        sys.exit(1)
    
    print(f"Starting {MODEL_NAME} quantization pipeline...")
    print(f"Using models path: {MODELS_BASE_PATH}")
    run_downloader()
    for p in PRECISIONS:
        run_converter(p)
    fp32_xml, fp16_xml, int8_xml = quantize_model()
    extra_paths = download_extra_files()
    clean_temp_dirs()
    print("Done.")