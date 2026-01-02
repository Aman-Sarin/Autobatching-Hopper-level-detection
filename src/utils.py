import cv2
import json
import numpy as np

def load_roi(config_path="../config/roi.json"):
    with open(config_path, "r") as f:
        data = json.load(f)
    return np.array(data["hopper_roi"], dtype=np.int32)


def apply_roi_mask(frame, roi_points):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [roi_points], 255)

    roi = cv2.bitwise_and(frame, frame, mask=mask)
    return roi, mask


def extract_v_channel(bgr_img):
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    return hsv[:, :, 2]


def threshold_material(v_channel, threshold=50):
    _, binary = cv2.threshold(v_channel, threshold, 255, cv2.THRESH_BINARY)
    return binary

def clean_mask(binary_mask):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    opened = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    return cleaned


def white_pixel_percentage(binary_mask, roi_mask):
    roi_pixels = roi_mask > 0

    if not np.any(roi_pixels):
        return 0.0

    white_pixels = binary_mask == 255
    white_in_roi = np.count_nonzero(white_pixels & roi_pixels)
    total_roi_pixels = np.count_nonzero(roi_pixels)

    return (white_in_roi / total_roi_pixels) * 100

