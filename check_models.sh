#!/bin/bash

# Set the models directory
MODELS_DIR="${PWD}/models"

# Function to check if a file exists
check_file() {
    local file_path="$1"
    if [ ! -f "$file_path" ]; then
        echo "Missing: $file_path"
        return 1
    fi
    return 0
}

# Function to check all required model files
check_all_models() {
    local missing_files=0
    
    echo "Checking model files in: $MODELS_DIR"
    
    # Object Classification - EfficientNet-B0
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/efficientnet-b0.json" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/efficientnet-b0.txt" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/FP16/efficientnet-b0.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/FP16/efficientnet-b0.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/INT8/efficientnet-b0.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/efficientnet-b0/INT8/efficientnet-b0.xml" || ((missing_files++))
    
    # Object Classification - Face Re-identification
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP16/face-reidentification-retail-0095.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP16/face-reidentification-retail-0095.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP16-INT8/face-reidentification-retail-0095.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP16-INT8/face-reidentification-retail-0095.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP32/face-reidentification-retail-0095.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_classification/face-reidentification-retail-0095/FP32/face-reidentification-retail-0095.xml" || ((missing_files++))
    
    # Object Detection - Face Detection
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP16/face-detection-retail-0004.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP16/face-detection-retail-0004.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP16-INT8/face-detection-retail-0004.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP16-INT8/face-detection-retail-0004.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP32/face-detection-retail-0004.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/face-detection-retail-0004/FP32/face-detection-retail-0004.xml" || ((missing_files++))
    
    # Object Detection - YOLO11n
    check_file "$MODELS_DIR/object_detection/yolo11n/FP16/yolo11n.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/yolo11n/FP16/yolo11n.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/yolo11n/FP32/yolo11n.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/yolo11n/FP32/yolo11n.xml" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/yolo11n/INT8/yolo11n.bin" || ((missing_files++))
    check_file "$MODELS_DIR/object_detection/yolo11n/INT8/yolo11n.xml" || ((missing_files++))
    
    return $missing_files
}

# Main execution
echo "=== Checking if all required models are present ==="

if check_all_models; then
    echo "All model files are present!"
    echo "Skipping model download."
    exit 0
else
    echo "Some model files are missing."
    echo "Models need to be downloaded."
    exit 1
fi