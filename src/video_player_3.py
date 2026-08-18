import cv2
import settings
import time
import os
import threading
import numpy as np
from datetime import datetime
from pycomm3 import LogixDriver
from utils import (
    load_rois,
    apply_roi_mask,
    extract_v_channel,
    threshold_material,
    clean_mask
)

# -------- Frames for Dashboard --------
CURRENT_V_FRAME = None
CURRENT_MASK_FRAME = None
plc = None
cap = None
_plc_lock = threading.RLock()

# -------- Dashboard Status --------

CURRENT_PERCENTAGE = 0.0
CURRENT_FLOW_PERCENTAGE = 0.0
CURRENT_THRESHOLD = 0

CURRENT_GATE = False
CURRENT_TRIGGER = False

CURRENT_STATE = "READY"
CURRENT_CAUSE = "-"
CURRENT_VISION_EMPTY = False

# ---------------- Dashboard Control ----------------

running = False

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

GATE_RESET_DELAY = 8
REARM_CONFIRM_SECONDS = 20

VISION_RESET_PERCENTAGE = 35.0
VISION_RESET_SECONDS = 30

def read_gate_open():
    with _plc_lock:
        if plc is None:
            raise RuntimeError("PLC connection is not available")

        # Configure this as the mixer-gate CLOSED feedback tag in the private
        # settings file. The installed meaning is 1=CLOSED and 0=OPEN.
        result = plc.read(settings.GATE_CLOSED_TAG)
        if not result:
            raise ConnectionError(
                f"Could not read PLC gate tag: {result.error or 'unknown error'}"
            )

        return not bool(result.value)


def write_camera_trigger(value):
    global CURRENT_TRIGGER

    with _plc_lock:
        if value and not running:
            raise RuntimeError(
                "PLC trigger ON blocked because detection is stopping"
            )

        if plc is None:
            raise RuntimeError("PLC connection is not available")

        # Configure this as the Boolean Python-to-PLC request tag in the
        # private settings file. Do not hardcode the factory tag here.
        result = plc.write(settings.CAMERA_TRIGGER_TAG, bool(value))
        if not result:
            raise ConnectionError(
                f"Could not write PLC trigger tag: {result.error or 'unknown error'}"
            )

        CURRENT_TRIGGER = bool(value)


def force_trigger_off():
    """Best-effort fail-safe reset of the PLC request bit."""
    global CURRENT_TRIGGER

    with _plc_lock:
        if plc is None or not settings.CAMERA_TRIGGER_TAG:
            CURRENT_TRIGGER = False
            return plc is None

        try:
            result = plc.write(settings.CAMERA_TRIGGER_TAG, False)
        except Exception as error:
            print(f"PLC trigger OFF warning: {error}")
            return False

        if not result:
            print(
                "PLC trigger OFF warning: "
                f"{result.error or 'unknown error'}"
            )
            return False

        CURRENT_TRIGGER = False
        return True


def request_stop():
    """Block new trigger writes and request an orderly detector stop."""
    global running

    running = False
    force_trigger_off()


def shutdown_resources():
    """Release camera, PLC, and OpenCV resources after any exit path."""
    global cap
    global plc
    global running

    running = False
    force_trigger_off()

    with _plc_lock:
        if plc is not None:
            try:
                plc.close()
            except Exception as error:
                print(f"PLC close warning: {error}")
            finally:
                plc = None

    if cap is not None:
        cap.release()
        cap = None

    cv2.destroyAllWindows()


