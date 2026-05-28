# BENCHLAB Python Core (`benchlab-pycore`)

**BENCHLAB PyCore** provides low-level telemetry, sensor I/O, device communication, and configuration utilities for BENCHLAB hardware devices. It includes standardised interfaces for reading sensors, handling serial communication, translating raw sensor data into human-readable formats, and reading and writing all device configuration including fan profiles, RGB profiles, and calibration.

## Features

- **Device Discovery**: Automatically detect connected BENCHLAB devices
- **Multi-Variant Support**: Compatible with both ORIGINAL (0x10) and CFE (0x11) device variants
- **Sensor Data Reading**: Read raw sensor data including power, voltage, temperature, and fan information
- **Extended Telemetry (CFE)**: CFE variant provides 23 power sensors and 8 temperature sensors (vs 11 and 4 in ORIGINAL)
- **Device Configuration**: Read and write fan profiles, RGB profiles, friendly name, and calibration
- **Calibration Management**: Load and store calibration to factory and user flash slots
- **Serial Communication**: Handle USB-to-serial communication with BENCHLAB devices
- **Error Handling**: Comprehensive error handling and logging for robust integration

## Installation

```bash
pip install benchlab-pycore
```

## Quick Start

### Basic Device Discovery and Sensor Reading

```python
import serial
from benchlab_pycore.core import get_fleet_info, read_device, read_sensors, translate_sensor_struct

# Discover all connected BENCHLAB devices
devices = get_fleet_info()
print(f"Found {len(devices)} device(s):")
for device in devices:
    print(f"  Port: {device['port']}, UID: {device['uid']}, Firmware: {device['firmware']}")

if devices:
    ser = serial.Serial(devices[0]['port'], 115200, timeout=1)

    # Read device info to determine variant
    info = read_device(ser)
    product_id = info['ProductId']

    # Read and translate sensors
    sensors = read_sensors(ser, product_id=product_id)
    if sensors:
        data = translate_sensor_struct(sensors, product_id=product_id)
        print(f"CPU Power:        {data['CPU_Power']}W")
        print(f"Chip Temperature: {data['Chip_Temp']}°C")
        print(f"ATX12V Voltage:   {data['ATX12V_Voltage']}V")

    ser.close()
```

### Working with CFE Devices

```python
import serial
from benchlab_pycore.core import (
    get_fleet_info,
    read_sensors,
    read_device,
    translate_sensor_struct,
    BENCHLAB_CFE_PRODUCT_ID,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
)

def read_with_variant_detection(port):
    ser = serial.Serial(port, 115200, timeout=1)
    try:
        device_info = read_device(ser)
        if not device_info:
            return None

        product_id = device_info['ProductId']
        variant = "CFE" if product_id == BENCHLAB_CFE_PRODUCT_ID else "ORIGINAL"
        print(f"Device on {port}: {variant} (Product ID: 0x{product_id:02X})")

        sensors = read_sensors(ser, product_id=product_id)
        if sensors:
            data = translate_sensor_struct(sensors, product_id=product_id)
            print(f"  CPU Power:  {data['CPU_Power']}W")
            print(f"  GPU Power:  {data['GPU_Power']}W")
            print(f"  Chip Temp:  {data['Chip_Temp']}°C")

            if variant == "CFE":
                print(f"  TS_HPWR1_IN:  {data.get('TS_HPWR1_IN', 'N/A')}°C")
                print(f"  TS_HPWR2_OUT: {data.get('TS_HPWR2_OUT', 'N/A')}°C")
            return data
    finally:
        ser.close()

devices = get_fleet_info()
for device in devices:
    read_with_variant_detection(device['port'])
```

### Reading and Writing Configuration

