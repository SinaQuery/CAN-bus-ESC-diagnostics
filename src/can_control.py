# can_control.py
import os
import time

def bring_up(channel="can0", bitrate=500000):
    """
    Bring up CAN interface with given bitrate.
    Requires passwordless sudo or proper permissions.
    """
    os.system(f"sudo ip link set {channel} down >/dev/null 2>&1 || true")
    os.system(f"sudo ip link set {channel} type can bitrate {bitrate} >/dev/null 2>&1 || true")
    os.system(f"sudo ip link set {channel} up")
    time.sleep(0.05)
    print(f"✅ {channel} is UP at {bitrate} bps")

def bring_down(channel="can0"):
    """Bring down CAN interface safely."""
    os.system(f"sudo ip link set {channel} down >/dev/null 2>&1 || true")
    print(f"⏹️ {channel} is DOWN")
