#!/usr/bin/env python3
"""
Configuration validation script for loss-prevention pipeline.
Validates workload_to_pipeline.json and camera_to_workload.json files.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional


class ConfigValidator:
    """Validates configuration files for the loss-prevention pipeline."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(f"ERROR: {message}")
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(f"WARNING: {message}")
    
    def validate_pipeline_config(self, config_path: str) -> bool:
        """Validate workload_to_pipeline.json configuration."""
        print(f"Validating pipeline configuration: {config_path}")
        
        if not Path(config_path).exists():
            self.add_error(f"Configuration file not found: {config_path}")
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.add_error(f"Invalid JSON in {config_path}: {e}")
            return False
        except Exception as e:
            self.add_error(f"Failed to read {config_path}: {e}")
            return False
        
        valid_count = 0
        required_fields = ['type', 'model', 'device', 'precision']
        
        for workload_name, workload_config in config.items():
            if isinstance(workload_config, list):
                # Direct array of model configs
                for i, model_config in enumerate(workload_config):
                    valid_count += self._validate_model_config(
                        model_config, f"{workload_name}[{i}]", required_fields
                    )
            elif isinstance(workload_config, dict):
                # Nested structure - check for arrays within the object
                for sub_key, sub_config in workload_config.items():
                    if isinstance(sub_config, list):
                        for i, model_config in enumerate(sub_config):
                            valid_count += self._validate_model_config(
                                model_config, f"{workload_name}.{sub_key}[{i}]", required_fields
                            )
            else:
                self.add_error(f"Invalid workload configuration type for '{workload_name}': expected array or object")
        
        if valid_count == 0:
            self.add_error("No valid model configurations found")
            return False
        
        print(f"SUCCESS: Found {valid_count} valid model configurations")
        return True
    
    def _validate_model_config(self, model_config: Dict[str, Any], context: str, required_fields: List[str]) -> int:
        """Validate a single model configuration object."""
        if not isinstance(model_config, dict):
            self.add_error(f"Invalid model configuration in {context}: expected object, got {type(model_config).__name__}")
            return 0
        
        for field in required_fields:
            if field not in model_config:
                self.add_error(f"Missing required field '{field}' in {context}")
                return 0
            
            value = model_config[field]
            if not isinstance(value, str) or not value.strip():
                # Provide specific error messages for device and precision fields
                if field == 'device':
                    self.add_error(f"Field 'device' must be a non-empty string in {context}. Supported values: CPU, GPU, NPU")
                elif field == 'precision':
                    self.add_error(f"Field 'precision' must be a non-empty string in {context}. Supported values: INT8, FP16, FP32")
                else:
                    self.add_error(f"Field '{field}' must be a non-empty string in {context}")
                return 0
        
        # Additional validation for device field - must be CPU, GPU, or NPU
        if 'device' in model_config:
            device_value = model_config['device'].strip().upper()
            valid_devices = ['CPU', 'GPU', 'NPU']
            if device_value not in valid_devices:
                self.add_error(f"Invalid device value '{model_config['device']}' in {context}. Supported values: {', '.join(valid_devices)}")
                return 0
        
        # Additional validation for precision field - must be INT8, FP16, or FP32
        if 'precision' in model_config:
            precision_value = model_config['precision'].strip().upper()
            valid_precisions = ['INT8', 'FP16', 'FP32']
            if precision_value not in valid_precisions:
                self.add_error(f"Invalid precision value '{model_config['precision']}' in {context}. Supported values: {', '.join(valid_precisions)}")
                return 0
        
        return 1
    
    def validate_camera_config(self, config_path: str) -> bool:
        """Validate camera_to_workload.json configuration."""
        print(f"Validating camera configuration: {config_path}")
        
        if not Path(config_path).exists():
            self.add_error(f"Configuration file not found: {config_path}")
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            self.add_error(f"Invalid JSON in {config_path}: {e}")
            return False
        except Exception as e:
            self.add_error(f"Failed to read {config_path}: {e}")
            return False
        
        # Check for lane_config structure
        if 'lane_config' not in config:
            self.add_error("Missing 'lane_config' section in camera configuration")
            return False
        
        lane_config = config['lane_config']
        if not isinstance(lane_config, dict):
            self.add_error("'lane_config' must be an object")
            return False
        
        if 'cameras' not in lane_config:
            self.add_error("Missing 'cameras' array in lane_config")
            return False
        
        cameras = lane_config['cameras']
        if not isinstance(cameras, list):
            self.add_error("'cameras' must be an array")
            return False
        
        if len(cameras) == 0:
            self.add_error("'cameras' array cannot be empty")
            return False
        
        valid_count = 0
        for i, camera in enumerate(cameras):
            if self._validate_camera_config(camera, f"camera[{i}]"):
                valid_count += 1
        
        if valid_count == 0:
            self.add_error("No valid camera configurations found")
            return False
        
        print(f"SUCCESS: Found {valid_count} valid camera configurations")
        return True
    
    def _validate_camera_config(self, camera: Dict[str, Any], context: str) -> bool:
        """Validate a single camera configuration."""
        if not isinstance(camera, dict):
            self.add_error(f"Invalid camera configuration in {context}: expected object")
            return False

        # Validate fileSrc
        if 'fileSrc' not in camera:
            self.add_error(f"Missing 'fileSrc' field in {context}")
            return False

        file_src = camera['fileSrc']
        if not isinstance(file_src, str) or not file_src.strip():
            self.add_error(f"'fileSrc' must be a non-empty string in {context}")
            return False

        # Check fileSrc format: filename|url
        if '|' not in file_src:
            self.add_error(f"Invalid 'fileSrc' format in {context}: must be 'filename|url', got '{file_src}'")
            return False

        parts = file_src.split('|', 1)  # Split into exactly 2 parts
        filename, url = parts[0].strip(), parts[1].strip()

        if not filename:
            self.add_error(f"Invalid 'fileSrc' format in {context}: filename part is empty in '{file_src}'")
            return False

        if not url:
            self.add_error(f"Invalid 'fileSrc' format in {context}: URL part is empty in '{file_src}'")
            return False

        # Validate region_of_interest if present
        if 'region_of_interest' in camera:
            roi = camera['region_of_interest']
            if not isinstance(roi, dict):
                self.add_error(f"'region_of_interest' must be an object in {context}")
                return False
            for field in ['x', 'y', 'x2', 'y2']:
                if field not in roi:
                    self.add_error(f"Missing '{field}' in region_of_interest in {context}")
                    return False
                value = roi[field]
                if value in [None, '', 0]:
                    self.add_error(f"Field '{field}' in region_of_interest must not be empty or 0 in {context}")
                    return False

        # Validate workloads
        if 'workloads' not in camera:
            self.add_error(f"Missing 'workloads' field in {context}")
            return False

        workloads = camera['workloads']
        if not isinstance(workloads, list):
            self.add_error(f"'workloads' must be an array in {context}")
            return False

        if len(workloads) == 0:
            self.add_error(f"'workloads' array cannot be empty in {context}")
            return False

        # Validate each workload is a non-empty string
        for j, workload in enumerate(workloads):
            if not isinstance(workload, str) or not workload.strip():
                self.add_error(f"workloads[{j}] must be a non-empty string in {context}")
                return False

        return True
    
    def print_results(self) -> bool:
        """Print validation results and return success status."""
        if self.warnings:
            for warning in self.warnings:
                print(warning)
        
        if self.errors:
            print("\nValidation failed with the following errors:")
            for error in self.errors:
                print(error)
            return False
        
        print("All validations passed successfully!")
        return True


