import os
import sys
import subprocess
from pathlib import Path
import json
import io
from typing import Tuple
from src.utils.config import MINIO_HOST, logger
from datetime import timedelta


# Create a global MinIO client instance (singleton)
_minio_client = None
MINIO_BUCKET = "loss-prevention-enhanced-vlm-results"
MINIO_API_HOST_PORT=os.environ.get("MINIO_API_HOST_PORT",4000)
MINIO_CONSOLE_HOST_PORT=os.environ.get("MINIO_CONSOLE_HOST_PORT",4001)
MINIO_HOST=f"{os.environ.get('LP_IP','localhost')}:{MINIO_API_HOST_PORT}"

def get_presigned_url( file_path: str, bucket_name: str) -> str:
    """
    Generate a presigned URL for accessing a file in MinIO.
    
    Args:
        bucket_name: Name of the MinIO bucket
        file_path: Path to the file in the bucket
        expires_in: URL expiration time in seconds (default: 3600 = 1 hour)
    
    Returns:
        str: Presigned URL or empty string if failed
    """
    try:
        from minio.error import S3Error
    except ImportError:
        logger.error("MinIO Python SDK is not installed")
        return ""
    try:
        client = get_minio_client()
        if client is None:
            logger.error("MinIO client not available")
            return ""
        if not bucket_name:
            logger.error("Bucket name was empty, using default bucket")
            bucket_name = MINIO_BUCKET
        if not file_path:
            logger.error("File path was empty")
            return ""
        # Check if bucket exists
        if not client.bucket_exists(bucket_name):
            logger.error(f"Bucket '{bucket_name}' does not exist")
            return ""

        # Generate presigned URL
        url = client.presigned_get_object(bucket_name, file_path, expires=timedelta(minutes=15))
        logger.info(f"Generated presigned URL for {bucket_name}/{file_path}")
        return url

    except S3Error as e:
        logger.error(f"MinIO S3 error while generating presigned URL: {e}")
        return ""
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Exception while generating presigned URL: {e}")
        return ""

def get_minio_client():
    global _minio_client
    if _minio_client is None:
        try:
            from minio import Minio
        except ImportError:
            logger.error(
                "MinIO Python SDK is not installed. Please install it with:\n"
                "  pip install minio"
            )
            return None
        logger.info(f"############ MINIO_HOST =================={MINIO_HOST}")
        MINIO_ENDPOINT = os.environ.get("MINIO_HOST", MINIO_HOST)
        MINIO_ACCESS_KEY = os.environ.get("MINIO_ROOT_USER", "user")
        MINIO_SECRET_KEY = os.environ.get("MINIO_ROOT_PASSWORD", "passwd")
        _minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )
    return _minio_client

def save_to_minio(use_case:str, data_type: str, data, bucket: str = None) -> Tuple[bool, str]:  
    """
    Save data to MinIO bucket.
    
    Args:
        data_type: Either 'json' or 'image'
        data: For 'json': dict or JSON string. For 'image': bytes or file-like object
        filename: Name of the file to save (without extension for json, with extension for image)
        bucket: MinIO bucket name (optional, uses default if None)
    
    Returns:
        Tuple[bool, str]: (success, message/path)
    """
    try:
        from minio.error import S3Error
    except ImportError:
        logger.error(
            "MinIO Python SDK is not installed. Please install it with:\n"
            "  pip install minio"
        )
        return False, "MinIO SDK not installed"

    client = get_minio_client()
    if client is None:
        return False, "MinIO client not available"

    # Use provided bucket or default to MINIO_BUCKET
    target_bucket = bucket if bucket is not None else MINIO_BUCKET
    
    logger.info(f"Connected to MinIO: bucket={target_bucket}")

    try:
        # Ensure bucket exists
        if not client.bucket_exists(target_bucket):
            client.make_bucket(target_bucket)
            logger.info(f"Created bucket: {target_bucket}")

        # Validate and process data based on type
        if data_type.lower() == 'json':
            # Validate JSON data
            if isinstance(data, str):
                try:
                    json.loads(data)  # Validate JSON string
                    json_bytes = data.encode("utf-8")
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON string: {e}"
            elif isinstance(data, dict):
                try:
                    json_bytes = json.dumps(data, indent=2).encode("utf-8")
                except Exception as e:
                    return False, f"Failed to serialize dict to JSON: {e}"
            else:
                return False, "JSON data must be a dict or valid JSON string"
            
            file_obj = io.BytesIO(json_bytes)
            final_filename = f"{use_case}.json"
            content_type = "application/json"
            data_length = len(json_bytes)
            
        elif data_type.lower() == 'image':
            # Validate image data
            if isinstance(data, bytes):
                file_obj = io.BytesIO(data)
                data_length = len(data)

            else:
                return False, "Image data must be bytes or a file-like object"

            final_filename = f"{use_case}.jpg"  # Assume filename already has extension
            content_type = "image/jpeg"  # Default, could be enhanced to detect type
            
        else:
            return False, f"Unsupported data_type: {data_type}. Must be 'json' or 'image'"

        logger.info(f"Preparing to upload {data_type} data to MinIO: {target_bucket}/{final_filename}")   
        client.put_object(
            target_bucket,
            final_filename,
            file_obj,
            length=data_length,
            content_type=content_type
        )

        logger.info(f"Saved {data_type} to MinIO: {target_bucket}/{final_filename}")
        return True, f"{target_bucket}/{final_filename}"

    except S3Error as e:
        logger.error(f"MinIO S3 error: {e}")
        return False, str(e)
    except Exception as e:
        logger.error(f"Exception while saving to MinIO: {e}")
        return False, str(e)