def main():

    global running
    global CURRENT_V_FRAME
    global CURRENT_MASK_FRAME

    global CURRENT_PERCENTAGE
    global CURRENT_FLOW_PERCENTAGE
    global CURRENT_THRESHOLD

    global CURRENT_GATE
    global CURRENT_TRIGGER
    global CURRENT_STATE
    global CURRENT_CAUSE
    global CURRENT_VISION_EMPTY
    global cap

    settings.reload()
    settings.require_connection_settings(
        "CAMERA_URL",
        "PLC_IP",
        "GATE_CLOSED_TAG",
        "CAMERA_TRIGGER_TAG",
    )

    running = True

    primary_roi, secondary_roi = load_rois()
    ROI_FILE = settings.ROI_FILE

    last_roi_modified = os.path.getmtime(ROI_FILE)

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


    primary_empty_start_time = None
    secondary_empty_start_time = None
    primary_empty = False
    secondary_empty = False
    vision_empty = False
    trigger_cause = None
    plc_trigger_active = False
    system_state = "READY"
    gate_open_seen = False
    rearm_start_time = None
    gate_open_time = None

    SNAPSHOT_FOLDER = settings.SNAPSHOT_DIR
    MASK_FOLDER = settings.MASK_DIR

    persistence_map = None
    last_saved_hour = None
    save_overlay_trigger = False
    save_trigger_name = None
    save_trigger_timestamp = None

    global plc
    # Enter the Logix-compatible PLC IP address in
    # config/settings.local.json; do not hardcode it in this file.
    plc = LogixDriver(settings.PLC_IP)
    if not plc.open():
        plc = None
        cap.release()
        raise ConnectionError(f"Could not connect to PLC at {settings.PLC_IP}")
    print("PLC Connected")

    os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)
    os.makedirs(MASK_FOLDER, exist_ok=True)

    running = True

    last_gate_poll_time = 0
    gate_open = False

    while running:

        # If camera is disconnected, keep trying to reconnect
        THRESHOLD_VALUE = get_threshold()
        try:
            current_modified = os.path.getmtime(ROI_FILE)

            if current_modified != last_roi_modified:

                primary_roi, secondary_roi = load_rois()

                last_roi_modified = current_modified

                print("ROI Reloaded")

        except Exception:
            pass

        if not cap.isOpened():

            print("Camera disconnected. Reconnecting...")

            while running:

                cap = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)

                if cap.isOpened():
                    print("Camera reconnected.")
                    break

                print("Reconnect failed. Trying again in 2 seconds...")
                time.sleep(RECONNECT_DELAY)

            if not running:
                break

        ret, frame = cap.read()

        if not ret:

            consecutive_failures += 1
            print(f"Frame lost ({consecutive_failures})")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:

                print("Too many frame losses. Restarting camera connection...")

                cap.release()

                if plc_trigger_active:
                    print(
                        "Camera failure while PLC trigger was active. "
                        "Resetting trigger and stopping detection."
                    )
                    force_trigger_off()
                    plc_trigger_active = False
                    system_state = "FAULT"
                    CURRENT_STATE = system_state
                    running = False

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

        vision_empty = primary_empty or secondary_empty

        if now - last_gate_poll_time >= 0.5:
            gate_open = read_gate_open()
            last_gate_poll_time = now

        # ==========================================================
        # STATE : READY
        # ==========================================================

        if system_state == "READY":

            if vision_empty and (not gate_open):

                if not plc_trigger_active:

                    write_camera_trigger(True)
                    plc_trigger_active = True

                trigger_cause = (
                    "BOTH" if primary_empty and secondary_empty
                    else "PRIMARY" if primary_empty
                    else "SECONDARY"
                )

                timestamp = time.strftime("%Y%m%d_%H%M%S")

                cv2.imwrite(
                    f"{SNAPSHOT_FOLDER}/{trigger_cause}_{timestamp}.jpg",
                    frame
                )

                save_overlay_trigger = True
                save_trigger_name = trigger_cause
                save_trigger_timestamp = timestamp

                print("Camera Trigger Sent")

                system_state = "WAIT_GATE_OPEN"

        # ==========================================================
        # STATE : WAIT_GATE_OPEN
        # ==========================================================

        elif system_state == "WAIT_GATE_OPEN":

            if gate_open:

                gate_open_seen = True
                gate_open_time = now

                print("Gate Open Detected")

                system_state = "WAIT_TRIGGER_RESET"


        # ==========================================================
        # STATE : WAIT_TRIGGER_RESET
        # ==========================================================

        elif system_state == "WAIT_TRIGGER_RESET":

            if now - gate_open_time >= GATE_RESET_DELAY:

                write_camera_trigger(False)
                plc_trigger_active = False
                print("PLC Trigger Reset")
                system_state = "WAIT_GATE_CLOSE"

        # ==========================================================
        # STATE : WAIT_GATE_CLOSE
        # ==========================================================

        elif system_state == "WAIT_GATE_CLOSE":

            if gate_open_seen and (not gate_open):

                print("Gate Closed")

                system_state = "WAIT_REARM"

        # ==========================================================
        # STATE : WAIT_REARM
        # ==========================================================

        elif system_state == "WAIT_REARM":

            if percentage > VISION_RESET_PERCENTAGE:

                if rearm_start_time is None:

                    rearm_start_time = now

                elif now - rearm_start_time >= VISION_RESET_SECONDS:

                    gate_open_seen = False
                    gate_open_time = None
                    rearm_start_time = None
                    trigger_cause = None
                    system_state = "READY"
                    vision_empty = False

                    print("System Rearmed")

            else:

                rearm_start_time = None


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

        y += 35

        cv2.putText(
            overlay,
            f"Vision Empty: {'YES' if vision_empty else 'NO'}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0,255,255),
            2
        )

        y += 35

        cv2.putText(
            overlay,
            f"Gate: {'OPEN' if gate_open else 'CLOSED'}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255,0,255),
            2
        )

        y += 35

        cv2.putText(
        overlay,
        f"PLC Trigger: {'ON' if plc_trigger_active else 'OFF'}",
        (15, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0,255,0),
        2
        )

        y += 35

        cv2.putText(
            overlay,
            f"State: {system_state}",
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255,255,255),
            2
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
        CURRENT_PERCENTAGE = percentage
        CURRENT_FLOW_PERCENTAGE = flow_percentage

        CURRENT_THRESHOLD = THRESHOLD_VALUE

        CURRENT_GATE = gate_open

        CURRENT_TRIGGER = plc_trigger_active

        CURRENT_STATE = system_state

        CURRENT_CAUSE = (
            trigger_cause if trigger_cause is not None else "-"
        )

        CURRENT_VISION_EMPTY = vision_empty
        CURRENT_V_FRAME = v_channel.copy()
        CURRENT_MASK_FRAME = overlay.copy()

        if not running:
            break

    shutdown_resources()


if __name__ == "__main__":
    try:
        main()
    finally:
        shutdown_resources()
