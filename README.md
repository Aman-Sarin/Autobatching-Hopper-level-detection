# Industrial Hopper Empty Detection and Autobatching

## Overview

This project uses computer vision to determine when a production hopper in
a Mixer batching system is sufficiently empty for the next batch to be released.
It was developed for a real industrial process where uneven material flow,
changing illumination, and material stuck to hopper walls made conventional
level sensor based automation unreliable.

The production solution combines:

- HSV V-channel material segmentation
- Material estimation in two separate ROIs
- Persistence-based removal of detached wall material
- Time-confirmed visual empty detection
- A state machine incorporating visual empty, PLC trigger, and Mixer gate feedback
- A full-screen operator dashboard for scalability
- Runtime-editable thresholds and automatic ROI reloading
- Camera reconnection, snapshots, and hourly diagnostic overlays

The system is a major breakthrough in soap/lumpy material batch operations
enabling autonomous functioning and removing manual dependency. It helps in
preventing premature batch dumping, which contributes to abnormalities like
hopper bridging, as well as batch delays leading to speed loss on packing lines.

## Python technologies used

- **Python 3.10.11:** coordinates the computer-vision, control, configuration,
  timing, logging, and operator-interface components.
- **OpenCV (`cv2`):** captures the camera stream, converts frames to HSV,
  creates and cleans binary masks, analyses connected components, draws live
  overlays, and saves diagnostic images.
- **NumPy:** performs pixel-array operations, ROI masking, and material
  percentage calculations.
- **PyQt5:** provides the full-screen operator dashboard, live image panels,
  controls, timers, and editable threshold fields.
- **pycomm3 (`LogixDriver`):** reads mixer-gate feedback and exchanges the
  empty-trigger signal with a Logix-compatible PLC.
- **Threading:** runs the vision and PLC process in the background so that the
  dashboard remains responsive.
- **JSON, pathlib, and os:** store settings and ROI coordinates, build portable
  project paths, and load private connection values safely.
- **time and datetime:** manage confirmation periods, state delays, timestamps,
  and time-of-day brightness-threshold selection.
- **unittest:** runs offline smoke tests for configuration, image processing,
  threshold validation, and PLC safety guards.

## Main programs

### `src/video_player_3.py`

The ready-to-use integrated industrial version. It performs vision detection,
writes the empty trigger to the PLC, monitors mixer-gate feedback, saves
diagnostic images, and supplies live frames and state to the dashboard.

Before using it at another installation, replace the local camera/PLC settings
and PLC tags. Never test PLC writes on live equipment until the controls owner
has reviewed the configured addresses and sequence.

### `src/hopper_empty_final.py`

The standalone vision implementation. It contains the final dual-ROI hopper
empty logic without PLC control or the dashboard. Use it to understand,
demonstrate, or tune the computer-vision method independently.

### `src/dashboard.py` and `src/settings.py`

The operator-facing application and shared configuration layer. Together they
provide live visualization, start/stop controls, ROI selection, validated
threshold editing, persistent settings, portable project paths, and separation
of public settings from private plant connection values.

## Repository structure

```text
Autobatching-Hopper-level-detection/
|
|-- config/
|   |-- roi.json                         # Primary and secondary ROI coordinates
|   |-- settings.json                    # Safe, editable vision thresholds
|   `-- settings.local.example.json      # Camera/PLC configuration template
|
|-- docs/
|   |-- approach_evolution.md
|   `-- images/
|
|-- src/
|   |-- dashboard.py                     # Recommended operator entry point
|   |-- hopper_empty_final.py            # Standalone vision logic
|   |-- video_player_3.py                # Integrated vision + PLC application
|   |-- settings.py                      # Shared paths and configuration
|   |-- roi_selector.py                  # Live primary/secondary ROI editor
|   |-- utils.py                         # Shared vision helpers
|   |-- video_player.py                  # Original development baseline
|   |-- video_player_2.py                # Persistence-development version
|   |-- roi_masker.py                    # ROI experiment
|   `-- utils_old.py                     # Compatibility helpers for old scripts
|
|-- requirements.txt
|-- .gitignore
`-- README.md
```

The `data/` folder contains local videos and generated images and is excluded
from Git. Python virtual environments and private plant settings are also
excluded.

## Windows setup

The validated development version is Python 3.10.11 (64-bit).

