import cv2
import json
import numpy as np
from pathlib import Path


# ---------------- ROI LOADING ----------------

DEFAULT_ROI_PATH = Path(__file__).resolve().parent.parent / "config" / "roi.json"


def load_rois(config_path=None):
    """
    Loads primary and secondary ROIs from config.
    Returns:
        primary_roi (np.ndarray)
        secondary_roi (np.ndarray)
    """
    path = Path(config_path) if config_path is not None else DEFAULT_ROI_PATH

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    primary_roi = np.array(data["primary_roi"], dtype=np.int32)
    secondary_roi = np.array(data["secondary_roi"], dtype=np.int32)

    return primary_roi, secondary_roi


def load_roi(config_path=None):
    """Compatibility helper for the original single-ROI experiments."""
    primary_roi, _ = load_rois(config_path)
    return primary_roi


# ---------------- ROI MASKING ----------------

def apply_roi_mask(frame, roi_points):
    """
    Applies polygon ROI mask to frame.
    Returns:
        roi_image
        roi_mask
    """
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [roi_points], 255)

    roi = cv2.bitwise_and(frame, frame, mask=mask)
    return roi, mask


# ---------------- CHANNEL EXTRACTION ----------------

def extract_v_channel(bgr_img):
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    return hsv[:, :, 2]


# ---------------- THRESHOLDING ----------------

def threshold_material(v_channel, threshold=50):
    _, binary = cv2.threshold(v_channel, threshold, 255, cv2.THRESH_BINARY)
    return binary


# ---------------- MORPHOLOGICAL CLEANUP ----------------

def clean_mask(binary_mask):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    opened = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    return cleaned


# ---------------- METRICS ----------------

def white_pixel_percentage(binary_mask, roi_mask):
    roi_pixels = roi_mask > 0

    if not np.any(roi_pixels):
        return 0.0

    white_pixels = binary_mask == 255
    white_in_roi = np.count_nonzero(white_pixels & roi_pixels)
    total_roi_pixels = np.count_nonzero(roi_pixels)

    return (white_in_roi / total_roi_pixels) * 100.0

