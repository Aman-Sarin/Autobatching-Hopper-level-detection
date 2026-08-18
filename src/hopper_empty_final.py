import cv2
import settings
import time
import numpy as np
from datetime import datetime
from utils import (
    load_rois,
    apply_roi_mask,
    extract_v_channel,
    threshold_material,
    clean_mask
)

# ---------------- PARAMETERS ----------------
def get_threshold():

    hour = datetime.now().hour

    if 6 <= hour < 11:
        return settings.MORNING_THRESHOLD

    elif 11 <= hour < 16:
        return settings.AFTERNOON_THRESHOLD

    elif 16 <= hour < 19:
        return settings.MORNING_THRESHOLD

    else:
        return settings.NIGHT_THRESHOLD

TIME_CONFIRM_SECONDS = 8

SECONDARY_CONFIRM_SECONDS = 4

PERSISTENCE_TIME_SECONDS = 4
MIN_STUCK_AREA = 30

VISION_RESET_PERCENTAGE = 35.0
VISION_RESET_SECONDS = 30


def main():
    settings.reload()
    settings.require_connection_settings("CAMERA_URL")

    primary_roi, secondary_roi = load_rois()

    # Enter the complete private camera RTSP URL in
    # config/settings.local.json; do not hardcode it in this file.
    camera_url = settings.CAMERA_URL
    cap = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("Could not connect to camera.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30

    PERSISTENCE_THRESHOLD = int(PERSISTENCE_TIME_SECONDS * fps)

    # Watchdog variables
    MAX_CONSECUTIVE_FAILURES = 15
    RECONNECT_DELAY = 2      # seconds
    consecutive_failures = 0

    cv2.namedWindow("V Channel", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Material Mask", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("V Channel", 600, 400)
    cv2.resizeWindow("Material Mask", 600, 400)

    primary_empty_start_time = None
    secondary_empty_start_time = None
    primary_empty = False
    secondary_empty = False
    hopper_empty_state = False
    trigger_cause = None
    refill_start_time = None
    SNAPSHOT_FOLDER = settings.SNAPSHOT_DIR
    MASK_FOLDER = settings.MASK_DIR

    persistence_map = None
    last_saved_hour = None
    save_overlay_trigger = False
    save_trigger_name = None
    save_trigger_timestamp = None

    import os
    os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)
    os.makedirs(MASK_FOLDER, exist_ok=True)

    while True:

        # If camera is disconnected, keep trying to reconnect
        THRESHOLD_VALUE = get_threshold()
        if not cap.isOpened():

            print("Camera disconnected. Reconnecting...")

            while True:

                cap = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)

                if cap.isOpened():
                    print("Camera reconnected.")
                    break

                print("Reconnect failed. Trying again in 2 seconds...")
                time.sleep(RECONNECT_DELAY)

        ret, frame = cap.read()

        if not ret:

            consecutive_failures += 1
            print(f"Frame lost ({consecutive_failures})")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:

                print("Too many frame losses. Restarting camera connection...")

                cap.release()

            time.sleep(0.1)
            continue

        # Frame received successfully
        consecutive_failures = 0

        # ---------------- PRIMARY ROI ----------------
        roi, roi_mask = apply_roi_mask(frame, primary_roi)
        v_channel = extract_v_channel(roi)
        material_mask = clean_mask(
            threshold_material(v_channel, THRESHOLD_VALUE)
        )

        if persistence_map is None:
            persistence_map = np.zeros_like(material_mask, dtype=np.int32)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            material_mask, connectivity=8
        )

        main_label = None
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            main_label = 1 + np.argmax(areas)

        main_mask = np.zeros_like(material_mask, dtype=np.uint8)
        if main_label is not None:
            main_mask[labels == main_label] = 255

        detached_mask = cv2.subtract(material_mask, main_mask)

        persistence_map[detached_mask == 255] += 1
        persistence_map[detached_mask == 0] = 0

        stuck_mask = np.zeros_like(material_mask, dtype=np.uint8)
        stuck_mask[persistence_map >= PERSISTENCE_THRESHOLD] = 255

        num_s, lbl_s, stats_s, _ = cv2.connectedComponentsWithStats(
            stuck_mask, connectivity=8
        )

        cleaned_stuck = np.zeros_like(stuck_mask)
        for i in range(1, num_s):
            if stats_s[i, cv2.CC_STAT_AREA] >= MIN_STUCK_AREA:
                cleaned_stuck[lbl_s == i] = 255

        stuck_mask = cleaned_stuck

        total_white = cv2.countNonZero(material_mask)
        stuck_white = cv2.countNonZero(stuck_mask)
        roi_area = cv2.countNonZero(roi_mask)

        effective_white = max(total_white - stuck_white, 0)
        percentage = (effective_white / roi_area) * 100 if roi_area > 0 else 0

        # ---------------- SECONDARY ROI (FLOW) ----------------
        flow_roi, flow_roi_mask = apply_roi_mask(frame, secondary_roi)
        flow_v = extract_v_channel(flow_roi)
        flow_mask = clean_mask(
            threshold_material(flow_v, THRESHOLD_VALUE)
        )

        flow_white = cv2.countNonZero(flow_mask)
        flow_area = cv2.countNonZero(flow_roi_mask)
        flow_percentage = (flow_white / flow_area) * 100 if flow_area > 0 else 0


        # ---------------- DECISION LOGIC ----------------

        now = time.time()

        # ---------- PRIMARY DETECTOR ----------

        if percentage < settings.PRIMARY_EMPTY_PERCENTAGE:

            if primary_empty_start_time is None:
                primary_empty_start_time = now

            elif now - primary_empty_start_time >= TIME_CONFIRM_SECONDS:
                primary_empty = True

        else:
            primary_empty = False
            primary_empty_start_time = None


        # ---------- SECONDARY DETECTOR ----------

        if flow_percentage < settings.SECONDARY_EMPTY_PERCENTAGE:

            if secondary_empty_start_time is None:
                secondary_empty_start_time = now

            elif now - secondary_empty_start_time >= SECONDARY_CONFIRM_SECONDS:
                secondary_empty = True

        else:
            secondary_empty = False
            secondary_empty_start_time = None


        # ---------- FINAL HOPPER EMPTY ----------

        if not hopper_empty_state:

            if primary_empty or secondary_empty:

                hopper_empty_state = True

                if primary_empty and secondary_empty:
                    trigger_cause = "BOTH"

                elif primary_empty:
                    trigger_cause = "PRIMARY"

                else:
                    trigger_cause = "SECONDARY"

                timestamp = time.strftime("%Y%m%d_%H%M%S")

                cv2.imwrite(
                    f"{SNAPSHOT_FOLDER}/{trigger_cause}_{timestamp}.jpg",
                    frame
                )
                save_overlay_trigger = True
                save_trigger_name = trigger_cause
                save_trigger_timestamp = timestamp

                print(f"Hopper Empty Triggered by {trigger_cause}")

        # ---------------- REFILL DETECTION ----------------

        if hopper_empty_state:
            if percentage > VISION_RESET_PERCENTAGE:
                if refill_start_time is None:
                    refill_start_time = now

                elif now - refill_start_time >= VISION_RESET_SECONDS:

                    hopper_empty_state = False
                    trigger_cause = None
                    refill_start_time = None
                    print("System reset.")

            else:
                refill_start_time = None

        # ---------------- VISUALIZATION ----------------
        overlay = cv2.cvtColor(material_mask, cv2.COLOR_GRAY2BGR)

        cv2.polylines(
        overlay,
        [primary_roi],
        True,
        (0, 0, 255),   # red
        2
)

        # Draw stuck material (blue contours)
        contours, _ = cv2.findContours(
            stuck_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        cv2.drawContours(overlay, contours, -1, (255, 0, 0), 2)

        # Draw secondary ROI boundary (green)
        cv2.polylines(
            overlay,
            [secondary_roi],
            isClosed=True,
            color=(0, 255, 0),
            thickness=2
        )

        # Text layout
        y = 45

        cv2.putText(
            overlay,
            f"Material: {percentage:.2f} % | White px: {total_white} | Subtracted px: {stuck_white}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2
        )

        y += 35

        cv2.putText(
            overlay,
            f"Secondary ROI: {flow_percentage:.1f} %",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2
        )

        y += 35

        cv2.putText(
            overlay,
            f"Threshold: {THRESHOLD_VALUE}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        y += 35

        cv2.putText(
            overlay,
            f"Cause: {trigger_cause}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        if hopper_empty_state:
            y += 40
            cv2.putText(
                overlay,
                "HOPPER EMPTY",
                (15, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.3,
                (0, 0, 255),
                3
            )

        if save_overlay_trigger:
            cv2.imwrite(
                f"{MASK_FOLDER}/{save_trigger_name}_{save_trigger_timestamp}_Overlay.jpg",
                overlay
            )

            save_overlay_trigger = False


        current_time = datetime.now()

        if current_time.minute == 0:
            if current_time.hour != last_saved_hour:
                filename = current_time.strftime("Hourly_%Y%m%d_%H00.jpg")
                cv2.imwrite(
                    f"{MASK_FOLDER}/{filename}",
                    overlay
                )

                print(f"Hourly overlay saved : {filename}")
                last_saved_hour = current_time.hour

        cv2.imshow("V Channel", v_channel)
        cv2.imshow("Material Mask", overlay)

        if cv2.waitKey(30) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
