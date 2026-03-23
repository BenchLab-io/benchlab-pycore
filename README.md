# BENCHLAB Python Core (`benchlab-pycore`)

**BENCHLAB PyCore** provides low-level telemetry, sensor I/O, and device communication utilities
for BENCHLAB hardware devices. It includes standardized interfaces for reading sensors, handling serial communication, and translating raw sensor data into human-readable formats.

## Features

- **Device Discovery**: Automatically detect connected BENCHLAB devices
- **Sensor Data Reading**: Read raw sensor data including power, voltage, temperature, and fan information
- **Data Translation**: Convert raw sensor values to human-readable formats
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
from benchlab_pycore.core import get_fleet_info, read_sensors, translate_sensor_struct

# Discover all connected BENCHLAB devices
devices = get_fleet_info()
print(f"Found {len(devices)} device(s):")
for device in devices:
    print(f"  Port: {device['port']}, UID: {device['uid']}, Firmware: {device['firmware']}")

if devices:
    # Connect to the first device
    ser = serial.Serial(devices[0]['port'], 115200, timeout=1)
    
    # Read raw sensor data
    sensors = read_sensors(ser)
    if sensors:
        # Translate to human-readable format
        data = translate_sensor_struct(sensors)
        
        # Access sensor values
        print(f"CPU Power: {data['CPU_Power']}W")
        print(f"Chip Temperature: {data['Chip_Temp']} deg C")
        print(f"12V Voltage: {data['12V_Voltage']}V")
    
    ser.close()
```

### Advanced Usage with Error Handling

```python
import serial
from benchlab_pycore.core import get_benchlab_ports, read_sensors, translate_sensor_struct

def read_device_sensors(port):
    """Read sensors from a specific port with error handling."""
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        sensors = read_sensors(ser)
        ser.close()
        
        if sensors:
            return translate_sensor_struct(sensors)
        else:
            print(f"Failed to read sensors from {port}")
            return None
            
    except serial.SerialException as e:
        print(f"Failed to open port {port}: {e}")
        return None
    except Exception as e:
        print(f"Error reading from {port}: {e}")
        return None

# Find all BENCHLAB ports
ports = get_benchlab_ports()
print(f"Found {len(ports)} BENCHLAB port(s)")

# Read from each device
for port_info in ports:
    port = port_info['port']
    print(f"\nReading from {port}...")
    data = read_device_sensors(port)
    if data:
        print(f"  CPU Power: {data['CPU_Power']}W")
        print(f"  GPU Power: {data['GPU_Power']}W")
        print(f"  System Power: {data['SYS_Power']}W")
```

## API Reference

### Core Functions

#### Device Discovery

- **`get_benchlab_ports()`** → `List[Dict[str, str]]`
  - Returns all BENCHLAB COM ports without opening them
  - Returns list of dictionaries with 'port' key

- **`find_benchlab_devices()`** → `List[Dict[str, str]]`
  - Scans and returns all connected BENCHLAB devices
  - Returns list of dictionaries with 'port', 'uid', and 'fw' keys
  - Opens and closes serial connections to read device info

- **`get_fleet_info()`** → `List[Dict[str, Union[str, int]]]`
  - Returns all BENCHLAB devices with UID and firmware info
  - Returns list of dictionaries with 'port', 'firmware', and 'uid' keys

#### Serial Communication

- **`open_serial_connection(port: Optional[str])`** → `Optional[serial.Serial]`
  - Opens and returns a serial connection to the given port
  - Returns None if port is None or connection fails

- **`read_device(ser: serial.Serial)`** → `Optional[Dict[str, int]]`
  - Reads vendor information from the device
  - Returns dictionary with 'VendorId', 'ProductId', and 'FwVersion' keys

- **`read_sensors(ser: serial.Serial)`** → `Optional[SensorStruct]`
  - Reads all sensors from the device
  - Returns SensorStruct object containing raw sensor data

- **`read_uid(ser: serial.Serial, retries=3, delay=0.2)`** → `Optional[str]`
  - Reads device UID with optional retries
  - Returns device UID as uppercase hex string

#### Data Processing

- **`translate_sensor_struct(sensor_struct: SensorStruct)`** → `Dict[str, Any]`
  - Converts raw sensor data to human-readable format
  - Returns dictionary with formatted sensor values

### Sensor Data Format

The `translate_sensor_struct()` function returns a dictionary with the following keys:

#### Power Measurements
- `SYS_Power`: Total system power (W)
- `CPU_Power`: CPU power consumption (W)
- `GPU_Power`: GPU power consumption (W)
- `MB_Power`: Motherboard power consumption (W)

#### Voltage Measurements
- `EPS1_Voltage`, `EPS2_Voltage`: EPS power supply voltages (V)
- `12V_Voltage`, `5V_Voltage`, `5VSB_Voltage`, `3.3V_Voltage`: ATX voltages (V)
- `PCIE8_1_Voltage` through `HPWR2_Voltage`: PCIe and power connector voltages (V)
- `VIN_0` through `VIN_12`: Additional voltage inputs (V)
- `Vdd`, `Vref`: Reference voltages (V)

#### Current Measurements
- `EPS1_Current` through `HPWR2_Current`: Current measurements (A)

#### Power Measurements (per rail)
- `EPS1_Power` through `HPWR2_Power`: Power per rail (W)

#### Temperature Measurements
- `Chip_Temp`: Chip temperature (deg C)
- `Ambient_Temp`: Ambient temperature (deg C)
- `Temp_Sensor_1` through `Temp_Sensor_4`: Additional temperature sensors (deg C)
- `Humidity`: Relative humidity (%)

#### Fan Measurements
- `Fan1_Duty` through `Fan9_Duty`: Fan duty cycles (%)
- `Fan1_RPM` through `Fan9_RPM`: Fan speeds (RPM)
- `Fan1_Status` through `Fan9_Status`: Fan enable status
- `FanExtDuty`: External fan duty cycle (%)

## Integration Examples

### MQTT Telemetry Pipeline

```python
import serial
import paho.mqtt.client as mqtt
from benchlab_pycore.core import get_fleet_info, read_sensors, translate_sensor_struct

