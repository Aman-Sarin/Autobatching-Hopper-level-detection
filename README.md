# Autobatching using Computer Vision

## Overview

This project implements a **computer vision based hopper empty detection system** for an industrial batch manufacturing process.  
The objective is to reliably detect when a hopper is sufficiently empty so that the next batch can be dumped automatically from an upstream mixer.
This automation will help with timely dumping of new batch eliminating batch delay as well as prevent premature dumping of batch leading to abnormalities like hopper bridging. 

The solution is designed for **real world plant deployment**, using footage from an existing fixed camera and integrating cleanly with PLC-based control systems.

---

## Need for Computer Vision and challenges

The auto dumping was initially tested with level sensors but failed to stabilize. In computer vision as well, multiple iterations of logic was required due to the following real world challenges of implementing such a system:

- Non uniform material flow and uneven emtying of hopper
- Variations in material consistency across batches
- Material sticking to hopper side walls
- Lighting changes and camera framing variations

<img src="docs/images/ROI_selection.png" alt="ROI selection" width="550">

---

## Final Solution Summary

The final solution uses a **coverage of thresholded material with persistence based elimination approach**:

- A fixed polygonal **Region of Interest (ROI)** selected by the user to focus on the lower section of the hopper
- Material is segmented using the **HSV V-channel**, ensuring lighting robustness
- Morphological cleanup suppresses noise
- Binary Thresholding is done to clearly bifurcate between material and hopper walls
- The **largest connected component** is treated as flowing material
- **Persistent detached material** (stuck to walls) is automatically identified and subtracted from total white pixels count
- Hopper empty is declared only when effective white pixels percentage falls below a threshold for a defined duration

<img src="docs/images/Successful_implementation.png" alt="Final Result" width="850">

Before finalizing the persistence-based subtraction of material, several other techniques were evaluated.  
For a detailed discussion of the technical reasoning and discarded approaches, refer to:
📄 **[Approach Evolution](docs/approach_evolution.md)**.

---

## Key Features

- Robust to camera framing and ROI changes
- Stable across day/night lighting conditions and various material colours
- Handles residual wall stuck material automatically
- Time confirmed empty detection to prevent false triggers
- Designed for PLC integration in batch processes

---

## Repository Structure

```text
Autobatching-Hopper-level-detection/
│
├── src/                       # Core source code
│   ├── video_player_2.py      # Main CV pipeline for hopper empty detection
│   ├── roi_selector.py        # Interactive ROI selection utility
│   └── utils.py               # Shared helper functions (masking, thresholding, etc.)
│
├── config/                    # Configuration and calibration files
│   └── roi_points.json        # Saved ROI polygon coordinates
│
├── data/                      # Sample videos for offline testing and validation and some video editing files
│   └── mixer 01 131125/       # (Not tracked / optional)
│
├── docs/                      # Documentation and design notes
│   ├── approach_evolution.md  # Step-by-step R&D evolution and design decisions
│   └── images/                # Screenshots used in documentation
│
├── requirements.txt           # Python dependencies
├── README.md                  # Project overview and usage instructions
└── .gitignore                 # Git ignore rules
```

## How to Run

### 1. Clone the repository
```bash
git clone https://github.com/Aman-Sarin/Autobatching-Hopper-level-detection.git
cd Autobatching-Hopper-level-detection
```
### 2. Create and activate a virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate
```
### 3. Install dependencies
```bash
pip install -r requirements.txt
```
### 4. Configure the Region of Interest
Left mouse click to select the points and right click to finalize the ROI coordinates, which are saved in
```bash
config/roi_points.json
```
This step is required only once unless camera position is changed
### 5. Run the hopper empty detection pipeline
```bash
python src/video_player_2.py
```
During execution:
- The V channel and material mask windows are displayed
- The system computes total material percentage and subtracted (stuck) material
- **HOPPER EMPTY** is triggered once the effective material falls below the configured threshold for the defined time window

(**IMP**) - If you wish to run only the white pixels percentage count logic without the stuck blobs being subtracted, then run:
```bash
python src/video_player.py
```
For the detailed understanding of past iterations, it is better to go through the project details in **[Approach Evolution](docs/approach_evolution.md)**
### 6. Integration with PLC for production deployment
In production:
- The HOPPER EMPTY condition is intended to trigger a PLC command to open the mixer gate
- A gate-open feedback signal can be used to reset the system for the next batch after a configurable delay

**NOTE**
Thresholds and persistence parameters can be tuned in 
```py
video_player_2.py
```
The system has been validated across multiple batches and camera framing variations and the variables have been tuned accordingly

## Future Work
Extension to Hopper bridging detection wherein if the main material (biggest connected component) does not move with time while Noodler (the equipment that the hopper emties into) is running, then a case of bridging will be identified and notified to the user.

---

## Author

**Aman Sarin**  
Assistant Manager – Supply Chain (Industrial Digital Transformation)  
Electronics & Instrumentation Engineer, NIT Rourkela  

GitHub: https://github.com/Aman-Sarin  
Interests: Computer Vision, Industrial Automation






