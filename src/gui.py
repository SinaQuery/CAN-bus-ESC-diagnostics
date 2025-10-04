# ============================================================
# File: gui.py
# Author: Sina Jahanbakhsh
# Description:
#   Graphical User Interface for HES-ESC Diagnostic Tester.
#   Provides actuator control, live signal monitoring with graphs,
#   DTC read/clear operations, and calibration routines.
#
#   رابط گرافیکی کاربر برای تستر عیب‌یاب ESC-HES.
#   شامل کنترل عملگرها، پایش زنده‌ی سیگنال‌ها با نمودار،
#   خواندن و پاک کردن خطاها (DTC) و انجام کالیبراسیون‌ها.
# ============================================================

import sys
import time
from PyQt5 import uic, QtGui
from PyQt5.QtGui import QFont, QColor, QBrush
from PyQt5.QtWidgets import (
    QApplication, QWidget, QTableWidgetItem,
    QHeaderView, QLabel, QVBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from uds_client import UDSClient
from actuators import ACTUATORS
import pyqtgraph as pg
from collections import deque

# CAN interface used for communication with the ECU (ای‌سی‌یو)
CAN_INTERFACE = "can0"


# ============================================================
# Worker Thread: Periodically Reads ECU Signals
# نخ کارگر برای خواندن مداوم داده‌های ای‌سی‌یو
# ============================================================
class MonitorWorker(QThread):
    data_signal = pyqtSignal(dict)

    def __init__(self, channel=CAN_INTERFACE, delay=0.5):
        super().__init__()
        self.channel = channel
        self.delay = delay
        self.running = True

    def run(self):
        """Main thread loop — reads data periodically."""
        uds = UDSClient(channel=self.channel)
        try:
            if not uds.enter_extended_session() or not uds.security_access():
                self.data_signal.emit({"error": "Failed to unlock ECU"})
                return

            # List of Data Identifiers (DIDs) to read
            dids = [
                0xF186, 0xF187, 0xF18A, 0xF18B,
                0xF190, 0xF195, 0xF1A4,
                0xFD00, 0xFD01, 0xFD02,
                0xFD03, 0xFD04, 0xFD05,
                0xFD06,
            ]

            while self.running:
                data = {}
                for did in dids:
                    val = uds.read_data_by_identifier(did)
                    decoded = uds.decode_value(did, val) if val is not None else None
                    if decoded is not None:
                        name = {
                            0xF186: "Diagnostic Session",
                            0xF187: "Spare Part Number",
                            0xF18A: "System Supplier ID",
                            0xF18B: "Manufacturing Date",
                            0xF190: "VIN",
                            0xF195: "Software Version",
                            0xF1A4: "Hardware Version",
                            0xFD00: "Wheel Speeds + Vehicle Speed",
                            0xFD01: "Input Data",
                            0xFD02: "Actuation State",
                            0xFD03: "Filling-in Status",
                            0xFD04: "EOL Status",
                            0xFD05: "System Sensors",
                            0xFD06: "Variant Code",
                        }[did]
                        data[name] = decoded

                self.data_signal.emit(data)
                uds.tester_present()  # keep session alive
                time.sleep(self.delay)
        finally:
            uds.shutdown()

    def stop(self):
        """Stop the monitoring thread."""
        self.running = False
        self.wait()


# ============================================================
# Main GUI Class
# کلاس اصلی رابط کاربر گرافیکی
# ============================================================
class DiagnosticGUI(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("./ui/HES_gui.ui", self)

        # ---------- Basic UI Setup ----------
        self.setWindowIcon(QtGui.QIcon("./assets/logo.png"))

        # Populate actuator dropdown
        self.actuator_select.clear()
        for name, aid in ACTUATORS.items():
            self.actuator_select.addItem(name, aid)

        # Stretch actuator table columns
        self.actuator_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Connect buttons to functions
        self.btn_activate.clicked.connect(self.run_actuator_on)
        self.btn_run_all.clicked.connect(self.run_all_actuators)
        self.btn_start_monitoring.clicked.connect(self.start_monitoring)
        self.btn_stop_monitoring.clicked.connect(self.stop_monitoring)

        # Calibration button connections (if exist in UI)
        try:
            self.btn_start_sas_cal.clicked.connect(
                lambda: self._run_calibration_routine("SAS Calibration (F105)", "start_sas_calibration"))
            self.btn_start_yaw_cal.clicked.connect(
                lambda: self._run_calibration_routine("Yaw Rate Calibration (F106)", "start_yaw_calibration"))
        except AttributeError:
            pass  # UI may not have calibration buttons

        # DTC buttons
        self.btn_read_dtcs.clicked.connect(self.read_dtcs)
        self.btn_clear_dtcs.clicked.connect(self.clear_dtcs)

        # Initialize GUI components
        self.init_actuator_table()
        self.init_monitor_table()
        self.init_graphs()

        # Configure DTC table columns
        self.dtc_table.setColumnCount(4)
        self.dtc_table.setHorizontalHeaderLabels(["Code", "Description", "Status", "Severity"])
        self.dtc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Add About tab
        self.add_about_tab()

        # State variables
        self.monitor_thread = None
        self.monitor_data = {}

    # ============================================================
    # About Tab (اطلاعات درباره نرم‌افزار)
    # ============================================================
    def add_about_tab(self):
        about_tab = QWidget()
        layout = QVBoxLayout()
        logo_label = QLabel()
        logo_label.setPixmap(
            QtGui.QPixmap("./assets/logo.png").scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        credit = QLabel("Created by Sina Jahanbakhsh")
        credit.setAlignment(Qt.AlignCenter)
        layout.addWidget(credit)
        about_tab.setLayout(layout)
        self.tabs.addTab(about_tab, "About")

    # ============================================================
    # Actuator Table Initialization
    # راه‌اندازی جدول عملگرها
    # ============================================================
    def init_actuator_table(self):
        self.actuator_table.setRowCount(len(ACTUATORS))
        for row, name in enumerate(ACTUATORS.keys()):
            self.actuator_table.setItem(row, 0, QTableWidgetItem(name))
            self.actuator_table.setItem(row, 1, QTableWidgetItem(""))

    # ============================================================
    # Live Monitoring Signal Layout
    # ایجاد لیبل‌ها برای نمایش داده‌های زنده
    # ============================================================
    def init_monitor_table(self):
        # Each tuple = (Group, SignalKey, LabelText)
        self.signals = [
            ("Diagnostic Session", None, "Diagnostic Session"),
            ("Spare Part Number", None, "Spare Part Number"),
            ("System Supplier ID", None, "System Supplier ID"),
            ("Manufacturing Date", None, "Manufacturing Date"),
            ("VIN", None, "VIN"),
            ("Software Version", None, "Software Version"),
            ("Hardware Version", None, "Hardware Version"),
            # --- Speeds ---
            ("Wheel Speeds + Vehicle Speed", "WheelFL_kmh", "Wheel Speed Front Left"),
            ("Wheel Speeds + Vehicle Speed", "WheelFR_kmh", "Wheel Speed Front Right"),
            ("Wheel Speeds + Vehicle Speed", "WheelRL_kmh", "Wheel Speed Rear Left"),
            ("Wheel Speeds + Vehicle Speed", "WheelRR_kmh", "Wheel Speed Rear Right"),
            ("Wheel Speeds + Vehicle Speed", "VehicleSpeed_kmh", "Vehicle Speed"),
            # --- Inputs ---
            ("Input Data", "BatteryV", "Battery Voltage (V)"),
            ("Input Data", "BrakeLight", "Brake Light Switch"),
            # --- Actuation State ---
            ("Actuation State", "ValveRelay", "Valve Relay"),
            ("Actuation State", "PumpMotor", "Pump Motor"),
            ("Actuation State", "EVFL", "Inlet Valve Front Left"),
            ("Actuation State", "AVFL", "Outlet Valve Front Left"),
            ("Actuation State", "EVFR", "Inlet Valve Front Right"),
            ("Actuation State", "AVFR", "Outlet Valve Front Right"),
            ("Actuation State", "EVRL", "Inlet Valve Rear Left"),
            ("Actuation State", "AVRL", "Outlet Valve Rear Left"),
            ("Actuation State", "EVRR", "Inlet Valve Rear Right"),
            ("Actuation State", "AVRR", "Outlet Valve Rear Right"),
            ("Actuation State", "USV1", "Valve USV1"),
            ("Actuation State", "USV2", "Valve USV2"),
            ("Actuation State", "HSV1", "Valve HSV1"),
            ("Actuation State", "HSV2", "Valve HSV2"),
            # --- Statuses ---
            ("Filling-in Status", None, "Filling-in Status"),
            ("EOL Status", None, "EOL Status"),
            # --- Sensors ---
            ("System Sensors", "MasterCylinder_bar", "Master Cylinder Pressure (bar)"),
            ("System Sensors", "Steering_deg", "Steering Angle (°)"),
            ("System Sensors", "Yaw_rad_s", "Yaw Rate (rad/s)"),
            ("System Sensors", "Lateral_m_s2", "Lateral Acceleration (m/s²)"),
            ("System Sensors", "Longitudinal_m_s2", "Longitudinal Acceleration (m/s²)"),
            # --- Variant ---
            ("Variant Code", None, "Variant Code"),
        ]

        # Create labels in grid layout (two per row)
        self.value_labels = {}
        row, col = 0, 0
        for group, signal, label in self.signals:
            lbl_name = QLabel(label)
            lbl_val = QLabel("N/A")
            lbl_val.setMinimumWidth(120)
            lbl_val.setStyleSheet("padding: 2px; border: 1px solid lightgray;")

            self.grid_signals.addWidget(lbl_name, row, col * 2)
            self.grid_signals.addWidget(lbl_val, row, col * 2 + 1)

            self.value_labels[(group, signal)] = lbl_val
            col += 1
            if col >= 2:
                col = 0
                row += 1

    # ============================================================
    # Initialize PyQtGraph Live Plots
    # ============================================================
    def init_graphs(self):
        self.max_points = 200
        self.time_axis = deque(maxlen=self.max_points)

        # --- Wheel Speeds Plot ---
        self.wheel_plot = pg.PlotWidget(title="Wheel Speeds (km/h)")
        self.wheel_plot.addLegend()
        self.graph_layout.addWidget(self.wheel_plot)
        self.curves_wheel = {
            "WheelFL_kmh": self.wheel_plot.plot(pen='r', name="Front Left"),
            "WheelFR_kmh": self.wheel_plot.plot(pen='g', name="Front Right"),
            "WheelRL_kmh": self.wheel_plot.plot(pen='b', name="Rear Left"),
            "WheelRR_kmh": self.wheel_plot.plot(pen='y', name="Rear Right"),
            "VehicleSpeed_kmh": self.wheel_plot.plot(pen='w', name="Vehicle"),
        }
        self.data_wheel = {k: deque(maxlen=self.max_points) for k in self.curves_wheel}

        # --- Sensors Plot ---
        self.sensor_plot = pg.PlotWidget(title="Sensors")
        self.sensor_plot.addLegend()
        self.graph_layout.addWidget(self.sensor_plot)
        self.curves_sensor = {
            "Steering_deg": self.sensor_plot.plot(pen='c', name="Steering Angle"),
            "Yaw_rad_s": self.sensor_plot.plot(pen='m', name="Yaw Rate"),
            "Lateral_m_s2": self.sensor_plot.plot(pen='r', name="Lateral Accel"),
            "Longitudinal_m_s2": self.sensor_plot.plot(pen='g', name="Longitudinal Accel"),
        }
        self.data_sensor = {k: deque(maxlen=self.max_points) for k in self.curves_sensor}

    # --- Actuator Functions ---
    def run_actuator_on(self):
        uds = UDSClient(channel=CAN_INTERFACE)
        try:
            uds.enter_extended_session()
            uds.security_access()
            actuator_id = self.actuator_select.currentData()
            uds.actuator_test(actuator_id, on=True, time_ms=1000)
            time.sleep(1.2)
            uds.actuator_test(actuator_id, on=False, time_ms=1000)
        finally:
            uds.shutdown()

    def run_all_actuators(self):
        # Remove summary row if it exists
        current_row_count = self.actuator_table.rowCount()
        if current_row_count > len(ACTUATORS):
            last_item = self.actuator_table.item(current_row_count - 1, 0)
            if last_item and "EOL Actuator Test" in last_item.text():
                self.actuator_table.removeRow(current_row_count - 1)

        QApplication.processEvents()

        # Clear previous status messages
        self.actuator_table.setRowCount(len(ACTUATORS))
        for row in range(self.actuator_table.rowCount()):
            empty_item = QTableWidgetItem("")
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.actuator_table.setItem(row, 1, empty_item)

        QApplication.processEvents()

        uds = UDSClient(channel=CAN_INTERFACE)
        all_passed = True
        try:
            uds.enter_extended_session()
            uds.security_access()
            for row, (name, aid) in enumerate(ACTUATORS.items()):
                resp = uds.actuator_test(aid, on=True, time_ms=1000)
                time.sleep(1.2)
                uds.actuator_test(aid, on=False, time_ms=1000)
                time.sleep(0.2)

                status_text = "✅ Success" if resp else "❌ Fail"
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)

                color = QColor(200, 255, 200) if resp else QColor(255, 200, 200)
                status_item.setBackground(QBrush(color))

                self.actuator_table.setItem(row, 1, status_item)
                QApplication.processEvents()

                if not resp:
                    all_passed = False

            # Add final summary row
            final_row = self.actuator_table.rowCount()
            self.actuator_table.insertRow(final_row)
            if all_passed:
                message = "✅ EOL Actuator Test has been successfully passed"
                bg_color = QColor(200, 255, 200)
            else:
                message = "❌ EOL Actuator Test failed — check individual actuators"
                bg_color = QColor(255, 200, 200)
            summary_item = QTableWidgetItem(message)
            summary_item.setTextAlignment(Qt.AlignCenter)
            summary_item.setBackground(QBrush(bg_color))

            # Make text bold and 3x larger
            font = QFont()
            font.setBold(True)
            font.setPointSize(font.pointSize() * 2)  # Triple the default font size
            summary_item.setFont(font)

            # Insert and style the row
            self.actuator_table.insertRow(self.actuator_table.rowCount())  # Add new row at the end
            final_row = self.actuator_table.rowCount() - 1  # Now get the correct index

            self.actuator_table.setSpan(final_row, 0, 1, self.actuator_table.columnCount())
            self.actuator_table.setItem(final_row, 0, summary_item)

            # Double the row height
            default_height = self.actuator_table.rowHeight(0)
            self.actuator_table.setRowHeight(final_row, default_height * 2)

        finally:
            uds.shutdown()

    # --- Monitoring ---
    def start_monitoring(self):
        if self.monitor_thread and self.monitor_thread.isRunning():
            return
        self.monitor_thread = MonitorWorker(channel=CAN_INTERFACE)
        self.monitor_thread.data_signal.connect(self.update_monitor_table)
        self.monitor_thread.start()

    def stop_monitoring(self):
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread = None

    def update_monitor_table(self, data: dict):
        self.monitor_data = data
        t = time.time()
        self.time_axis.append(t)

        for group, signal, _ in self.signals:
            decoded = data.get(group, None)
            value_str = "N/A"
            if isinstance(decoded, dict) and signal and signal in decoded:
                value_str = decoded[signal]
            elif decoded is not None and signal is None:
                value_str = decoded

            if isinstance(value_str, bool):
                value_str = "ON" if value_str else "OFF"

            lbl = self.value_labels.get((group, signal))
            if lbl:
                lbl.setText(str(value_str))
                if str(value_str).upper() in ("ON", "1", "TRUE"):
                    lbl.setStyleSheet("background-color: lightgreen; padding: 2px;")
                elif str(value_str).upper() in ("OFF", "0", "FALSE"):
                    lbl.setStyleSheet("background-color: pink; padding: 2px;")
                else:
                    lbl.setStyleSheet("padding: 2px; border: 1px solid lightgray;")

        # Update graphs
        wheels = data.get("Wheel Speeds + Vehicle Speed", {})
        for key, curve in self.curves_wheel.items():
            if isinstance(wheels, dict) and key in wheels:
                self.data_wheel[key].append(float(wheels[key]))
                curve.setData(list(self.time_axis), list(self.data_wheel[key]))

        sensors = data.get("System Sensors", {})
        for key, curve in self.curves_sensor.items():
            if isinstance(sensors, dict) and key in sensors:
                self.data_sensor[key].append(float(sensors[key]))
                curve.setData(list(self.time_axis), list(self.data_sensor[key]))

    def read_dtcs(self):
        uds = UDSClient(channel=CAN_INTERFACE)
        try:
            uds.enter_extended_session()
            uds.security_access()
            dtcs = uds.read_dtcs()
            self.dtc_table.setRowCount(len(dtcs))
            for row, d in enumerate(dtcs):
                self.dtc_table.setItem(row, 0, QTableWidgetItem(d["code"]))
                self.dtc_table.setItem(row, 1, QTableWidgetItem(d["desc"]))
                self.dtc_table.setItem(row, 2, QTableWidgetItem(d["status"]))
                self.dtc_table.setItem(row, 3, QTableWidgetItem(d["severity"]))
        finally:
            uds.shutdown()

    def clear_dtcs(self):
        uds = UDSClient(channel=CAN_INTERFACE)
        try:
            uds.enter_extended_session()
            uds.security_access()
            if uds.clear_dtcs():
                self.dtc_table.setRowCount(0)
        finally:
            uds.shutdown()

    def _run_calibration_routine(self, routine_name: str, routine_attr_name: str):
        lbl = getattr(self, "lbl_cal_status", None)
        bar = getattr(self, "progress_calibration", None)

        if lbl:
            lbl.setText(f"➡️ Starting {routine_name}...")
        if bar:
            bar.setValue(0)
            bar.setFormat("Running...")
            bar.setStyleSheet("QProgressBar::chunk { background-color: lightblue; }")

        uds = UDSClient(channel=CAN_INTERFACE)
        try:
            uds.enter_extended_session()
            uds.security_access()
            func = getattr(uds, routine_attr_name)

            # Run the routine (this usually completes in <1s)
            resp = func()

            if resp and len(resp) >= 3 and resp[0] == 0x71:
                msg = f"✅ {routine_name}: OK (resp: {resp.hex()})"
                if bar:
                    bar.setStyleSheet("QProgressBar::chunk { background-color: lightgreen; }")
                    bar.setValue(100)
                    bar.setFormat("Completed ✓")
            elif resp and resp[0] == 0x7F:
                nrc = resp[2] if len(resp) > 2 else None
                msg = f"❌ {routine_name}: Negative Response (NRC=0x{nrc:02X})"
                if bar:
                    bar.setStyleSheet("QProgressBar::chunk { background-color: lightcoral; }")
                    bar.setValue(100)
                    bar.setFormat("Failed ✗")
            else:
                msg = f"ℹ️ {routine_name}: Unknown Response {resp}"

            if lbl:
                lbl.setText(msg)

            # Animate progress bar for 10 seconds while calibration runs
            if bar:
                self._animate_progress_bar(bar, duration_ms=10000)

        except Exception as e:
            if lbl:
                lbl.setText(f"❌ {routine_name}: {e}")
            if bar:
                bar.setStyleSheet("QProgressBar::chunk { background-color: lightcoral; }")
                bar.setValue(100)
                bar.setFormat("Error ✗")
        finally:
            uds.shutdown()

    def _animate_progress_bar(self, bar, duration_ms=10000):
        """Animate calibration progress bar for given duration"""
        steps = 100
        interval = duration_ms // steps
        bar.setValue(0)
        self._progress_val = 0
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(lambda: self._update_progress_bar(bar))
        self._progress_timer.start(interval)

    def _update_progress_bar(self, bar):
        self._progress_val += 1
        bar.setValue(self._progress_val)
        if self._progress_val >= 100:
            self._progress_timer.stop()
            bar.setFormat("Done ✓")

    def on_start_sas_cal(self):
        """Handler for Start SAS Calibration button"""
        self._run_calibration_routine("SAS Calibration (F105)", lambda: UDSClient(channel=CAN_INTERFACE).start_sas_calibration())

    def on_start_yaw_cal(self):
        """Handler for Start Yaw Rate Calibration button"""
        self._run_calibration_routine("Yaw Rate Calibration (F106)", lambda: UDSClient(channel=CAN_INTERFACE).start_yaw_calibration())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = DiagnosticGUI()
    gui.show()
    sys.exit(app.exec_())
