#!/bin/bash
set -e

echo "================ Face Model Download Script "$PRECISION

MODEL_NAME=${1:-"face-detection-retail-0004"}
PRECISION=${3}

echo "================ Face Model Download Script ================"$PRECISION
# ==============================
# 1️⃣ Proxy Setup
# ==============================
if [[ -n "$http_proxy" || -n "$https_proxy" ]]; then
    echo "=== Proxy detected: $http_proxy"
    cat <<EOF > /etc/wgetrc
use_proxy = on
http_proxy = $http_proxy
https_proxy = $https_proxy
no_proxy = $no_proxy
EOF
    git config --global http.proxy "$http_proxy"
    git config --global https.proxy "$https_proxy"
else
    echo "=== No proxy configured."
fi

# ==============================
# 2️⃣ Model directory setup
# ==============================
if [[ "$MODEL_NAME" == *reidentification* ]]; then
    SUBDIR="object_classification"
else
    SUBDIR="object_detection"
fi

MODELS_PATH=${2:-"/workspace/models/$SUBDIR"}
OMZ_DIR="/tmp/open_model_zoo"

echo "=== Preparing directories ..."
mkdir -p "$MODELS_PATH"

MODEL_XML_FP16="$MODELS_PATH/$MODEL_NAME/FP16/$MODEL_NAME.xml"

if [ -f "$MODEL_XML_FP16" ] ; then
    echo "✓ Model $MODEL_NAME already exists in $MODELS_PATH"
    exit 0
fi

# ==============================
# 3️⃣ Clone full OMZ repo
# ==============================
echo "=== Cloning Open Model Zoo repository ..."
rm -rf "$OMZ_DIR"
git clone --depth 1 https://github.com/openvinotoolkit/open_model_zoo.git "$OMZ_DIR"

TOOLS_DIR="$OMZ_DIR/tools/model_tools"

# ==============================
# 4️⃣ Run downloader and converter
# ==============================
echo "=== Downloading and converting model: $MODEL_NAME ..."

python3 "$TOOLS_DIR/downloader.py" \
    --name "$MODEL_NAME" \
    --output_dir "$MODELS_PATH" \
    --cache_dir /tmp/omz_cache \
    --precisions "$PRECISION"


# ==============================
# 5️⃣ Move model and cleanup
# ==============================
if [ -d "$MODELS_PATH/intel/$MODEL_NAME" ]; then
    mv "$MODELS_PATH/intel/$MODEL_NAME" "$MODELS_PATH/" || true
    rmdir --ignore-fail-on-non-empty "$MODELS_PATH/intel" 2>/dev/null || true
fi

echo "=== Cleaning up Open Model Zoo repo ..."
rm -rf "$OMZ_DIR"

# ==============================
# 6️⃣ Verify download
# ==============================
echo "=== Listing downloaded model files ..."
find "$MODELS_PATH/$MODEL_NAME" -type f \( -name "*.xml" -o -name "*.bin" \) | sort

echo "✅ Model $MODEL_NAME downloaded successfully into $MODELS_PATH"