def publish_sensor_data(client, device_port):
    """Read and publish sensor data to MQTT."""
    try:
        ser = serial.Serial(device_port, 115200, timeout=1)
        sensors = read_sensors(ser)
        ser.close()
        
        if sensors:
            data = translate_sensor_struct(sensors)
            
            # Publish individual sensor values
            for key, value in data.items():
                topic = f"benchlab/{device_port.replace('COM', 'com')}/{key}"
                client.publish(topic, value)
                
    except Exception as e:
        print(f"Error publishing data from {device_port}: {e}")

# Setup MQTT client
client = mqtt.Client()
client.connect("mqtt.example.com", 1883, 60)

# Discover and monitor all devices
devices = get_fleet_info()
for device in devices:
    publish_sensor_data(client, device['port'])
```

### Data Logging to CSV

```python
import csv
import serial
import time
from benchlab_pycore.core import get_fleet_info, read_sensors, translate_sensor_struct

def log_device_data(device_port, duration_seconds=60, interval_seconds=1):
    """Log sensor data to CSV file."""
    filename = f"{device_port}_sensor_log.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = None
        writer = None
        
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            try:
                ser = serial.Serial(device_port, 115200, timeout=1)
                sensors = read_sensors(ser)
                ser.close()
                
                if sensors:
                    data = translate_sensor_struct(sensors)
                    data['timestamp'] = time.time()
                    
                    if fieldnames is None:
                        fieldnames = list(data.keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                    
                    writer.writerow(data)
                    csvfile.flush()
                
                time.sleep(interval_seconds)
                
            except Exception as e:
                print(f"Error logging data from {device_port}: {e}")
                time.sleep(interval_seconds)

# Log data from all devices
devices = get_fleet_info()
for device in devices:
    log_device_data(device['port'], duration_seconds=300, interval_seconds=5)
```

## Error Handling

The library provides comprehensive error handling for robust integration:

- **Serial Communication Errors**: Handled with appropriate exceptions and logging
- **Device Discovery Failures**: Graceful handling when no devices are found
- **Sensor Read Failures**: Returns None for failed reads with detailed logging
- **Data Translation Errors**: Validates sensor data before processing

### Best Practices

1. **Always check return values**: Functions may return None on failure
2. **Handle serial exceptions**: Use try-catch blocks when opening serial connections
3. **Implement timeouts**: Use appropriate timeouts for serial communication
4. **Log errors**: Use the built-in logging for debugging integration issues
5. **Validate data**: Check sensor data validity before processing

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

### Unit Tests

Run the comprehensive unit test suite:

```bash
pip install pytest
python -m pytest tests/ -v
```

### Device Testing

To verify that benchlab-pycore is working correctly with your physical BENCHLAB device, use the included device testing script:

```bash
# Run comprehensive device testing
python tests/test_device.py
```

This script will:
- ✅ Discover connected BENCHLAB devices
- ✅ Test serial communication
- ✅ Read vendor information and device UID
- ✅ Read and translate sensor data
- ✅ Validate sensor readings for reasonable ranges
- ✅ Provide detailed test results and troubleshooting information

**Example Output:**
```
 BENCHLAB DEVICE COMPREHENSIVE TEST
Testing benchlab-pycore library with physical hardware
 DEVICE DISCOVERY TEST
ℹ️  Testing port discovery...
✅ Found 1 BENCHLAB port(s)
  - COM3

ℹ️  Testing device discovery...
✅ Found 1 device(s)
  - Port: COM3
    UID: 123456789ABCDEF011223344
    Firmware: 1.0

ℹ️  Testing fleet information...
✅ Found 1 device(s) in fleet
  - Port: COM3
    UID: 123456789ABCDEF011223344
    Firmware: 1

 SERIAL CONNECTION TEST
ℹ️  Testing connection to COM3...
✅ Serial connection opened successfully

 VENDOR INFORMATION TEST
✅ Vendor info read successfully
  Vendor ID: 0xEE
  Product ID: 0x10
  Firmware Version: 1
✅ Device identification matches BENCHLAB specifications

 UID READING TEST
✅ UID read successfully: 123456789ABCDEF011223344
✅ UID format is valid

 SENSOR READING TEST
ℹ️  Reading raw sensor data...
✅ Raw sensor data read successfully
ℹ️  Translating sensor data...
✅ Sensor data translation successful

--- Key Sensor Values ---
  SYS_Power: 250.5
  CPU_Power: 120.0
  GPU_Power: 100.0
  MB_Power: 30.5
  Chip_Temp: 65.0
  Ambient_Temp: 22.5
  12V_Voltage: 12.05

--- Data Validation ---
✅ System power in reasonable range: 250.5W
✅ Chip temperature in reasonable range: 65.0 deg C
✅ 12V voltage in reasonable range: 12.05V

--- All Available Sensors (45 total) ---
  12V_Current: 10.5
  12V_Power: 126.6
  12V_Voltage: 12.05
  3.3V_Current: 2.1
  3.3V_Power: 6.9
  3.3V_Voltage: 3.3
  5V_Current: 4.2
  5V_Power: 21.0
  5V_Voltage: 5.0
  5VSB_Current: 0.8
  5VSB_Power: 4.0
  5VSB_Voltage: 5.0
  EPS1_Current: 10.0
  EPS1_Power: 120.0
  EPS1_Voltage: 12.0
  EPS2_Current: 10.0
  EPS2_Power: 120.0
  EPS2_Voltage: 12.0
  Fan1_Duty: 50
  Fan1_RPM: 1200
  Fan1_Status: 1
  Fan2_Duty: 60
  Fan2_RPM: 1400
  Fan2_Status: 1
  Fan3_Duty: 70
  Fan3_RPM: 1600
  Fan3_Status: 1
  Fan4_Duty: 80
  Fan4_RPM: 1800
  Fan4_Status: 1
  Fan5_Duty: 0
  Fan5_RPM: 0
  Fan5_Status: 0
  Fan6_Duty: 0
  Fan6_RPM: 0
  Fan6_Status: 0
  Fan7_Duty: 0
  Fan7_RPM: 0
  Fan7_Status: 0
  Fan8_Duty: 0
  Fan8_RPM: 0
  Fan8_Status: 0
  Fan9_Duty: 0
  Fan9_RPM: 0
  Fan9_Status: 0
  FanExtDuty: 0
  Humidity: 45.0
  MB_Power: 30.5
  SYS_Power: 250.5
  Temp_Sensor_1: 25.0
  Temp_Sensor_2: 26.0
  Temp_Sensor_3: 27.0
  Temp_Sensor_4: 28.0
  Vdd: 3.3
  Vref: 2.5
  VIN_0: 0.0
  VIN_1: 1.0
  VIN_10: 10.0
  VIN_11: 11.0
  VIN_12: 12.0
  VIN_2: 2.0
  VIN_3: 3.0
  VIN_4: 4.0
  VIN_5: 5.0
  VIN_6: 6.0
  VIN_7: 7.0
  VIN_8: 8.0
  VIN_9: 9.0

 TEST SUMMARY
Test Results:
  Device Discovery: ✅ PASS
  Serial Connection: ✅ PASS
  Vendor Info: ✅ PASS
  UID Reading: ✅ PASS
  Sensor Reading: ✅ PASS

🎉 ALL TESTS PASSED! Your BENCHLAB device is working correctly.
The benchlab-pycore library is ready for use.
```

**Sensor Reading Verification:**
The device test includes detailed logging of sensor readings with timestamps for verification of accuracy:

```
--- Key Sensor Values ---
  SYS_Power: 5.469
2026-03-23 09:46:37,793 [INFO] SENSOR_READING: SYS_Power = 5.469
  CPU_Power: 0.0
2026-03-23 09:46:37,793 [INFO] SENSOR_READING: CPU_Power = 0.0
  GPU_Power: 0.0
2026-03-23 09:46:37,793 [INFO] SENSOR_READING: GPU_Power = 0.0
  MB_Power: 5.469
2026-03-23 09:46:37,794 [INFO] SENSOR_READING: MB_Power = 5.469
  Chip_Temp: 36.0
2026-03-23 09:46:37,794 [INFO] SENSOR_READING: Chip_Temp = 36.0
  Ambient_Temp: 26.3
2026-03-23 09:46:37,794 [INFO] SENSOR_READING: Ambient_Temp = 26.3
  12V_Voltage: 0.0
2026-03-23 09:46:37,794 [INFO] SENSOR_READING: 12V_Voltage = 0.0
```

**TroubleshootingIf tests fail, common issues include:
- Device not properly connected via USB
- Missing or incorrect USB drivers
- Device firmware problems
- Serial port access permissions

The test script provides detailed error messages to help diagnose and resolve issues.

### Building and Publishing

```bash
# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

## License

MIT License (c) 2025 BenchLab Contributors

## Support

For integration questions and support, please refer to the [BENCHLAB documentation](https://benchlab.io/docs) or contact the development team.
