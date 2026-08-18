import sys
import threading
import settings

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QSizePolicy,
)

from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtGui import QImage, QPixmap

import cv2

import video_player_3 as main
import roi_selector

def load_settings():
    settings.reload()
    return {
        "morning_threshold": settings.MORNING_THRESHOLD,
        "afternoon_threshold": settings.AFTERNOON_THRESHOLD,
        "night_threshold": settings.NIGHT_THRESHOLD,
        "primary_empty_percentage": settings.PRIMARY_EMPTY_PERCENTAGE,
        "secondary_empty_percentage": settings.SECONDARY_EMPTY_PERCENTAGE,
    }

# -----------------------------
# Dashboard Window
# -----------------------------
class Dashboard(QWidget):

    def __init__(self):

        super().__init__()
        self.settings = load_settings()
        self.setStyleSheet("""

        QWidget{
            background-color:#0A2342;
            color:white;
            font-size:18px;
        }

        QGroupBox{
            border:2px solid white;
            border-radius:8px;
            margin-top:12px;
            font-weight:bold;
            font-size:20px;
        }

        QGroupBox::title{
            subcontrol-origin: margin;
            left:15px;
            top:-2px;
            padding-left:8px;
            padding-right:8px;
            background:#0A2342;
        }
        QLineEdit{
            background:white;
            color:black;
            padding:6px;
            font-size:18px;
        }

        QPushButton{
            background:#FFD54F;
            color:black;
            font-size:18px;
            font-weight:bold;
            padding:10px;
            border-radius:8px;
        }

        QPushButton:hover{
            background:#FFE082;
        }

        """)

        self.setWindowTitle("Autobatching Console")
        self.initUI()

        self.showFullScreen()

        self.detection_thread = None
        self.roi_thread = None
        self.timer = QTimer()

        self.timer.timeout.connect(self.updateFrames)

        self.timer.start(30)

    # --------------------------------

    def initUI(self):

        mainLayout = QVBoxLayout()
        mainLayout.setSpacing(15)
        mainLayout.setContentsMargins(15,15,15,15)

        # ---------------- Title ----------------

        title = QLabel("AUTOBATCHING CONSOLE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size:40px;
            font-weight:bold;
            color:white;
            padding:10px;
        """)

        mainLayout.addWidget(title)
        mainLayout.addSpacing(15)

        # ---------------- Middle Area ----------------

        middleLayout = QHBoxLayout()
        middleLayout.setStretch(0,1)
        middleLayout.setStretch(1,1)
        middleLayout.setSpacing(15)

        # ==========================================
        # V CHANNEL
        # ==========================================

        self.vGroup = QGroupBox("V Channel")

        vLayout = QVBoxLayout()
        vLayout.setContentsMargins(10, 18, 10, 10)
        vLayout.setSpacing(12)

        self.vLabel = QLabel()
        self.vLabel.setText("Waiting for Video...")

        self.vLabel.setFixedSize(900, 500)

        self.vLabel.setStyleSheet("""
            background:black;
            border:2px solid gray;
        """)

        self.vLabel.setAlignment(Qt.AlignCenter)

        vLayout.addWidget(self.vLabel)

        self.vGroup.setLayout(vLayout)

        # ==========================================
        # MATERIAL MASK
        # ==========================================

        self.maskGroup = QGroupBox("Material Mask")

        maskLayout = QVBoxLayout()
        maskLayout.setContentsMargins(10, 18, 10, 10)
        maskLayout.setSpacing(12)

        self.maskLabel = QLabel()
        self.maskLabel.setText("Waiting for Mask...")

        self.maskLabel.setMinimumHeight(500)

        self.maskLabel.setFixedSize(900, 500)

        self.maskLabel.setStyleSheet("""
            background:black;
            border:2px solid gray;
        """)

        self.maskLabel.setAlignment(Qt.AlignCenter)

        maskLayout.addWidget(self.maskLabel)

        self.maskGroup.setLayout(maskLayout)

        # ==========================================
        # CONTROLS
        # ==========================================

        self.controlGroup = QGroupBox("Controls")

        controlLayout = QGridLayout()
        controlLayout.setContentsMargins(15, 20, 15, 15)
        controlLayout.setHorizontalSpacing(20)
        controlLayout.setVerticalSpacing(18)
        self.startButton = QPushButton("START")
        self.stopButton = QPushButton("STOP")
        self.roiButton = QPushButton("ROI SELECTOR")
        self.applyButton = QPushButton("APPLY SETTINGS")
        self.exitButton = QPushButton("EXIT")
        buttons = [
            self.startButton,
            self.stopButton,
            self.roiButton,
            self.applyButton,
            self.exitButton
        ]

        for b in buttons:
            b.setFixedHeight(70)
            b.setMinimumWidth(120)

        controlLayout.addWidget(self.startButton, 0, 0)

        controlLayout.addWidget(self.stopButton, 0, 1)

        controlLayout.addWidget(self.roiButton, 0, 2)

        controlLayout.addWidget(self.applyButton, 0, 3)

        controlLayout.addWidget(self.exitButton, 0, 4)

        self.morningLabel = QLabel("Morning/Evening Threshold")

        self.afternoonLabel = QLabel("Afternoon Threshold")

        self.nightLabel = QLabel("Night Threshold")

        self.primaryEmptyLabel = QLabel("Primary Empty %")

        self.secondaryEmptyLabel = QLabel("Secondary Empty %")

        self.morningBox = QLineEdit(
            str(self.settings["morning_threshold"])
        )

        self.afternoonBox = QLineEdit(
            str(self.settings["afternoon_threshold"])
        )

        self.nightBox = QLineEdit(
            str(self.settings["night_threshold"])
        )

        self.primaryEmptyBox = QLineEdit(
            str(self.settings["primary_empty_percentage"])
        )

        self.secondaryEmptyBox = QLineEdit(
            str(self.settings["secondary_empty_percentage"])
        )

        boxes = [
            self.morningBox,
            self.afternoonBox,
            self.nightBox,
            self.primaryEmptyBox,
            self.secondaryEmptyBox
        ]

        for box in boxes:
            box.setFixedWidth(110)
            box.setFixedHeight(45)

        # Column 1
        controlLayout.addWidget(self.morningLabel, 1, 0)
        controlLayout.addWidget(self.morningBox,   1, 1)

        controlLayout.addWidget(self.afternoonLabel, 2, 0)
        controlLayout.addWidget(self.afternoonBox,   2, 1)

        # Column 2
        controlLayout.addWidget(self.nightLabel, 1, 2)
        controlLayout.addWidget(self.nightBox, 1, 3)

        # Column 3
        controlLayout.addWidget(self.primaryEmptyLabel, 1, 4)
        controlLayout.addWidget(self.primaryEmptyBox,   1, 5)

        controlLayout.addWidget(self.secondaryEmptyLabel, 2, 4)
        controlLayout.addWidget(self.secondaryEmptyBox,   2, 5)

        self.controlGroup.setLayout(controlLayout)

        # ---------------- Add Panels ----------------

        middleLayout.addWidget(self.vGroup,1)

        middleLayout.addWidget(self.maskGroup,1)

        mainLayout.addLayout(middleLayout, 4)

        mainLayout.addWidget(self.controlGroup, 1)
        self.setLayout(mainLayout)

        # ---------------- Connections ----------------

        self.startButton.clicked.connect(
            self.startDetection
        )

        self.stopButton.clicked.connect(
            self.stopDetection
        )

        self.roiButton.clicked.connect(
            self.startROISelector
        )

        self.applyButton.clicked.connect(
            self.applySettings
        )

        self.exitButton.clicked.connect(
            self.close
        )
    # --------------------------------

    def log(self, text):
        pass

    # --------------------------------

    def startDetection(self):

        if self.detection_thread is None or not self.detection_thread.is_alive():

            self.log("Starting Detection...")

            self.detection_thread = threading.Thread(
                target=self.runDetection,
                daemon=True
            )

            self.detection_thread.start()

        else:

            self.log("Detection already running.")

    def runDetection(self):
        try:
            main.main()
        except Exception as error:
            main.running = False
            print(f"Detection stopped: {error}")
        finally:
            main.shutdown_resources()

    # --------------------------------

    def stopDetection(self):

        self.log("Stopping Detection...")
        main.request_stop()

        if self.detection_thread is not None:
            self.detection_thread.join(timeout=2)

            if self.detection_thread.is_alive():
                print(
                    "Detection is still shutting down. "
                    "START remains blocked until it has stopped."
                )
                return

        self.detection_thread = None

    # --------------------------------

    def startROISelector(self):

        if self.roi_thread is None or not self.roi_thread.is_alive():

            self.log("Opening ROI Selector...")

            self.roi_thread = threading.Thread(
                target=roi_selector.main,
                daemon=True
            )

            self.roi_thread.start()

        else:

            self.log("ROI Selector already running.")

    # --------------------------------

    def stopROISelector(self):

        self.log("Stopping ROI Selector...")

        roi_selector.running = False

        if self.roi_thread is not None:
            self.roi_thread.join(timeout=2)

            if self.roi_thread.is_alive():
                print(
                    "ROI selector is still shutting down. "
                    "A second selector will not be started."
                )
                return

        self.roi_thread = None

    def closeEvent(self, event):
        """Request clean worker shutdown before closing the dashboard."""
        self.stopDetection()
        self.stopROISelector()
        event.accept()

    def applySettings(self):

        try:

            settings.save_thresholds(
                morning_threshold=int(self.morningBox.text()),
                afternoon_threshold=int(self.afternoonBox.text()),
                night_threshold=int(self.nightBox.text()),
                primary_empty_percentage=float(self.primaryEmptyBox.text()),
                secondary_empty_percentage=float(self.secondaryEmptyBox.text()),
            )

            print("Settings Updated")

        except ValueError:

            print("Invalid Settings")
    def updateFrames(self):
        #print(main.CURRENT_V_FRAME)
        if main.CURRENT_V_FRAME is not None:

            frame = main.CURRENT_V_FRAME

            if len(frame.shape) == 2:
                h, w = frame.shape
                bytesPerLine = w
                img = QImage(
                    frame.data,
                    w,
                    h,
                    bytesPerLine,
                    QImage.Format_Grayscale8,
                )

            else:

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytesPerLine = ch * w
                img = QImage(
                    rgb.data,
                    w,
                    h,
                    bytesPerLine,
                    QImage.Format_RGB888,
                )

            pix = QPixmap.fromImage(img)

            self.vLabel.setPixmap(
                pix.scaled(
                    self.vLabel.size(),
                    Qt.KeepAspectRatio,
                )
            )

        # ==========================================
        # Material Mask
        # ==========================================

        if main.CURRENT_MASK_FRAME is not None:

            mask = main.CURRENT_MASK_FRAME
            rgb = cv2.cvtColor(mask, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytesPerLine = ch * w
            img = QImage(
                rgb.data,
                w,
                h,
                bytesPerLine,
                QImage.Format_RGB888,
            )

            pix = QPixmap.fromImage(img)
            self.maskLabel.setPixmap(
                pix.scaled(
                    self.maskLabel.size(),
                    Qt.KeepAspectRatio,
                )
            )

def run_dashboard():
    app = QApplication(sys.argv)
    window = Dashboard()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(run_dashboard())