```python
import serial
from benchlab_pycore.core import (
    read_name, write_name,
    read_fan_profile, write_fan_profile,
    read_rgb_profile, write_rgb_profile,
    FanConfigStruct, FanMode, RGBConfigStruct,
    CAL_USER, CAL_FACTORY,
)

ser = serial.Serial("COM4", 115200, timeout=1)

# Read device name
print(f"Device name: {read_name(ser)}")

# Read a fan profile
cfg = read_fan_profile(ser, fan_profile=0, fan_id=0)
if cfg:
    print(f"Fan 0/0: FanMode={cfg.FanMode} FixedDuty={cfg.FixedDuty}%")

# Write a fan profile
cfg = FanConfigStruct()
cfg.FanMode    = FanMode.FIXED
cfg.FixedDuty  = 60
cfg.TempSource = 0
cfg.MinDuty    = 20
cfg.MaxDuty    = 100
cfg.RampStep   = 5
cfg.FanStop    = 0
write_fan_profile(ser, fan_profile=0, fan_id=0, config=cfg)

# Read and write RGB
rgb = read_rgb_profile(ser, rgb_profile=0)
rgb.Mode = 9   # SINGLE_COLOR
rgb.Red  = 255
rgb.Green = 0
rgb.Blue  = 0
write_rgb_profile(ser, rgb_profile=0, config=rgb)

ser.close()
```

## API Reference

### Device Discovery

- **`get_benchlab_ports()`** → `List[Dict[str, str]]`
  Returns all BENCHLAB COM ports without opening them. Each dict has a `'port'` key.

- **`find_benchlab_devices()`** → `List[Dict[str, str]]`
  Scans and returns all connected devices with `'port'`, `'uid'`, and `'fw'` keys.

- **`get_fleet_info()`** → `List[Dict[str, Union[str, int]]]`
  Returns all devices with `'port'`, `'firmware'`, and `'uid'` keys.

### Serial Communication

- **`read_device(ser)`** → `Optional[Dict[str, int]]`
  Reads vendor info. Returns dict with `'VendorId'`, `'ProductId'`, `'FwVersion'`.
  Use `ProductId` to determine variant: `0x10` = ORIGINAL, `0x11` = CFE.

- **`read_sensors(ser, product_id=None)`** → `Optional[Union[SensorStructOriginal, SensorStructCFE]]`
  Reads all sensors. Pass `product_id` to select the correct struct.

- **`read_uid(ser, retries=3, delay=0.2)`** → `Optional[str]`
  Returns device UID as an uppercase hex string.

### Data Translation

- **`translate_sensor_struct(sensor_struct, product_id=None)`** → `Dict[str, Any]`
  Converts raw sensor data to human-readable format. Auto-detects variant from struct type or `product_id`.

### Configuration — Friendly Name

- **`ping(ser)`** → `bool`
  Sends the welcome command and verifies the device responds correctly.

- **`read_name(ser)`** → `Optional[str]`
  Reads the device friendly name (up to 31 characters).

- **`write_name(ser, name)`** → `bool`
  Writes a new friendly name. Truncated to 31 characters if longer.

### Configuration — Fan Profiles

Fan profiles are indexed by profile slot (0–2) and fan channel (0–8).

- **`read_fan_profile(ser, fan_profile, fan_id)`** → `Optional[FanConfigStruct]`
  Reads one fan channel's configuration. Returns `FanConfigStruct` or `None`.

- **`write_fan_profile(ser, fan_profile, fan_id, config)`** → `bool`
  Writes a fan channel configuration.

`FanConfigStruct` fields (14 bytes, packed):

| Field | Type | Description |
|-------|------|-------------|
| `FanMode` | `uint8` | `FanMode.TEMP_CONTROL=0`, `FanMode.FIXED=1`, `FanMode.EXT=2` |
| `TempSource` | `uint8` | `TempSrc` enum: `AUTO=0`, `TS1–TS4=1–4`, `TAMB=5` |
| `Temp[2]` | `int16[2]` | Temperature breakpoints in tenths of °C (e.g. 300 = 30.0°C) |
| `Duty[2]` | `uint8[2]` | Duty cycle at each breakpoint (0–100%) |
| `RampStep` | `uint8` | Max duty change per control tick |
| `FixedDuty` | `uint8` | Duty cycle used in FIXED mode (0–100%) |
| `MinDuty` | `uint8` | Minimum allowed duty cycle (0–100%) |
| `MaxDuty` | `uint8` | Maximum allowed duty cycle (0–100%) |
| `FanStop` | `uint8` | `FanStop.OFF=0`, `FanStop.ON=1` |

### Configuration — RGB Profiles

RGB profiles are indexed 0–1.

- **`read_rgb_profile(ser, rgb_profile)`** → `Optional[RGBConfigStruct]`
  Reads one RGB profile. Returns `None` if the slot is not available.

