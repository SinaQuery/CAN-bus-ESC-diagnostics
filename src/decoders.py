# ============================================================
# File: decoders.py
# Author: Sina Jahanbakhsh
# Description:
#   Data decoding utilities for UDS ReadDataByIdentifier (RDBI)
#   responses. Converts raw payloads from ESC ECU to
#   human-readable Python data types (strings, numbers, dicts).
#
#   ماژول تفسیر داده‌های دریافتی از ای‌سی‌یو (ECU)
#   در پاسخ به فرمان ReadDataByIdentifier، جهت تبدیل
#   بایت‌های خام به مقادیر قابل‌فهم برای انسان.
# ============================================================

from utils import hexdump


def decode_value(did, data):
    """
    Decode payload for a given DID from ReadDataByIdentifier (0x22) response.

    did : int - Data Identifier (e.g., 0xFD00)
    data: bytes - Full UDS response including SID (e.g. b'\x62\xFD\x00...')

    Returns:
        Decoded value as string, number, or dict.

    پارامترها:
        did : شناسه داده
        data : پاسخ خام دریافتی از ای‌سی‌یو
    """
    if not data or len(data) < 3:
        return None

    payload = data[3:]  # strip SID + DID

    # ============================================================
    # --- F186 : Diagnostic Session ---
    # ============================================================
    if did == 0xF186:
        if len(payload) >= 1:
            session_map = {
                0x01: "Default Session",
                0x03: "Extended Session"
            }
            return session_map.get(payload[0], f"0x{payload[0]:02X}")
        return None

    # ============================================================
    # --- F187 : Spare Part Number (ASCII, 8 bytes) ---
    # ============================================================
    if did == 0xF187:
        try:
            return payload[:8].decode("ascii", errors="ignore").rstrip()
        except Exception:
            return hexdump(payload)

    # ============================================================
    # --- F18A : System Supplier ID (ASCII, 10 bytes) ---
    # ============================================================
    if did == 0xF18A:
        try:
            return payload[:10].decode("ascii", errors="ignore").rstrip()
        except Exception:
            return hexdump(payload)

    # ============================================================
    # --- F18B : Manufacturing Date (BCD format) ---
    # ============================================================
    if did == 0xF18B:
        if len(payload) >= 4:
            def bcd_to_int(b): return ((b >> 4) * 10) + (b & 0x0F)
            year = bcd_to_int(payload[0]) * 100 + bcd_to_int(payload[1])
            month = bcd_to_int(payload[2])
            day = bcd_to_int(payload[3])
            return f"{year:04d}-{month:02d}-{day:02d}"
        return hexdump(payload)

    # ============================================================
    # --- F190 : VIN (ASCII or structured) ---
    # ============================================================
    if did == 0xF190:
        try:
            return payload.decode("ascii", errors="ignore").strip()
        except Exception:
            return hexdump(payload)

    # ============================================================
    # --- F195 : Software Version ---
    # ============================================================
    if did == 0xF195:
        try:
            return payload[:8].decode("ascii", errors="ignore").rstrip()
        except Exception:
            return hexdump(payload)

    # ============================================================
    # --- F1A4 : Hardware Version ---
    # ============================================================
    if did == 0xF1A4:
        try:
            return payload[:10].decode("ascii", errors="ignore").rstrip()
        except Exception:
            return hexdump(payload)

    # ============================================================
    # --- FD00 : Wheel & Vehicle Speeds ---
    # ============================================================
    if did == 0xFD00:
        if len(payload) < 10:
            return None

        def to_speed(raw):
            # Convert raw 16-bit to km/h, ignore invalid markers >= 0xFF00
            # تبدیل مقادیر خام به سرعت کیلومتر بر ساعت
            if raw >= 0xFF00:
                return None
            return raw * 0.05625

        vehicle_raw = int.from_bytes(payload[0:2], "big")
        fl_raw = int.from_bytes(payload[2:4], "big")
        fr_raw = int.from_bytes(payload[4:6], "big")
        rl_raw = int.from_bytes(payload[6:8], "big")
        rr_raw = int.from_bytes(payload[8:10], "big")

        return {
            "VehicleSpeed_kmh": to_speed(vehicle_raw),
            "WheelFL_kmh": to_speed(fl_raw),
            "WheelFR_kmh": to_speed(fr_raw),
            "WheelRL_kmh": to_speed(rl_raw),
            "WheelRR_kmh": to_speed(rr_raw),
        }

    # ============================================================
    # --- FD01 : Input Data (Battery, Brake) ---
    # ============================================================
    if did == 0xFD01:
        if len(payload) >= 2:
            battery_v = payload[0] * 0.08
            brake_on = (payload[1] == 0x01)
            return {"BatteryV": battery_v, "BrakeLight": brake_on}
        return None

    # ============================================================
    # --- FD02 : Actuation State ---
    # ============================================================
    if did == 0xFD02:
        if len(payload) >= 4:
            relay_status = "ON" if payload[0] == 0x01 else "OFF"
            pump_status = "ON" if payload[1] == 0x01 else "OFF"
            b5, b6 = payload[2], payload[3]
            valves = {
                "EVFL": bool(b5 & 0x01),
                "AVFL": bool(b5 & 0x02),
                "EVFR": bool(b5 & 0x04),
                "AVFR": bool(b5 & 0x08),
                "EVRL": bool(b5 & 0x10),
                "AVRL": bool(b5 & 0x20),
                "EVRR": bool(b5 & 0x40),
                "AVRR": bool(b5 & 0x80),
                "USV1": bool(b6 & 0x01),
                "USV2": bool(b6 & 0x02),
                "HSV1": bool(b6 & 0x04),
                "HSV2": bool(b6 & 0x08),
            }
            result = {"ValveRelay": relay_status, "PumpMotor": pump_status}
            result.update(valves)
            return result
        return {"Raw": hexdump(payload)}

    # ============================================================
    # --- FD03 : Filling-in Status ---
    # ============================================================
    if did == 0xFD03:
        if len(payload) >= 1:
            code = payload[0]
            mapping = {
                0x00: "Not completed",
                0xAA: "Completed OK",
                0xEE: "Completed Not OK",
                0xFF: "Delivery State"
            }
            return mapping.get(code, f"0x{code:02X}")
        return None

    # ============================================================
    # --- FD04 : EOL Status ---
    # ============================================================
    if did == 0xFD04:
        if len(payload) >= 1:
            code = payload[0]
            mapping = {
                0x00: "Not completed",
                0xAA: "Completed OK",
                0xEE: "Completed Not OK",
                0xFF: "Delivery State"
            }
            return mapping.get(code, f"0x{code:02X}")
        return None

    # ============================================================
    # --- FD05 : System Sensors (Pressure, Steering, Yaw, Accel) ---
    # ============================================================
    if did == 0xFD05:
        if len(payload) < 10:
            return None

        def decode_sensor(raw, resolution):
            """Two's complement & invalid handling."""
            # تفسیر داده‌های سنسور با درنظر گرفتن علامت و مقدار نامعتبر
            if raw == 0x7FFF:
                return None
            if raw < 0x8000:
                return raw * resolution
            neg = raw - 0x10000
            return neg * resolution

        mcp_raw = int.from_bytes(payload[0:2], "big")
        steer_raw = int.from_bytes(payload[2:4], "big")
        yaw_raw = int.from_bytes(payload[4:6], "big")
        lat_raw = int.from_bytes(payload[6:8], "big")
        lon_raw = int.from_bytes(payload[8:10], "big")

        return {
            "MasterCylinder_bar": decode_sensor(mcp_raw, 0.0153),
            "Steering_deg": decode_sensor(steer_raw, 0.1),
            "Yaw_rad_s": decode_sensor(yaw_raw, 0.00213),
            "Lateral_m_s2": decode_sensor(lat_raw, 0.02712),
            "Longitudinal_m_s2": decode_sensor(lon_raw, 0.02712)
        }

    # ============================================================
    # --- FD06 : Variant Code ---
    # ============================================================
    if did == 0xFD06:
        if len(payload) >= 1:
            return payload[0]
        return None

    # ============================================================
    # Default / Fallback
    # ============================================================
    return hexdump(payload)
