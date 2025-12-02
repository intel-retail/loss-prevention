"""
Publisher module for processing video frames and publishing metadata to RabbitMQ.
Handles frame processing, metadata storage, and MinIO object storage integration.
"""

import sys
import json
import os
import shutil
import time
import random
import logging
import atexit
import traceback
from datetime import datetime
from io import BytesIO
from collections import defaultdict

import numpy as np
import pika
from PIL import Image
from .rabbitmq_client import get_rabbitmq_connection
from config.config import METADATA_DIR_FULL_PATH, FRAMES_DIR_FULL_PATH, BUCKET_NAME, MINIO_HOST,FRAME_DIR_VOL_BASE, RESULTS_DIR

# ============================================================================
# CONSTANTS
# ============================================================================

threshold_value = os.environ.get("DETECTION_THRESHOLD")
THRESHOLD = int(threshold_value) if threshold_value else 16  # Number of frames an item must appear in before sending notification

# ============================================================================
# LOGGER SETUP
# ============================================================================

def setup_logger():
    """
    Configure and return logger for the publisher module.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()  # Also output to console
            ]
        )
        return logging.getLogger("loss_prevention_gvapython")
    except Exception as e:
        # Fallback to console-only logging if file setup fails
        logger.error(traceback.format_exc())
        sys.exit(1)

logger = setup_logger()

# ============================================================================
# MINIO CLIENT
# ============================================================================

def get_minio_client():
    """
    Initialize and return MinIO client instance.
    
    Returns:
        Minio: Configured MinIO client or None if import fails
    """
    try:
        from minio import Minio
        
        logger.info(f"############ MINIO_HOST =================={MINIO_HOST}")
        
        MINIO_ENDPOINT = MINIO_HOST
        MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER")
        MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD")
        
        _minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )
        return _minio_client
    except ImportError:
        logger.error(
            "MinIO Python SDK is not installed. Please install it with:\n"
            "  pip install minio"
        )
        logger.error(traceback.format_exc())
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error initializing MinIO client: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

# ============================================================================
# PUBLISHER CLASS
# ============================================================================

class Publisher:
    """
    Handles video frame processing, metadata management, and message publishing.
    
    Responsibilities:
    - Process video frames and extract metadata
    - Store images in MinIO object storage
    - Publish detection events to RabbitMQ
    - Manage cleanup on stream end
    """
    
    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    
    def __init__(self, clean_output=True):
        """
        Initialize Publisher with necessary connections and directories.
        
        Args:
            clean_output (bool): Whether to clean output directories on startup
        """
        try:
            # Frame tracking
            self.frame_counter = 0
            self.run_id = f"{int(time.time())}-{random.randint(1000, 9999)}"
            
            # Directory setup
            self.metadata_dir = METADATA_DIR_FULL_PATH
            self.frames_dir = FRAMES_DIR_FULL_PATH
            self.output_dir_frames = "/app/pipeline-server/results/frames"
            
            # Detection tracking
            self.item_frameid_mapper = defaultdict(list)
            self.sent_items = set()
            
            # External connections
            self.minio_client = get_minio_client()
            self.connection = None
            self.channel = None
            self.file_handle = None
            
            # Setup
            self._setup_directories(clean_output)
            self._setup_jsonl_file()
            self._setup_rabbitmq()            
            logger.info(f"GVA Publisher initialized: {self.metadata_dir}")
        except Exception as e:
            logger.error(f"Error initializing Publisher: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _setup_directories(self, clean_output):
        """Clean and create necessary directories."""
        try:
            if clean_output:
                self.clean_output_directory(self.frames_dir)
                self.clean_output_directory(self.metadata_dir)
            
            os.makedirs(self.metadata_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Error setting up directories: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _setup_jsonl_file(self):
        """Initialize JSONL file for metadata storage."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S") + str(int(time.time_ns()))[10:16]
            self.jsonl_file = os.path.join(self.metadata_dir, f"rs-1_{timestamp}.jsonl")
            os.makedirs(os.path.dirname(self.jsonl_file), exist_ok=True)
            self.file_handle = open(self.jsonl_file, 'a')
        except Exception as e:
            logger.error(f"Error setting up JSONL file: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _setup_rabbitmq(self):
        """Establish RabbitMQ connection and channel."""
        try:
            # Use shared client function
            self.connection = get_rabbitmq_connection()
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue="object_detection", durable=True)
        except Exception as e:
            logger.error(f"Error setting up RabbitMQ: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # ------------------------------------------------------------------------
    # FRAME PROCESSING
    # ------------------------------------------------------------------------
    
    def process(self, frame):
        """
        Process GVA VideoFrame and save metadata.
        
        Args:
            frame: GVA VideoFrame object containing image and metadata
            
        Returns:
            bool: False if processing failed, None otherwise
        """
        try:
            with frame.data() as image:
                video_info = frame.video_info()
                logger.info("Frame received for processing**********************************")
                
                frame_id = f"frame__{self.frame_counter:06d}.jpg"
                metadata = {"frame_id": frame_id}
                
                # Extract and update metadata
                messages = frame.messages()
                if isinstance(messages, list) and len(messages) > 0:
                    json_string = messages[0]
                    data = json.loads(json_string)
                    metadata.update(data)
                    
                    self.save_metadata_json(metadata)
                    self.add_video_format_info(video_info, metadata)
                    
                    frame_path = os.path.join(self.run_id, frame_id)
                    self.save_image(image, frame_path, metadata)
                    logger.info(f"Image saved: {metadata}")
                    
                    # Process detected objects
                    self._process_detections(metadata, frame_path)
                    
                    self.frame_counter += 1
            
        except Exception as e:
            logger.error(f"Error processing frame {self.frame_counter}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _process_detections(self, metadata, frame_path):
        """
        Process object detections and send notifications if threshold reached.
        
        Args:
            metadata (dict): Frame metadata containing detected objects
            frame_path (str): Path to saved frame image
        """
        try:
            if not metadata or len(metadata.get("objects", [])) == 0:
                return
            
            for obj in metadata.get("objects", []):
                detection = obj.get("detection", {})
                label = detection.get("label")
                
                if label and label != "person":
                    logger.info(f"Items extracted from label: {self.item_frameid_mapper}")
                    self.item_frameid_mapper[label].append(frame_path)
                    
                    if len(self.item_frameid_mapper[label]) >= THRESHOLD and label not in self.sent_items:
                        logger.info(f"Sending Data: {self.item_frameid_mapper}")
                        self._send_detection_notification(label)
                        self.sent_items.add(label)
        except Exception as e:
            logger.error(f"Error processing detections: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _send_detection_notification(self, label):
        """Send RabbitMQ notification for detected item."""
        try:
            message = {
                "data": {
                    "item_name": label,
                    "frames": self.item_frameid_mapper[label],
                    "bucket": BUCKET_NAME
                },
                "msg_type": "FRAME_DATA",
                "status": "PROCESSING",
                "timestamp": datetime.now().isoformat()
            }
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending detection notification: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # ------------------------------------------------------------------------
    # METADATA MANAGEMENT
    # ------------------------------------------------------------------------
    
    def add_video_format_info(self, video_info, metadata):
        """
        Add video format information to metadata.
        
        Args:
            video_info: GStreamer video info object
            metadata (dict): Metadata dictionary to update
        """
        try:
            image_format = video_info.to_caps().get_structure(0).get_value('format')
            metadata["img_format"] = image_format
        except Exception as e:
            logger.error(f"Error adding video format info for frame {self.frame_counter}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def save_metadata_json(self, metadata):
        """
        Save metadata to JSONL file.
        
        Args:
            metadata (dict): Frame metadata to save
        """
        try:
            json.dump(metadata, self.file_handle)
            self.file_handle.write('\n')
            self.file_handle.flush()
            logger.info(f"Metadata saved to: {self.jsonl_file}")
        except Exception as e:
            logger.error(f"Error saving JSON for frame {self.frame_counter}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def clean_and_ignore_label(self, record):
        """
        Check if record should be ignored based on label.
        
        Args:
            record (dict): Detection record
            
        Returns:
            bool: True if should process, False if should ignore
        """
        try:
            for key, value in record["objects"][0].items():
                if "classification" in key and "label" in value:
                    clean_label = value["label"].split(" ", 1)[1]
                    if clean_label == "envelope":
                        return False
                    return True
            return False
        except Exception as e:
            logger.error(f"Error in clean_and_ignore_label: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # ------------------------------------------------------------------------
    # IMAGE STORAGE
    # ------------------------------------------------------------------------
    
    def save_image(self, image_array, image_filename, metadata):
        """
        Save image to MinIO object storage and local filesystem.
        
        Args:
            image_array (np.ndarray): Image data
            image_filename (str): Filename for MinIO storage
            metadata (dict): Image metadata containing format info
        """
        try:
            # Convert BGR to RGB if needed
            if metadata.get("img_format") in ["BGR", "BGRx", "BGRA"]:
                image_array = image_array[:, :, 2::-1]
            
            # Save to MinIO
            self._save_to_minio(image_array, image_filename)
            
            # Save to local filesystem
            #save_to_local(image_array)
            
        except Exception as e:
            logger.error(f"Error saving image {image_filename}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _save_to_minio(self, image_array, image_filename):
        """Save image to MinIO object storage."""
        try:
            image = Image.fromarray(image_array)
            image_buffer = BytesIO()
            image.save(image_buffer, format="JPEG", quality=85)
            image_buffer.seek(0)
            if self.minio_client is None:
                logger.error("MinIO client is not initialized. Initialize MinIO client again to save images.")
                self.minio_client = get_minio_client()
            if not self.minio_client.bucket_exists(BUCKET_NAME):
                self.minio_client.make_bucket(BUCKET_NAME)
                logger.info(f"Minio Bucket '{BUCKET_NAME}' created ✅")
            
            self.minio_client.put_object(
                BUCKET_NAME,
                image_filename,
                image_buffer,
                length=image_buffer.getbuffer().nbytes,
                content_type="image/jpeg"
            )
        except Exception as e:
            logger.error(f"Error saving to MinIO: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def _save_to_local(self, image_array):
        """Save image to local filesystem."""
        try:
            pil_image = Image.fromarray(image_array)
            output_path = f"{self.output_dir_frames}/frame_{self.frame_counter:06d}.jpg"
            pil_image.save(output_path, format="JPEG")
        except Exception as e:
            logger.error(f"Error saving to local filesystem: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # ------------------------------------------------------------------------
    # RABBITMQ COMMUNICATION
    # ------------------------------------------------------------------------
    
    def send_message(self, text):
        """
        Send message to RabbitMQ queue.
        
        Args:
            text (dict): Message payload
        """
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key='object_detection',
                body=json.dumps(text),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logger.info(f"Sent: {text}")
        except Exception as e:
            logger.error(f"Error sending message to RabbitMQ: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # ------------------------------------------------------------------------
    # CLEANUP AND UTILITIES
    # ------------------------------------------------------------------------
    
    def clean_output_directory(self, op_dir):
        """
        Empty the contents of output directory without deleting the directory itself.
        
        Args:
            op_dir (str): Directory path to clean
        """
        try:
            if os.path.exists(op_dir):
                for filename in os.listdir(op_dir):
                    file_path = os.path.join(op_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f'Failed to delete {file_path}. Reason: {e}')
                        logger.error(traceback.format_exc())
                logger.info(f"Emptied output directory: {op_dir}")
            else:
                logger.info(f"Output directory doesn't exist, will create: {op_dir}")
        except Exception as e:
            logger.error(f"Error cleaning output directory: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    def close(self):
        """Close file handle."""
        try:
            if hasattr(self, 'file_handle') and self.file_handle and not self.file_handle.closed:
                self.file_handle.close()
                logger.info("Publisher file handle closed")
        except Exception as e:
            logger.error(f"Error closing file handle: {e}")
            logger.error(traceback.format_exc())
# ============================================================================
# END OF FILE
# ============================================================================