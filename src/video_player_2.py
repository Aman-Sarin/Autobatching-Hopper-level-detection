import cv2
import time
import numpy as np
from pathlib import Path
from utils_old import (
    load_roi,
    apply_roi_mask,
    extract_v_channel,
    threshold_material,
    clean_mask
)

VIDEO_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "mixer 01 131125"
    / "Sample Video 5.mp4"
)

# PARAMETERS
THRESHOLD_VALUE = 100

EMPTY_PERCENTAGE = 28.0
TIME_CONFIRM_SECONDS = 10

# PERSISTENCE PARAMETERS
PERSISTENCE_TIME_SECONDS = 10    # how long detached pixels must persist
MIN_STUCK_AREA = 30             # ignore tiny regions

def main():
    roi_points = load_roi()
    cap = cv2.VideoCapture(VIDEO_PATH)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30  # fallback

    PERSISTENCE_THRESHOLD = int(PERSISTENCE_TIME_SECONDS * fps)

    cv2.namedWindow("V Channel", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Material Mask", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("V Channel", 600, 400)
    cv2.resizeWindow("Material Mask", 600, 400)

    empty_start_time = None
    trigger_sent = False

    persistence_map = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        roi, roi_mask = apply_roi_mask(frame, roi_points)

        v_channel = extract_v_channel(roi)
        material_mask = clean_mask(
            threshold_material(v_channel, THRESHOLD_VALUE)
        )

        if persistence_map is None:
            persistence_map = np.zeros_like(material_mask, dtype=np.int32)

        # ---- CONNECTED COMPONENT ANALYSIS ----
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            material_mask, connectivity=8
        )

        # Identify main bulk (largest component)
        main_label = None
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            main_label = 1 + np.argmax(areas)

        main_mask = np.zeros_like(material_mask, dtype=np.uint8)
        if main_label is not None:
            main_mask[labels == main_label] = 255

        # Detached = material minus main bulk
        detached_mask = cv2.subtract(material_mask, main_mask)

        # UPDATE PERSISTENCE (DETACHED ONLY)
        persistence_map[detached_mask == 255] += 1
        persistence_map[detached_mask == 0] = 0

        # STUCK MASK
        stuck_mask = np.zeros_like(material_mask, dtype=np.uint8)
        stuck_mask[persistence_map >= PERSISTENCE_THRESHOLD] = 255

        # Remove tiny stuck regions
        num_s, lbl_s, stats_s, _ = cv2.connectedComponentsWithStats(
            stuck_mask, connectivity=8
        )

        cleaned_stuck = np.zeros_like(stuck_mask)
        for i in range(1, num_s):
            if stats_s[i, cv2.CC_STAT_AREA] >= MIN_STUCK_AREA:
                cleaned_stuck[lbl_s == i] = 255

        stuck_mask = cleaned_stuck

        # METRICS
        total_white = cv2.countNonZero(material_mask)
        stuck_white = cv2.countNonZero(stuck_mask)
        roi_area = cv2.countNonZero(roi_mask)

        effective_white = max(total_white - stuck_white, 0)
        percentage = (effective_white / roi_area) * 100 if roi_area > 0 else 0

        # OVERLAY
        overlay = cv2.cvtColor(material_mask, cv2.COLOR_GRAY2BGR)

        # Draw stuck material (blue outline)
        contours, _ = cv2.findContours(
            stuck_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours, -1, (255, 0, 0), 2)

        y = 45
        dy = 40

        cv2.putText(
            overlay, f"Material: {percentage:.2f} %",
            (15, y), cv2.FONT_HERSHEY_SIMPLEX,
            1.2, (255, 255, 255), 3
        )
        y += dy

        cv2.putText(
            overlay, f"White px: {total_white}",
            (15, y), cv2.FONT_HERSHEY_SIMPLEX,
            1, (200, 200, 200), 3
        )
        y += dy

        cv2.putText(
            overlay, f"Subtracted px: {stuck_white}",
            (15, y), cv2.FONT_HERSHEY_SIMPLEX,
            1, (0, 200, 255), 3
        )
        y += dy

        # EMPTY LOGIC
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
                overlay, "HOPPER EMPTY",
                (15, y + 30), cv2.FONT_HERSHEY_SIMPLEX,
                1.4, (0, 0, 255), 3
            )

        # DISPLAY
        cv2.imshow("V Channel", v_channel)
        cv2.imshow("Material Mask", overlay)

        if cv2.waitKey(30) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()




