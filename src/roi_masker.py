import cv2
import json
import numpy as np

def load_roi(path="../config/roi.json"):
    with open(path, "r") as f:
        return np.array(json.load(f)["hopper_roi"], dtype=np.int32)

def apply_roi_mask(frame, roi_points):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [roi_points], 255)
    roi = cv2.bitwise_and(frame, frame, mask=mask)
    return roi, mask

def main():
    video_path = "../data/mixer 01 131125/sample video 1.mp4"

    roi_points = load_roi()
    cap = cv2.VideoCapture(video_path)
    # Create windows ONCE
    cv2.namedWindow("Original", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Selected ROI", cv2.WINDOW_NORMAL)
    # cv2.resizeWindow("Selected ROI", 1200, 800)
    # cv2.namedWindow("ROI - H Channel", cv2.WINDOW_NORMAL)
    # cv2.namedWindow("ROI - S Channel", cv2.WINDOW_NORMAL)
    # cv2.namedWindow("ROI - V Channel", cv2.WINDOW_NORMAL)
    cv2.namedWindow("V Channel", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Material Mask", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("Selected ROI", 600, 400)
    cv2.resizeWindow("Material Mask", 600, 400)
    cv2.resizeWindow("V Channel", 600, 400)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        roi, mask = apply_roi_mask(frame, roi_points)
        # cv2.imshow("Original", frame)
        # cv2.imshow("Selected ROI", roi)
        # Convert ROI to HSV
        # hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # h, s, v = cv2.split(hsv)

        # Show HSV channels
        # cv2.imshow("ROI - H Channel", h)
        # cv2.imshow("ROI - S Channel", s)
        # cv2.imshow("ROI - V Channel", v)
        # Convert ROI to HSV and extract V channel
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]

        # Binary threshold on V channel
        V_THRESHOLD = 40  # starting value, we will tune this
        _, material_mask = cv2.threshold(
            v_channel,
            V_THRESHOLD,
            255,
            cv2.THRESH_BINARY
        )

        cv2.imshow("V Channel", v_channel)
        cv2.imshow("Material Mask", material_mask)
        if cv2.waitKey(30) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
