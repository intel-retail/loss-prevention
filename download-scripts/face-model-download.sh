#!/bin/bash

set -e

# Usage: face-model-download.sh <model_name> <output_dir>
MODEL_NAME=${1:-"face-detection-retail-0004"}
# Decide subdir based on model type
if [[ "$MODEL_NAME" == *reidentification* ]]; then
    SUBDIR="object_classification"
else
    SUBDIR="object_detection"
fi
MODELS_PATH=${2:-"models/$SUBDIR"}

if [[ -z "$MODEL_NAME" || -z "$MODELS_PATH" ]]; then
    echo "Usage: $0 <model_name> <output_dir>"
    exit 1
fi


echo "Creating a directory for models at $MODELS_PATH..."
mkdir -p "$MODELS_PATH"

MODEL_XML_FP16="$MODELS_PATH/$MODEL_NAME/FP16/$MODEL_NAME.xml"
MODEL_XML_FP32="$MODELS_PATH/$MODEL_NAME/FP32/$MODEL_NAME.xml"
if [ -f "$MODEL_XML_FP16" ] && [ -f "$MODEL_XML_FP32" ]; then
    echo "Model $MODEL_NAME already downloaded at $MODEL_XML_FP16 and $MODEL_XML_FP32 ✓"
else
    echo "Downloading model $MODEL_NAME using Open Model Zoo downloader..."
    omz_downloader --name "$MODEL_NAME" --output_dir "$MODELS_PATH"
    # OMZ puts models in models/intel/<model_name> or models/public/<model_name>, move to $MODELS_PATH/<model_name>
    if [ -d "$MODELS_PATH/intel/$MODEL_NAME" ]; then
        echo "Moving model from $MODELS_PATH/intel/$MODEL_NAME to $MODELS_PATH/$MODEL_NAME ..."
        mv "$MODELS_PATH/intel/$MODEL_NAME" "$MODELS_PATH/" || true
        rmdir --ignore-fail-on-non-empty "$MODELS_PATH/intel" 2>/dev/null || true
    elif [ -d "$MODELS_PATH/public/$MODEL_NAME" ]; then
        echo "Moving model from $MODELS_PATH/public/$MODEL_NAME to $MODELS_PATH/$MODEL_NAME ..."
        mv "$MODELS_PATH/public/$MODEL_NAME" "$MODELS_PATH/" || true
        rmdir --ignore-fail-on-non-empty "$MODELS_PATH/public" 2>/dev/null || true
    fi
    echo "Listing downloaded model(s)..."
    find "$MODELS_PATH" -name "*.xml" -o -name "*.bin" | sort
    echo "Model download completed successfully! ✓"
fi