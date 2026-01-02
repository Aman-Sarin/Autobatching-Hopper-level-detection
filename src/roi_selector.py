import cv2
import json
import os
import numpy as np

ROI_POINTS = []
ROI_FINALIZED = False

def mouse_callback(event, x, y, flags, param):
    global ROI_POINTS, ROI_FINALIZED

    # Left click → add vertex
    if event == cv2.EVENT_LBUTTONDOWN and not ROI_FINALIZED:
        ROI_POINTS.append((x, y))

    # Right click → finalize ROI and save
    elif event == cv2.EVENT_RBUTTONDOWN and not ROI_FINALIZED:
        if len(ROI_POINTS) < 3:
            return  # silently ignore
        ROI_FINALIZED = True
        save_roi()

def save_roi():
    os.makedirs("../config", exist_ok=True)
    with open("../config/roi.json", "w") as f:
        json.dump({"hopper_roi": ROI_POINTS}, f, indent=4)
    print("ROI saved")

def main():
    global ROI_POINTS, ROI_FINALIZED

    video_path = "../data/mixer 01 131125/sample video 2.mp4"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Video not found")
        return

    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Could not read video")
        return

    cv2.namedWindow("Select Hopper ROI", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Select Hopper ROI", 900, 600)
    cv2.setMouseCallback("Select Hopper ROI", mouse_callback)

    while True:
        display = frame.copy()
        # Draw selected ROI points (green dots)
        for pt in ROI_POINTS:
            cv2.circle(display, pt, 4, (0, 255, 0), -1)
        # If ROI finalized → darken outside
        if ROI_FINALIZED:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [np.array(ROI_POINTS, dtype=np.int32)], 255)
            display[mask == 0] = (display[mask == 0] * 0.3).astype(np.uint8)

        cv2.imshow("Select Hopper ROI", display)
        key = cv2.waitKey(1) & 0xFF

        # Reset
        if key == ord('r'):
            ROI_POINTS = []
            ROI_FINALIZED = False
            print("ROI reset")

        elif key == 27:
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

