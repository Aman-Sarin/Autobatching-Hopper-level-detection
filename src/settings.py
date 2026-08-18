"""Shared configuration for the hopper monitoring applications.

Safe, non-secret thresholds are loaded from ``config/settings.json``.
Camera and PLC connection values are loaded from the optional, Git-ignored
``config/settings.local.json`` or from environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

ROI_FILE = CONFIG_DIR / "roi.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LOCAL_SETTINGS_FILE = CONFIG_DIR / "settings.local.json"
SNAPSHOT_DIR = DATA_DIR / "snapshot"
MASK_DIR = DATA_DIR / "Material_Mask"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def _connection_value(
    local_settings: dict[str, Any],
    key: str,
    environment_name: str,
) -> str:
    return os.getenv(environment_name, str(local_settings.get(key, ""))).strip()


def reload() -> None:
    """Reload configuration values from disk and environment variables."""
    global MORNING_THRESHOLD
    global AFTERNOON_THRESHOLD
    global NIGHT_THRESHOLD
    global PRIMARY_EMPTY_PERCENTAGE
    global SECONDARY_EMPTY_PERCENTAGE
    global CAMERA_URL
    global PLC_IP
    global GATE_CLOSED_TAG
    global CAMERA_TRIGGER_TAG

    public_settings = _load_json(SETTINGS_FILE)
    local_settings = _load_json(LOCAL_SETTINGS_FILE)

    MORNING_THRESHOLD = int(public_settings.get("morning_threshold", 92))
    AFTERNOON_THRESHOLD = int(public_settings.get("afternoon_threshold", 98))
    NIGHT_THRESHOLD = int(public_settings.get("night_threshold", 90))
    PRIMARY_EMPTY_PERCENTAGE = float(
        public_settings.get("primary_empty_percentage", 18.0)
    )
    SECONDARY_EMPTY_PERCENTAGE = float(
        public_settings.get("secondary_empty_percentage", 60.0)
    )

    # PRIVATE SETUP: copy config/settings.local.example.json to
    # config/settings.local.json and replace every PLEASE_ENTER_* placeholder.
    # Do not place real camera or PLC connection values in this source file.
    CAMERA_URL = _connection_value(
        local_settings, "camera_url", "HOPPER_CAMERA_URL"
    )

    # Enter the Logix-compatible PLC IP address in the private local file.
    PLC_IP = _connection_value(local_settings, "plc_ip", "HOPPER_PLC_IP")

    # Enter the mixer-gate CLOSED feedback tag. Its tested meaning is:
    # 1 = gate CLOSED, 0 = gate OPEN.
    GATE_CLOSED_TAG = _connection_value(
        local_settings, "gate_closed_tag", "HOPPER_GATE_CLOSED_TAG"
    )

    # Enter the Boolean PLC request tag that Python may switch ON and OFF.
    CAMERA_TRIGGER_TAG = _connection_value(
        local_settings, "camera_trigger_tag", "HOPPER_CAMERA_TRIGGER_TAG"
    )


def save_thresholds(
    morning_threshold: int,
    afternoon_threshold: int,
    night_threshold: int,
    primary_empty_percentage: float,
    secondary_empty_percentage: float,
) -> None:
    """Persist dashboard-editable thresholds and refresh module values."""
    values = {
        "morning_threshold": int(morning_threshold),
        "afternoon_threshold": int(afternoon_threshold),
        "night_threshold": int(night_threshold),
        "primary_empty_percentage": float(primary_empty_percentage),
        "secondary_empty_percentage": float(secondary_empty_percentage),
    }

    for name in (
        "morning_threshold",
        "afternoon_threshold",
        "night_threshold",
    ):
        if not 0 <= values[name] <= 255:
            raise ValueError(f"{name} must be between 0 and 255")

    for name in (
        "primary_empty_percentage",
        "secondary_empty_percentage",
    ):
        if not 0.0 <= values[name] <= 100.0:
            raise ValueError(f"{name} must be between 0 and 100")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary_file = SETTINGS_FILE.with_name(f"{SETTINGS_FILE.name}.tmp")

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(values, file, indent=4)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_file, SETTINGS_FILE)
    finally:
        temporary_file.unlink(missing_ok=True)

    reload()


def require_connection_settings(*names: str) -> None:
    """Raise a clear error when required plant settings are missing."""
    missing = [name for name in names if not globals().get(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Missing connection settings: "
            f"{joined}. Copy config/settings.local.example.json to "
            "config/settings.local.json and replace the placeholder values."
        )


reload()
