# ============================================================
# File: uds_client.py
# Author: Sina Jahanbakhsh
# Description:
#   Unified Diagnostic Services (UDS) client implementation
#   for communication with ESC (Electronic Stability Control) ECU
#   over CAN bus (ISO-TP). Provides session management,
#   security access, routine control, DTC handling, and
#   actuator test commands.
#
#   ای‌سی‌یو (ECU) کلاینت برای ارتباط تشخیصی از طریق پروتکل UDS،
#   شامل ورود به سشن، دسترسی امنیتی، کنترل روتین‌ها، خطاها و تست عملگرها.
# ============================================================

import time
import can
import isotp
from dtc_codes import DTC_MAP, decode_status
from can_control import bring_up, bring_down
from utils import print_request, print_response
from decoders import decode_value  # ← new external decoder module


class UDSClient:
    """UDS client for ESC ECU communication via CAN."""

    def __init__(self, channel="can0", txid=0x710, rxid=0x790, bitrate=500000):
        self.channel = channel
        self.txid = txid
        self.rxid = rxid
        self.bitrate = bitrate
        self.bus = None
        self.stack = None
        self.timeout = 2.0
        self.connect()

    # ------------------------------------------------------------
    # Connection setup / teardown
    # ------------------------------------------------------------
    def connect(self):
        """Initialize CAN and ISO-TP stack."""
        bring_up(self.channel, self.bitrate)
        self.bus = can.interface.Bus(channel=self.channel, interface="socketcan")
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits,
                             txid=self.txid, rxid=self.rxid)
        self.stack = isotp.CanStack(bus=self.bus, address=addr)
        try:
            self.stack.set_fc_opts(stmin=0.01, bs=8)
        except Exception:
            try:
                self.stack.fc_stmin = 0.01
                self.stack.fc_bs = 8
            except Exception:
                pass
        self.stack.padding = 0x00

    def shutdown(self):
        """Close CAN and ISO-TP interfaces."""
        if self.stack:
            try:
                self.stack.stop()
            except Exception:
                pass
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception:
                pass
        bring_down(self.channel)

    # ------------------------------------------------------------
    # Request sending and response handling
    # ------------------------------------------------------------
    def send_request(self, label, payload, timeout=None):
        """Send a UDS request and wait for response, handle 0x78 pending."""
        if timeout is None:
            timeout = self.timeout
        print_request(label, payload)
        self.stack.send(payload)

        start = time.time()
        pending = False

        while True:
            self.stack.process()
            if self.stack.available():
                resp = self.stack.recv()
                print_response(label, resp)

                # Handle NRC 0x78 (Response Pending)
                if resp and len(resp) >= 3 and resp[0] == 0x7F and resp[2] == 0x78:
                    if not pending:
                        print("⏳ ای‌سی‌یو پاسخ در حال پردازش است...")
                        pending = True
                    start = time.time()
                    continue
                return resp

            if time.time() - start > timeout:
                print(f"⏱️ Timeout waiting for {label}")
                return None
            time.sleep(0.005)

    # ------------------------------------------------------------
    # Session & Security
    # ------------------------------------------------------------
    def enter_extended_session(self):
        """Enter extended diagnostic session."""
        resp = self.send_request("ExtendedSession", b"\x10\x03")
        return bool(resp and resp[:2] == b"\x50\x03")

    def security_access(self):
        """
        Perform UDS SecurityAccess handshake (seed/key exchange).
        الگوریتم محاسبه کلید با استفاده از دادهٔ seed از ای‌سی‌یو.
        """
        resp = self.send_request("SecurityAccess - RequestSeed", b"\x27\x01")
        if not resp or resp[0:2] != b"\x67\x01":
            print("❌ خطا در دریافت Seed از ای‌سی‌یو")
            return False

        seed = int.from_bytes(resp[2:], "big")
        seed_bytes = len(resp) - 2
        print(f"🔑 Received Seed ({seed_bytes} bytes): 0x{seed:0{seed_bytes*2}X}")

        # Key calculation (simple XOR-shift mask)
        raw_key = ((((seed >> 2) ^ seed) << 3) ^ seed)
        mask = (1 << (8 * seed_bytes)) - 1
        key = raw_key & mask

        print(f"🔑 Computed Key (masked): 0x{key:0{seed_bytes*2}X}")
        payload = b"\x27\x02" + key.to_bytes(seed_bytes, "big")

        resp2 = self.send_request("SecurityAccess - SendKey", payload)
        if resp2 and resp2[:2] == b"\x67\x02":
            print("✅ دسترسی امنیتی موفق بود")
            return True

        print("❌ Security Access Failed")
        return False

    def tester_present(self):
        """Keep session alive."""
        self.send_request("TesterPresent", b"\x3E\x00", timeout=0.6)

    # ------------------------------------------------------------
    # RoutineControl (0x31)
    # ------------------------------------------------------------
    def _routine_control(self, control_option, routine_id, params=b"", timeout=None):
        """Generic RoutineControl command."""
        if timeout is None:
            timeout = self.timeout
        payload = bytes([0x31, control_option]) + routine_id.to_bytes(2, "big") + params
        return self.send_request(
            f"RoutineControl 0x{routine_id:04X} (opt={control_option:02X})", payload, timeout=timeout
        )

    def start_routine(self, routine_id, params=b"", timeout=10.0):
        """Start a diagnostic routine (کنترل شروع روتین تشخیصی)."""
        return self._routine_control(0x01, routine_id, params, timeout)

    def start_sas_calibration(self, params=b"", timeout=20.0):
        """Start Steering Angle Sensor calibration (F105)."""
        return self.start_routine(0xF105, params, timeout)

    def start_yaw_calibration(self, params=b"", timeout=20.0):
        """Start Yaw Rate Sensor calibration (F106)."""
        return self.start_routine(0xF106, params, timeout)

    # ------------------------------------------------------------
    # Actuator Test (0x31 F003)
    # ------------------------------------------------------------
    def actuator_test(self, actuator_id, on=True, time_ms=1000):
        """Perform actuator test for given ID."""
        actuator_value = b"\xFF\xFF" if on else b"\x00\x00"
        time_val = int(time_ms / 10).to_bytes(2, "big")
        payload = (
            b"\x31\x01\xF0\x03" +
            actuator_value + actuator_id.to_bytes(2, "big") +
            b"\x00\x00\x00\x00" + time_val +
            b"\x00" * 8
        )
        resp = self.send_request(f"ActuatorTest 0x{actuator_id:04X}", payload)
        if resp and resp[:2] == b"\x71\x01":
            print("✅ تست عملگر موفق بود")
        elif resp and resp[0] == 0x7F:
            print("❌ خطای پاسخ منفی از ای‌سی‌یو")
        return resp

    # ------------------------------------------------------------
    # Diagnostic Trouble Codes (DTC)
    # ------------------------------------------------------------
    def read_dtcs(self):
        """Read stored Diagnostic Trouble Codes (خواندن کدهای خطا)."""
        dtcs, seen = [], set()

        for mask in [b"\x04", b"\x01"]:
            print(f"➡️ Sending ReadDTCInformation: 1902{mask.hex()}")
            resp = self.send_request("ReadDTCInformation", b"\x19\x02" + mask, timeout=5.0)

            if not resp or resp[0] != 0x59:
                print("❌ پاسخ نامعتبر برای DTC")
                continue

            payload = resp[3:]
            for i in range(0, len(payload), 4):
                if i + 4 > len(payload):
                    break
                code_bytes = payload[i:i + 3]
                status = payload[i + 3]
                dtc_val = int.from_bytes(code_bytes, "big")

                if dtc_val in seen:
                    continue
                seen.add(dtc_val)

                dtc_code = f"{code_bytes[0]:02X}{code_bytes[1]:02X}{code_bytes[2]:02X}"
                desc = DTC_MAP.get(dtc_val, f"DTC {dtc_code}")
                decoded = decode_status(status)

                dtcs.append({
                    "code": dtc_code,
                    "status": decoded["flags"],
                    "severity": decoded["severity"],
                    "desc": desc
                })

        return dtcs

    def clear_dtcs(self):
        """Clear all stored DTCs (پاک‌کردن خطاها)."""
        resp = self.send_request("ClearDiagnosticInformation", b"\x14\xFF\xFF\xFF")
        return bool(resp and resp[0] == 0x54)

    # ------------------------------------------------------------
    # ReadDataByIdentifier (0x22)
    # ------------------------------------------------------------
    def read_data_by_identifier(self, did):
        """Read data by DID (خواندن داده با شناسه)."""
        return self.send_request(f"ReadDataByIdentifier {hex(did)}", b"\x22" + did.to_bytes(2, "big"))

    def decode_value(self, did, data):
        """Delegate decoding to external decoder module."""
        return decode_value(did, data)
