# Automotive Diagnostics Tool

## Overview
This project is a Python-based application for automotive ESC diagnostics, supporting CAN (Controller Area Network) and UDS (Unified Diagnostic Services) protocols. It features a graphical user interface (GUI) built with PyQt5 for interacting with vehicle electronic control units (ECUs), reading diagnostic trouble codes (DTCs), controlling actuators, and visualizing data.

## Features
- Communicate with vehicle ECUs via CAN and UDS protocols.
- Decode and display diagnostic trouble codes (DTCs).
- Control vehicle actuators.
- Visualize diagnostic data using graphs (via pyqtgraph).
- User-friendly GUI for diagnostics and testing.

## Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/automotive-diagnostics.git
   cd automotive-diagnostics
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure CAN interface** (e.g., for `can0`):
   ```bash
   sudo ip link set can0 up type can bitrate 500000
   ```
   Note: You may need a CAN hardware interface (e.g., USB-to-CAN adapter) and appropriate permissions.
5. **Run the application**:
   ```bash
   sudo python src/gui.py
   ```

## Requirements
- **Python**: 3.8 or higher
- **Hardware**: CAN interface (e.g., USB-to-CAN adapter)
- **Dependencies** (listed in `requirements.txt`):
  - `python-can==4.6.1`: CAN communication
  - `can-isotp==2.0.7`: ISO-TP protocol
  - `udsoncan==1.25.1`: UDS protocol
  - `PyQt5==5.15.11`: GUI framework
  - `pyqtgraph==0.13.7`: Data visualization
  - `numpy==2.3.3`: Data processing

## Usage
1. Ensure your CAN interface is connected and configured.
2. Launch the GUI with `sudo python src/gui.py`.
3. Use the interface to:
   - Read and decode DTCs.
   - Send UDS commands to ECUs.
   - Control actuators.
   - View data visualizations.

## Project Structure
```
automotive-diagnostics/
├── src/                    # Source code
│   ├── actuators.py        # Actuator control logic
│   ├── can_control.py      # CAN communication logic
│   ├── client.py           # Main client for diagnostics
│   ├── decoders.py         # DTC and data decoding
│   ├── dtc_codes.py        # DTC definitions
│   ├── gui.py              # GUI implementation
│   ├── uds_client.py       # UDS protocol logic
│   ├── utils.py            # Utility functions
├── ui/                     # UI files
│   ├── HES_gui.ui          # Qt Designer UI file
├── assets/                 # Static assets
│   ├── logo.png            # Application logo
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore file
├── LICENSE                # License file
```

## Contributing
Contributions are welcome! Please submit a pull request or open an issue on GitHub for bugs, features, or improvements.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