```powershell
git clone https://github.com/Aman-Sarin/Autobatching-Hopper-level-detection.git
cd Autobatching-Hopper-level-detection

python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

In Visual Studio Code, install the Microsoft Python extension and select
`.venv\Scripts\python.exe` using **Python: Select Interpreter**.

## Configure the plant connection

Copy the safe template to a local file:

```powershell
Copy-Item config\settings.local.example.json config\settings.local.json
```

Edit `config/settings.local.json` and replace all placeholders:

```json
{
    "_instructions": {
        "camera_url": "Enter the complete private camera RTSP URL.",
        "plc_ip": "Enter the Logix-compatible PLC IP address.",
        "gate_closed_tag": "Enter the gate CLOSED feedback tag: 1=CLOSED, 0=OPEN.",
        "camera_trigger_tag": "Enter the Boolean Python-to-PLC request tag."
    },
    "camera_url": "rtsp://PLEASE_ENTER_CAMERA_USERNAME:PLEASE_ENTER_CAMERA_PASSWORD@PLEASE_ENTER_CAMERA_IP_ADDRESS:554/Streaming/Channels/101",
    "plc_ip": "PLEASE_ENTER_PLC_IP_ADDRESS",
    "gate_closed_tag": "PLEASE_ENTER_MIXER_GATE_CLOSED_FEEDBACK_TAG",
    "camera_trigger_tag": "PLEASE_ENTER_PYTHON_TO_PLC_TRIGGER_TAG"
}
```

`settings.local.json` is ignored by Git. Connection values
can alternatively be supplied with these environment variables:

- `HOPPER_CAMERA_URL`
- `HOPPER_PLC_IP`
- `HOPPER_GATE_CLOSED_TAG`
- `HOPPER_CAMERA_TRIGGER_TAG`

Safe detection thresholds are stored separately in `config/settings.json` and
can be changed through the dashboard.

## Configure the ROIs

Run the ROI selector directly:

```powershell
python src\roi_selector.py
```

Alternatively, select **ROI SELECTOR** from the dashboard. Use left-click to
add polygon vertices and right-click to save each ROI. The primary ROI covers
the hopper material area; the secondary ROI covers the discharge-flow zone.
The saved coordinates are reloaded automatically by the integrated detector.

## Run the applications

Recommended operator interface:

```powershell
python src\dashboard.py
```

Standalone vision logic without PLC control:

```powershell
python src\hopper_empty_final.py
```

Integrated industrial logic without the dashboard:

```powershell
python src\video_player_3.py
```

The integrated application can write to the configured PLC trigger tag. Only
run it when the connection file has been reviewed for the intended equipment.

Original percentage-only development baseline:

```powershell
python src\video_player.py
```

This earlier script measures the primary ROI without persistence-based
stuck-material subtraction. For the reasoning behind this and later iterations,
see [Approach Evolution](docs/approach_evolution.md).

## Run offline smoke tests

The smoke tests validate configuration paths, ROI loading, mask processing,
threshold validation, and the missing-PLC safety guard without contacting plant
equipment:

```powershell
python -m unittest discover -s tests -v
```

## Detection and PLC sequence

1. Segment material in the primary and secondary ROIs.
2. Subtract persistent detached material from the primary material percentage.
3. Confirm an empty condition for the configured duration.
4. Write the camera empty trigger when the mixer gate is closed.
5. Wait for gate-open feedback.
6. Reset the PLC trigger after the configured delay.
7. Wait for the gate to close and material level to recover before rearming.

Camera loss is handled by repeated reconnection attempts while the PLC request
is inactive. If a confirmed camera failure occurs while the request is active,
the application attempts to write the request OFF, enters `FAULT`, and stops
that detector run. Stop, Exit, and unexpected-error paths also attempt an OFF
write before closing the PLC connection. PLC reads and writes are validated and
stop with an explicit error if communication fails; automatic PLC reconnection
is not currently implemented.

## Technical approach

For the full R&D history—including grayscale evaluation, HSV selection,
connected-component experiments, and persistence-based stuck-material subtraction,
and the logic behind state machine—see [Approach Evolution](docs/approach_evolution.md).

## Deployment and safety notes

- Create `config/settings.local.json` from the supplied example and keep the
  completed local file private.
- Replace every camera, PLC, and tag placeholder with values reviewed for the
  intended installation.
- Confirm the mixer-gate feedback meaning and PLC trigger sequence with the
  plant controls owner before enabling writes.
- Test camera detection and PLC behaviour under controlled conditions before
  enabling automatic production operation.
- Never publish camera credentials, plant network addresses, or operational PLC
  tag names.

## Author

**Aman Sarin**<br>
Assistant Manager – Supply Chain (Industrial Digital Transformation)<br>
Electronics & Instrumentation Engineer, NIT Rourkela<br>

GitHub: [Aman-Sarin](https://github.com/Aman-Sarin)<br>
Interests: Computer Vision, Industrial Automation
