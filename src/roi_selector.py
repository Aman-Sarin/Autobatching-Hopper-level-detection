import cv2
import json
import os
import numpy as np
import settings

# ---------------- CONFIG ----------------
ROI_SAVE_PATH = settings.ROI_FILE

# -------- Dashboard Control --------
running = False

# ---------------- GLOBAL STATE ----------------
primary_points = []
secondary_points = []

primary_started = False
secondary_started = False


# -------------------------------------------------
# Load existing ROI (if present)
# -------------------------------------------------
def load_existing_rois():
    global primary_points, secondary_points

    if not os.path.exists(ROI_SAVE_PATH):
        print("No existing ROI file found.")
        return

    try:
        with open(ROI_SAVE_PATH, "r") as f:
            data = json.load(f)

        primary_points = data.get("primary_roi", [])
        secondary_points = data.get("secondary_roi", [])

        print("Existing ROI loaded.")

    except Exception as e:
        print("Could not load ROI:", e)


# -------------------------------------------------
# Save ROI
# -------------------------------------------------
def save_rois():

    os.makedirs(os.path.dirname(ROI_SAVE_PATH), exist_ok=True)

    with open(ROI_SAVE_PATH, "w") as f:
        json.dump(
            {
                "primary_roi": primary_points,
                "secondary_roi": secondary_points,
            },
            f,
            indent=4,
        )

    print("ROI.json updated successfully.")


# -------------------------------------------------
# Primary Mouse Callback
# -------------------------------------------------
def primary_callback(event, x, y, flags, param):

    global primary_points
    global primary_started

    if event == cv2.EVENT_LBUTTONDOWN:

        # First click = overwrite existing ROI
        if not primary_started:
            primary_points = []
            primary_started = True
            print("\nStarted drawing PRIMARY ROI")

        primary_points.append([x, y])

    elif event == cv2.EVENT_RBUTTONDOWN:

        if primary_started and len(primary_points) >= 3:

            save_rois()

            primary_started = False

            print("PRIMARY ROI saved.\n")


# -------------------------------------------------
# Secondary Mouse Callback
# -------------------------------------------------
def secondary_callback(event, x, y, flags, param):

    global secondary_points
    global secondary_started

    if event == cv2.EVENT_LBUTTONDOWN:

        if not secondary_started:
            secondary_points = []
            secondary_started = True
            print("\nStarted drawing SECONDARY ROI")

        secondary_points.append([x, y])

    elif event == cv2.EVENT_RBUTTONDOWN:

        if secondary_started and len(secondary_points) >= 3:

            save_rois()

            secondary_started = False

            print("SECONDARY ROI saved.\n")


# -------------------------------------------------
# Draw ROI while drawing only
# -------------------------------------------------
def draw_points(frame, points, drawing):

    if not drawing:
        return

    for pt in points:
        cv2.circle(frame, tuple(pt), 4, (0, 255, 0), -1)

    if len(points) >= 2:
        cv2.polylines(
            frame,
            [np.array(points, dtype=np.int32)],
            False,
            (0, 255, 0),
            2,
        )


# -------------------------------------------------
# MAIN
# -------------------------------------------------
def main():

    global running

    settings.reload()
    settings.require_connection_settings("CAMERA_URL")
    running = True

    load_existing_rois()

    # Enter the complete private camera RTSP URL in
    # config/settings.local.json; do not hardcode it in this file.
    cap = cv2.VideoCapture(settings.CAMERA_URL, cv2.CAP_FFMPEG)

    if not cap.isOpened():
        print("Cannot connect to RTSP stream.")
        return

    cv2.namedWindow("Select Primary ROI (Hopper)", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Select Secondary ROI (Flow Zone)", cv2.WINDOW_NORMAL)

    cv2.resizeWindow("Select Primary ROI (Hopper)", 900, 600)
    cv2.resizeWindow("Select Secondary ROI (Flow Zone)", 900, 600)

    cv2.setMouseCallback(
        "Select Primary ROI (Hopper)",
        primary_callback,
    )

    cv2.setMouseCallback(
        "Select Secondary ROI (Flow Zone)",
        secondary_callback,
    )

    print("\n===================================")
    print("ROI SELECTOR")
    print("===================================")
    print("Left Click  : Add vertex")
    print("Right Click : Save ROI")
    print("ESC         : Exit")
    print("===================================\n")

    while running:

        ret, frame = cap.read()

        # Sometimes RTSP skips one frame
        if not ret:
            continue

        primary_display = frame.copy()
        secondary_display = frame.copy()

        draw_points(
            primary_display,
            primary_points,
            primary_started,
        )

        draw_points(
            secondary_display,
            secondary_points,
            secondary_started,
        )

        cv2.imshow(
            "Select Primary ROI (Hopper)",
            primary_display,
        )

        cv2.imshow(
            "Select Secondary ROI (Flow Zone)",
            secondary_display,
        )

        cv2.moveWindow(
            "Select Primary ROI (Hopper)",
            50,
            80
        )

        cv2.moveWindow(
            "Select Secondary ROI (Flow Zone)",
            900,
            80
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