def main():
    """Main function to run configuration validation."""
    parser = argparse.ArgumentParser(description='Validate loss-prevention configuration files')
    parser.add_argument('--pipeline-config', 
                       default='configs/workload_to_pipeline.json',
                       help='Path to workload_to_pipeline.json (default: configs/workload_to_pipeline.json)')
    parser.add_argument('--camera-config', 
                       default='configs/camera_to_workload.json',
                       help='Path to camera_to_workload.json (default: configs/camera_to_workload.json)')
    parser.add_argument('--validate-pipeline', action='store_true',
                       help='Validate only pipeline configuration')
    parser.add_argument('--validate-camera', action='store_true',
                       help='Validate only camera configuration')
    parser.add_argument('--validate-all', action='store_true',
                       help='Validate all configurations (default if no specific validation is requested)')
    
    args = parser.parse_args()
    
    # Default to validating all if no specific validation is requested
    if not any([args.validate_pipeline, args.validate_camera, args.validate_all]):
        args.validate_all = True
    
    validator = ConfigValidator()
    success = True
    
    if args.validate_pipeline or args.validate_all:
        success &= validator.validate_pipeline_config(args.pipeline_config)
    
    if args.validate_camera or args.validate_all:
        success &= validator.validate_camera_config(args.camera_config)
    
    success &= validator.print_results()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