- **`write_rgb_profile(ser, rgb_profile, config)`** → `bool`
  Writes an RGB profile.

`RGBConfigStruct` fields (6 bytes, packed):

| Field | Type | Description |
|-------|------|-------------|
| `Mode` | `uint8` | `RGBMode` enum (0=RAINBOW_CYCLE … 9=SINGLE_COLOR) |
| `Red` | `uint8` | Red component 0–255 |
| `Green` | `uint8` | Green component 0–255 |
| `Blue` | `uint8` | Blue component 0–255 |
| `Direction` | `uint8` | `RGBDirection.CLOCKWISE=0`, `COUNTER_CLOCKWISE=1` |
| `Speed` | `uint8` | Animation speed |

### Configuration — Calibration

Calibration structs are device-scoped — ORIGINAL and CFE have different sizes and are automatically selected based on `product_id`.

| Variant | Struct | Size |
|---------|--------|------|
| ORIGINAL | `CalibrationStruct` | 178 bytes |
| CFE | `CalibrationStructCFE` | 294 bytes |

`CalibrationStruct` / `CalibrationStructCFE` fields:

| Field | Description |
|-------|-------------|
| `Crc` | CRC of calibration data (firmware-computed) |
| `Vin[N]` | VIN channel calibrations (N=13 both variants) |
| `Vdd`, `Vref` | Supply and reference voltage calibrations |
| `Ts[N]` | Temperature sensor calibrations (N=4 ORIGINAL, N=8 CFE) |
| `TsB[N]` | Thermistor B-coefficient selection (0=TS_B_3950, 1=TS_B_3380) |
| `Tamb`, `Hum` | Ambient temperature and humidity calibrations |
| `PowerReadingVoltage[N]` | Power sensor voltage calibrations (N=11 ORIGINAL, N=23 CFE) |
| `PowerReadingCurrent[N]` | Power sensor current calibrations (N=11 ORIGINAL, N=23 CFE) |

Each `CalibrationValueStruct` entry has:
- `Offset` (`int16`): Additive offset in raw ADC units
- `GainOffset` (`int16`): Gain offset (Q12 fixed-point, multiplier = 4096)

- **`read_calibration(ser, product_id=None)`** → `Optional[Union[CalibrationStruct, CalibrationStructCFE]]`
  Reads the full calibration table from RAM. Selects the correct struct automatically.

- **`write_calibration(ser, calibration, product_id=None)`** → `bool`
  Writes the full calibration table to RAM in chunks (max 62 bytes per packet).

- **`write_calibration_chunk(ser, offset, chunk, product_id=None)`** → `bool`
  Writes a raw byte slice at a given offset. Used internally by `write_calibration()`.

- **`load_calibration(ser, cal_id)`** → `bool`
  Loads a calibration slot from flash into RAM. `CAL_FACTORY=0`, `CAL_USER=1`.

- **`store_calibration(ser, cal_id)`** → `bool`
  Saves the current RAM calibration to a flash slot. `CAL_FACTORY=0`, `CAL_USER=1`.

### Configuration — Actions

- **`send_action(ser, action, param1=0, param2=0, param3=0)`** → `bool`
  Sends a one-shot action. Action codes from `config.h`:
  `CONFIG_ACTION_SAVE=0`, `CONFIG_ACTION_LOAD=1`, `CONFIG_ACTION_RESET=2`.

### Sensor Data Format

`translate_sensor_struct()` returns a flat dictionary. Sensors marked **[CFE]** are only available on CFE devices.

#### Power Totals
- `SYS_Power`: Total system power (W)
- `CPU_Power`: CPU power — EPS1 + EPS2 (W)
- `GPU_Power`: GPU power — PCIE1 + PCIE2 + PCIE3 + HPWR1 + HPWR2 (W)
- `MB_Power`: Motherboard power — ATX3V + ATX5V + ATX5VSB + ATX12V (W)

#### Per-Rail Voltage / Current / Power

| Rail | Notes |
|------|-------|
| EPS1, EPS2 | All devices |
| ATX3V, ATX5V, ATX5VSB, ATX12V | All devices |
| PCIE1, PCIE2, PCIE3 | All devices |
| HPWR1, HPWR2 | All devices |
| HPWR1_W1–HPWR1_W6 | **[CFE]** |
| HPWR2_W1–HPWR2_W6 | **[CFE]** |

