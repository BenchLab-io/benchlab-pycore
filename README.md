# BENCHLAB Python Core (`benchlab-pycore`)

**BENCHLAB PyCore** provides low-level telemetry, sensor IO, and device communication utilities
for BENCHLAB. It includes standardized interfaces for reading sensors, handling serial communication, and publishing telemetry data.

## Features

- Read and translate sensor data from BENCHLAB devices  
- Communicate via serial ports  
- Designed to be easily integrated into larger telemetry pipelines

## Installation

pip install benchlab-pycore

## Usage Example

import benchlab
from benchlab.core import get_fleet_info, read_sensors

info = get_fleet_info()
print(info)

## Project Layout

benchlab/
├── core/
│ ├── serial_io.py
│ ├── sensor_translation.py
│ └── ...

## Development

Clone and install locally:

git clone https://github.com/BenchLab-io/benchlab-pycore.git
cd benchlab-pycore
pip install -e .

## License

MIT License © 2025 BenchLab Contributors
