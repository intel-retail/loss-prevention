import sys
import urllib.request
from pathlib import Path

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "efficientnet-b0"
MODELS_BASE_PATH = sys.argv[2] if len(sys.argv) > 2 else "models"
BASE_URL = "https://raw.githubusercontent.com/dlstreamer/pipeline-zoo-models/refs/heads/main/storage/efficientnet-b0_INT8/FP16-INT8/"

BASE_DIR = Path(MODELS_BASE_PATH) / "object_classification" / MODEL_NAME
FP16_DIR = BASE_DIR / "FP16"
INT8_DIR = BASE_DIR / "INT8"

for dir_path in [BASE_DIR, FP16_DIR, INT8_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

def download_file(url, dest_path):
    """Download file if it doesn't exist"""
    if dest_path.exists():
        print(f"[INFO] {dest_path.name} already exists. Skipping.")
        return True
    try:
        print(f"[INFO] Downloading {dest_path.name}...")
        urllib.request.urlretrieve(url, dest_path)
        print(f"[SUCCESS] Downloaded {dest_path.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download {dest_path.name}: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 effnetb0_download.py <model_name> <models_path>")
        sys.exit(1)
    
    print(f"Starting {MODEL_NAME} download...")
    
    # Model files to download
    files = [
        (f"{MODEL_NAME}.xml", FP16_DIR),
        (f"{MODEL_NAME}.bin", FP16_DIR),
        (f"{MODEL_NAME}.xml", INT8_DIR),
        (f"{MODEL_NAME}.bin", INT8_DIR)
    ]
    
    # Extra files
    extra_files = [
        (f"{MODEL_NAME}.txt", "https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/tags/v2025.2.0/samples/labels/imagenet_2012.txt", BASE_DIR),
        (f"{MODEL_NAME}.json", "https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/tags/v2025.2.0/samples/gstreamer/model_proc/public/preproc-aspect-ratio.json", BASE_DIR)
    ]
    
    success_count = 0
    
    # Download model files
    for filename, target_dir in files:
        url = BASE_URL + filename
        if download_file(url, target_dir / filename):
            success_count += 1
    
    # Download extra files
    for filename, url, target_dir in extra_files:
        if download_file(url, target_dir / filename):
            success_count += 1
    
    # Verify downloads
    for precision_dir in [FP16_DIR, INT8_DIR]:
        has_xml = any(f.suffix == ".xml" for f in precision_dir.glob("*"))
        has_bin = any(f.suffix == ".bin" for f in precision_dir.glob("*"))
        status = "SUCCESS" if has_xml and has_bin else "WARNING"
        print(f"[{status}] {precision_dir.name} - XML: {has_xml}, BIN: {has_bin}")
    
    if success_count > 0:
        print(f"[DONE] {MODEL_NAME} download completed! Files saved to: {BASE_DIR}")
    else:
        print(f"[ERROR] Failed to download {MODEL_NAME} model files")
        sys.exit(1)

if __name__ == "__main__":
    main()