Each rail exposes `{Rail}_Voltage` (V), `{Rail}_Current` (A), `{Rail}_Power` (W).

#### Temperature & Humidity
- `Chip_Temp`: MCU chip temperature (°C)
- `Ambient_Temp`: Ambient temperature (°C)
- `Humidity`: Relative humidity (%)
- `TS_1`–`TS_4`: External temperature sensors (°C) — `None` if no sensor connected
- `TS_HPWR1_IN`, `TS_HPWR1_OUT`, `TS_HPWR2_IN`, `TS_HPWR2_OUT` — **[CFE]**

#### Fans (All Devices)
- `Fan1_Duty`–`Fan9_Duty`: Duty cycle (%)
- `Fan1_RPM`–`Fan9_RPM`: Speed (RPM)
- `Fan1_Status`–`Fan9_Status`: Enable status (0=off, 1=on)
- `FanExtDuty`: External fan duty cycle (%)

#### Voltage Inputs (All Devices)
- `VIN_0`–`VIN_12`: Additional voltage inputs (V)
- `Vdd`: Supply voltage (V)
- `Vref`: Reference voltage (V)

> Total sensor count: ~75 keys for ORIGINAL, ~127 keys for CFE.

## Integration Examples

### MQTT Telemetry Pipeline

```python
import serial
import paho.mqtt.client as mqtt
from benchlab_pycore.core import get_fleet_info, read_device, read_sensors, translate_sensor_struct

def publish_sensor_data(client, device_port):
    ser = serial.Serial(device_port, 115200, timeout=1)
    try:
        info = read_device(ser)
        pid = info['ProductId'] if info else None
        sensors = read_sensors(ser, product_id=pid)
        if sensors:
            data = translate_sensor_struct(sensors, product_id=pid)
            for key, value in data.items():
                topic = f"benchlab/{device_port}/{key}"
                client.publish(topic, value)
    finally:
        ser.close()

client = mqtt.Client()
client.connect("mqtt.example.com", 1883, 60)
for device in get_fleet_info():
    publish_sensor_data(client, device['port'])
```

### Data Logging to CSV

```python
import csv, serial, time
from benchlab_pycore.core import get_fleet_info, read_device, read_sensors, translate_sensor_struct

def log_device_data(device_port, duration_seconds=60, interval_seconds=1):
    filename = f"{device_port}_sensor_log.csv"
    ser = serial.Serial(device_port, 115200, timeout=1)
    info = read_device(ser)
    pid = info['ProductId'] if info else None

    with open(filename, 'w', newline='') as csvfile:
        writer = None
        start = time.time()
        while time.time() - start < duration_seconds:
            sensors = read_sensors(ser, product_id=pid)
            if sensors:
                data = translate_sensor_struct(sensors, product_id=pid)
                data['timestamp'] = time.time()
                if writer is None:
                    writer = csv.DictWriter(csvfile, fieldnames=list(data.keys()))
                    writer.writeheader()
                writer.writerow(data)
                csvfile.flush()
            time.sleep(interval_seconds)
    ser.close()

for device in get_fleet_info():
    log_device_data(device['port'], duration_seconds=300, interval_seconds=5)
```

## Requirements

- Python 3.8+
- pyserial >= 3.5

## Development

### Installation for Development

```bash
git clone https://github.com/BenchLab-io/benchlab-pycore.git
cd benchlab-pycore
pip install -e .
```

### Testing

**Unit tests:**
```bash
pip install pytest
python -m pytest tests/ -v
```

**Hardware tests (safe, read-only by default):**
```bash
python tests/test_device.py
```

**Hardware tests with write operations (requires confirmation for each write):**
```bash
python tests/test_device.py --destructive
```

**Interactive configuration tool:**
```bash
python tests/test_deviceConfig.py          # auto-detects device
python tests/test_deviceConfig.py COM4     # explicit port
```

### Building and Publishing

```bash
python -m build
python -m twine upload dist/*
```

## License

MIT License (c) 2025 BenchLab Contributors

## Support

For integration questions and support, please refer to the [BENCHLAB documentation](https://benchlab.io/docs) or contact the development team.