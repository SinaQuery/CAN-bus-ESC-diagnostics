# utils.py
import binascii

def hexdump(data: bytes) -> str:
    """Convert bytes to hex string for display."""
    return binascii.hexlify(data).decode()

def print_request(label, payload: bytes):
    print(f"\n➡️ Sending {label}: {hexdump(payload)}")

def print_response(label, resp: bytes):
    if resp is None:
        print(f"⬅️ {label} Response: None")
    else:
        print(f"⬅️ {label} Response: {hexdump(resp)}")
