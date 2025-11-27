#!/bin/bash
set -x  # Enable debug mode
VLM_MODEL_NAME=$1
VLM_COMPRESSION_WEIGHT_FORMAT=$2
HUGGINGFACE_TOKEN=$3

echo "FULL SCRIPT ARGUMENTS:"
echo "VLM_MODEL_NAME: $VLM_MODEL_NAME"
echo "VLM_COMPRESSION_WEIGHT_FORMAT: $VLM_COMPRESSION_WEIGHT_FORMAT"
echo "HUGGINGFACE_TOKEN: $HUGGINGFACE_TOKEN"

# Ensure directory exists and is writable
mkdir -p ov-model
chmod 777 ov-model

source $(poetry env info --path)/bin/activate

MODEL_DIR=$(echo $VLM_MODEL_NAME | awk -F/ '{print $NF}')
MODEL_DIR="ov-model/$MODEL_DIR/$VLM_COMPRESSION_WEIGHT_FORMAT"




# More verbose login
if [ -n "$HUGGINGFACE_TOKEN" ] && [ "$HUGGINGFACE_TOKEN" != "none" ]; then
    echo "Logging in to Hugging Face to access gated models..."
    huggingface-cli login --token "$HUGGINGFACE_TOKEN" || echo "HF Login FAILED"
fi

# Detailed export logging
if [ ! -d "$MODEL_DIR" ]; then
    echo " Attempting to export model..."
    optimum-cli export openvino \
        --trust-remote-code \
        --model "$VLM_MODEL_NAME" \
        "$MODEL_DIR" \
        --weight-format "$VLM_COMPRESSION_WEIGHT_FORMAT" \
        || echo "MODEL EXPORT FAILED"
    
    # Check export result
    if [ -d "$MODEL_DIR" ]; then
        echo "Model exported successfully to $MODEL_DIR"
        ls -l "$MODEL_DIR"
    else
        echo "MODEL EXPORT DIRECTORY NOT CREATED"
    fi
else
    echo "Model directory already exists. Skipping export."
fi

echo "Model compression script completed."