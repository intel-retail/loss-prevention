import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from utils.save_results import get_frames_from_minio

class FrameProcessingError(Exception):
    pass


def compute_optical_flow_mag_fast(gray1, gray2):
    """Compute average motion magnitude on small grayscale frames."""
    flow = cv2.calcOpticalFlowFarneback(
        gray1, gray2, None, 0.5, 3, 15, 3, 5, 1.2, 0
    )
    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return np.mean(mag)


def get_best_frame(frames_list, bucket_name="", alpha=0.5, resize_factor=0.2):
    prev_gray = None
    best_frame = None
    best_score = -1

    try:
        for f in frames_list:
            # Fetch → decode
            frame_bytes = get_frames_from_minio(f, bucket_name=bucket_name)
            img = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue

            # Resize once — used for BOTH SSIM & optical flow
            small = cv2.resize(img, None, fx=resize_factor, fy=resize_factor,
                               interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                # Optical flow on resized grayscale frames (FASTER)
                motion = compute_optical_flow_mag_fast(prev_gray, gray)
                motion_score = 1 / (1 + motion)

                # SSIM (no full map → much faster)
                ssim_score = ssim(prev_gray, gray)

                # Weighted score
                stability_score = alpha * ssim_score + (1 - alpha) * motion_score

                if stability_score > best_score:
                    best_score = stability_score
                    best_frame = f

            prev_gray = gray

        return best_frame, best_score if best_frame else (None, 0.0)

    except Exception as e:
        raise FrameProcessingError(f"Error processing frames: {e}")
