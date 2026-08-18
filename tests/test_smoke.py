import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import dashboard  # noqa: E402
import hopper_empty_final  # noqa: E402
import settings  # noqa: E402
import utils  # noqa: E402
import video_player_3  # noqa: E402


class ConfigurationTests(unittest.TestCase):
    def test_project_paths_are_absolute(self):
        self.assertTrue(settings.PROJECT_ROOT.is_absolute())
        self.assertEqual(settings.PROJECT_ROOT, PROJECT_ROOT)
        self.assertTrue(settings.ROI_FILE.exists())
        self.assertTrue(settings.SETTINGS_FILE.exists())

    def test_invalid_threshold_is_rejected_before_saving(self):
        with self.assertRaises(ValueError):
            settings.save_thresholds(-1, 98, 90, 18, 60)

    def test_missing_plc_connection_is_rejected(self):
        original_plc = video_player_3.plc
        video_player_3.plc = None
        try:
            with self.assertRaises(RuntimeError):
                video_player_3.read_gate_open()
        finally:
            video_player_3.plc = original_plc

    def test_settings_are_replaced_atomically(self):
        original_config_dir = settings.CONFIG_DIR
        original_settings_file = settings.SETTINGS_FILE
        original_local_settings_file = settings.LOCAL_SETTINGS_FILE

        try:
            with tempfile.TemporaryDirectory() as directory:
                temporary_dir = Path(directory)
                settings.CONFIG_DIR = temporary_dir
                settings.SETTINGS_FILE = temporary_dir / "settings.json"
                settings.LOCAL_SETTINGS_FILE = temporary_dir / "settings.local.json"

                settings.save_thresholds(92, 98, 90, 18, 60)

                saved = json.loads(settings.SETTINGS_FILE.read_text("utf-8"))
                self.assertEqual(saved["primary_empty_percentage"], 18.0)
                self.assertFalse(
                    settings.SETTINGS_FILE.with_name("settings.json.tmp").exists()
                )
        finally:
            settings.CONFIG_DIR = original_config_dir
            settings.SETTINGS_FILE = original_settings_file
            settings.LOCAL_SETTINGS_FILE = original_local_settings_file
            settings.reload()


class TriggerSafetyTests(unittest.TestCase):
    class SuccessfulResult:
        value = False
        error = None

        def __bool__(self):
            return True

    class FakePLC:
        def __init__(self):
            self.writes = []

        def write(self, tag, value):
            self.writes.append((tag, value))
            return TriggerSafetyTests.SuccessfulResult()

    def setUp(self):
        self.original_plc = video_player_3.plc
        self.original_running = video_player_3.running
        self.original_tag = settings.CAMERA_TRIGGER_TAG

    def tearDown(self):
        video_player_3.plc = self.original_plc
        video_player_3.running = self.original_running
        settings.CAMERA_TRIGGER_TAG = self.original_tag

    def test_force_trigger_off_writes_false(self):
        fake_plc = self.FakePLC()
        video_player_3.plc = fake_plc
        video_player_3.CURRENT_TRIGGER = True
        settings.CAMERA_TRIGGER_TAG = "TEST_TRIGGER"

        self.assertTrue(video_player_3.force_trigger_off())
        self.assertEqual(fake_plc.writes, [("TEST_TRIGGER", False)])
        self.assertFalse(video_player_3.CURRENT_TRIGGER)

    def test_trigger_on_is_blocked_after_stop_request(self):
        fake_plc = self.FakePLC()
        video_player_3.plc = fake_plc
        video_player_3.running = False
        settings.CAMERA_TRIGGER_TAG = "TEST_TRIGGER"

        with self.assertRaises(RuntimeError):
            video_player_3.write_camera_trigger(True)

        self.assertEqual(fake_plc.writes, [])


class DashboardWorkerTests(unittest.TestCase):
    class StillRunningWorker:
        def join(self, timeout=None):
            self.timeout = timeout

        def is_alive(self):
            return True

    def test_live_detection_worker_reference_is_retained(self):
        worker = self.StillRunningWorker()

        class DashboardStub:
            detection_thread = worker

            @staticmethod
            def log(_message):
                pass

        dashboard_stub = DashboardStub()
        original_request_stop = dashboard.main.request_stop
        try:
            dashboard.main.request_stop = lambda: None
            dashboard.Dashboard.stopDetection(dashboard_stub)
        finally:
            dashboard.main.request_stop = original_request_stop

        self.assertIs(dashboard_stub.detection_thread, worker)


class VisionParameterTests(unittest.TestCase):
    def test_standalone_vision_parameters_match_integrated_version(self):
        self.assertEqual(
            hopper_empty_final.TIME_CONFIRM_SECONDS,
            video_player_3.TIME_CONFIRM_SECONDS,
        )
        self.assertEqual(
            hopper_empty_final.SECONDARY_CONFIRM_SECONDS,
            video_player_3.SECONDARY_CONFIRM_SECONDS,
        )
        self.assertEqual(
            hopper_empty_final.PERSISTENCE_TIME_SECONDS,
            video_player_3.PERSISTENCE_TIME_SECONDS,
        )
        self.assertEqual(
            hopper_empty_final.MIN_STUCK_AREA,
            video_player_3.MIN_STUCK_AREA,
        )
        self.assertEqual(
            hopper_empty_final.VISION_RESET_PERCENTAGE,
            video_player_3.VISION_RESET_PERCENTAGE,
        )
        self.assertEqual(
            hopper_empty_final.VISION_RESET_SECONDS,
            video_player_3.VISION_RESET_SECONDS,
        )


class VisionUtilityTests(unittest.TestCase):
    def test_rois_and_mask_pipeline(self):
        primary_roi, secondary_roi = utils.load_rois()
        self.assertGreaterEqual(len(primary_roi), 3)
        self.assertGreaterEqual(len(secondary_roi), 3)

        max_x = int(max(primary_roi[:, 0].max(), secondary_roi[:, 0].max()))
        max_y = int(max(primary_roi[:, 1].max(), secondary_roi[:, 1].max()))
        frame = np.zeros((max_y + 10, max_x + 10, 3), dtype=np.uint8)
        cv2.fillPoly(frame, [primary_roi], (255, 255, 255))

        roi, roi_mask = utils.apply_roi_mask(frame, primary_roi)
        v_channel = utils.extract_v_channel(roi)
        material_mask = utils.clean_mask(
            utils.threshold_material(v_channel, settings.MORNING_THRESHOLD)
        )

        self.assertEqual(material_mask.shape, frame.shape[:2])
        self.assertGreater(cv2.countNonZero(roi_mask), 0)
        self.assertGreater(utils.white_pixel_percentage(material_mask, roi_mask), 0)


if __name__ == "__main__":
    unittest.main()
