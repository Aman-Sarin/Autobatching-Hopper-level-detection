import cv2
import time
from utils import (
    load_roi,
    apply_roi_mask,
    extract_v_channel,
    threshold_material,
    clean_mask,
    white_pixel_percentage
)

VIDEO_PATH = "../data/mixer 01 131125/Sample Video 2.mp4"

# ---- PARAMETERS (tunable) ----
THRESHOLD_VALUE = 100
EMPTY_PERCENTAGE = 30.0     # x % material below which hopper is "empty"
TIME_CONFIRM_SECONDS = 12   # must stay low for x minute

def main():
    roi_points = load_roi()
    cap = cv2.VideoCapture(VIDEO_PATH)

    # Create windows ONCE
    cv2.namedWindow("V Channel", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Material Mask", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("V Channel", 600, 400)
    cv2.resizeWindow("Material Mask", 600, 400)

    empty_start_time = None
    trigger_sent = False

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        roi, roi_mask = apply_roi_mask(frame, roi_points)

        v_channel = extract_v_channel(roi)
        material_mask = threshold_material(v_channel, THRESHOLD_VALUE)
        material_mask = clean_mask(material_mask)

        percentage = white_pixel_percentage(material_mask, roi_mask)
        # print(f"\rWhite pixel %: {percentage:6.2f}", end="")
        # ---- OVERLAY TEXT PREP (for display only) ----
        overlay = cv2.cvtColor(material_mask, cv2.COLOR_GRAY2BGR)

        cv2.putText(
            overlay,
            f"Material: {percentage:.2f} %",
            (15, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 255),
            3,
            cv2.LINE_AA
        )

        # ---- TIME-BASED TRIGGER LOGIC ----
        if percentage < EMPTY_PERCENTAGE:
            if empty_start_time is None:
                empty_start_time = time.time()
            elif time.time() - empty_start_time >= TIME_CONFIRM_SECONDS:
                if not trigger_sent:
                    print("HOPPER EMPTY")
                    trigger_sent = True
        else:
            empty_start_time = None
            trigger_sent = False

        if trigger_sent:
            cv2.putText(
                overlay,
                "HOPPER EMPTY",
                (15, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 0, 255),
                3,
                cv2.LINE_AA
            )

        # Display
        cv2.imshow("V Channel", v_channel)
        cv2.imshow("Material Mask", overlay)

        if cv2.waitKey(30) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