def get_order_json_from_minio(order_id: str, bucket: str = None) -> dict:
    """
    Download and return the JSON (excluding video_id) from MinIO for the given order_id.
    """
    client = get_minio_client()
    if client is None:
        logger.error("MinIO client not available")
        return {"error": "MinIO client not available"}

    # Use provided bucket or default to MINIO_BUCKET
    target_bucket = bucket if bucket is not None else MINIO_BUCKET
    filename = f"{order_id}.json"
    
    try:
        response = client.get_object(target_bucket, filename)
        json_bytes = response.read()
        data = json.loads(json_bytes.decode("utf-8"))
        return data
    except Exception as e:
        logger.error(f"Failed to fetch {filename} from {target_bucket}: {e}")
        return {"error": f"Failed to fetch order: {e}"}
    
def get_frames_from_minio(minio_path,bucket_name=None) -> dict:
    """
    Download and return the JSON (excluding video_id) from MinIO for the given order_id.
    """
    client = get_minio_client()
    if client is None:
        logger.error("MinIO client not available")
        return {"error": "MinIO client not available"}
    if not minio_path:
        logger.error("No minio_path provided")
        return {"error": "No minio_path provided"}

    # Use provided bucket or default to MINIO_BUCKET
    target_bucket = bucket_name if bucket_name is not None else MINIO_BUCKET

    try:
        response = client.get_object(target_bucket, minio_path)
        image_bytes = response.read()
        response.close()
        response.release_conn()
        return image_bytes
    
    except Exception as e:
        logger.error(f"Failed to fetch {minio_path} from {target_bucket}: {e}")
        return {"error": f"Failed to fetch order: {e}"}

def get_video_url_from_minio(video_id: str, bucket: str = None) -> str:
    """
    Return a video URL or local file path for Gradio video preview.
    If Gradio blocks direct IP URLs, download the video from MinIO to a temp file and return the local path.
    """
    if not video_id:
        logger.error("No video_id provided for video preview.")
        return ""
    try:
        # Use provided bucket or default to MINIO_BUCKET for video location template
        target_bucket = bucket if bucket is not None else MINIO_BUCKET
        url = VIDEO_MINIO_LOCATION_TEMPLATE.format(video_id=video_id, bucket=target_bucket)
        logger.info(f"Generated video URL for preview: {url}")

        # Try to use HTTP/HTTPS URL first (works if Gradio allows)
        if url.startswith("http://") or url.startswith("https://"):
            # Gradio >=4 may block IPs; if so, fallback to local download
            parsed = urlparse(url)
            try:
                # If hostname is an IP address, fallback to download
                socket.inet_aton(parsed.hostname)
                is_ip = True
            except Exception:
                is_ip = False
            if not is_ip:
                return url

        # Fallback: Download video from MinIO to a temp file and return local path
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        logger.info(f"Downloading video from MinIO to local temp file: {tmp.name}")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.error(f"Failed to generate or download video for preview: {e}")
        return ""

def get_video_url_from_minio(video_id: str) -> str:
    """
    Return a video URL or local file path for Gradio video preview.
    If Gradio blocks direct IP URLs, download the video from MinIO to a temp file and return the local path.
    """
    if not video_id:
        logger.error("No video_id provided for video preview.")
        return ""
    try:
        url = VIDEO_MINIO_LOCATION_TEMPLATE.format(video_id=video_id)
        logger.info(f"Generated video URL for preview: {url}")

        # Try to use HTTP/HTTPS URL first (works if Gradio allows)
        if url.startswith("http://") or url.startswith("https://"):
            # Gradio >=4 may block IPs; if so, fallback to local download
            import socket
            from urllib.parse import urlparse
            parsed = urlparse(url)
            try:
                # If hostname is an IP address, fallback to download
                socket.inet_aton(parsed.hostname)
                is_ip = True
            except Exception:
                is_ip = False
            if not is_ip:
                return url

        # Fallback: Download video from MinIO to a temp file and return local path
        import tempfile
        import requests
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        logger.info(f"Downloading video from MinIO to local temp file: {tmp.name}")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.error(f"Failed to generate or download video for preview: {e}")
        return ""



