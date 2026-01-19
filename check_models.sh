#!/bin/bash
# Copyright © 2025 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Script to check if all required models are present

MODELS_DIR="${1:-models}"

# Define required models and their paths
declare -a REQUIRED_MODELS=(
    "object_classification/efficientnet-b0/FP16/efficientnet-b0.bin"
    "object_classification/efficientnet-b0/FP16/efficientnet-b0.xml"
    "object_classification/efficientnet-b0/INT8/efficientnet-b0.bin"
    "object_classification/efficientnet-b0/INT8/efficientnet-b0.xml"
    "object_classification/efficientnet-b0/efficientnet-b0.json"
    "object_classification/efficientnet-b0/efficientnet-b0.txt"
    "object_classification/face-reidentification-retail-0095/FP16/face-reidentification-retail-0095.bin"
    "object_classification/face-reidentification-retail-0095/FP16/face-reidentification-retail-0095.xml"
    "object_classification/age-gender-recognition-retail-0013/FP16/age-gender-recognition-retail-0013.bin"
    "object_classification/age-gender-recognition-retail-0013/FP16/age-gender-recognition-retail-0013.xml"
    "object_detection/face-detection-retail-0004/FP16/face-detection-retail-0004.bin"
    "object_detection/face-detection-retail-0004/FP16/face-detection-retail-0004.xml"
    "object_detection/yolo11n/FP16/yolo11n.bin"
    "object_detection/yolo11n/FP16/yolo11n.xml"
    "object_detection/yolo11n/FP32/yolo11n.bin"
    "object_detection/yolo11n/FP32/yolo11n.xml"
    "object_detection/yolo11n/INT8/yolo11n.bin"
    "object_detection/yolo11n/INT8/yolo11n.xml"
)

# Check if models directory exists
if [ ! -d "$MODELS_DIR" ]; then
    echo "Models directory not found: $MODELS_DIR"
    exit 0
fi

# Check each required model
MISSING_MODELS=0
for model in "${REQUIRED_MODELS[@]}"; do
    if [ ! -f "$MODELS_DIR/$model" ]; then
        echo "Missing model: $model"
        MISSING_MODELS=1
    fi
done

if [ $MISSING_MODELS -eq 0 ]; then
    echo "✓ All required models are present"
    exit 1
else
    echo "✗ Some models are missing"
    exit 0
fi