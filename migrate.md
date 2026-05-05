# Migration Guide to benchlab-pycore v0.3.0

This guide explains how to migrate your tools and applications to use benchlab-pycore v0.3.0. Version 0.3.0 introduces multi-variant device support, allowing the library to work with both the original BENCHLAB device and the extended BENCHLAB-CFE device.

## What's New in v0.3.0

### Multi-Variant Device Support

v0.3.0 adds support for two BENCHLAB device variants:

| Variant | Product ID | Description |
|---------|------------|-------------|
| **ORIGINAL** | `0x10` | Original BENCHLAB device with 11 power sensors, 4 temperature sensors |
| **CFE** | `0x11` | Extended BENCHLAB-CFE device with 23 power sensors, 8 temperature sensors |

### New Structures and Constants

The following new structures and constants are now available:

```python
from benchlab_pycore.core import (
    # CFE Variant Structures
    SensorStructCFE,
    BENCHLAB_CFE_PRODUCT_ID,
    BENCHLAB_CFE_FIRMWARE_VERSION,
    SENSOR_VIN_NUM_CFE,
    SENSOR_POWER_NUM_CFE,
    SENSOR_TS_NUM_CFE,
    SENSOR_POWER_NAMES_CFE,
    SENSOR_TS_NAMES_CFE,
    
    # ORIGINAL Variant (renamed for clarity)
    SensorStructOriginal,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    BENCHLAB_ORIGINAL_FIRMWARE_VERSION,
    SENSOR_VIN_NUM_ORIGINAL,
    SENSOR_POWER_NUM_ORIGINAL,
    SENSOR_TS_NUM_ORIGINAL,
    SENSOR_POWER_NAMES_ORIGINAL,
    SENSOR_TS_NAMES_ORIGINAL,
)
```

### Updated Translation Function

The `translate_sensor_struct()` function now automatically detects the device variant:

```python
from benchlab_pycore.core import read_sensors, translate_sensor_struct

# Automatically detects ORIGINAL or CFE variant
sensors = read_sensors(ser)
if sensors:
    data = translate_sensor_struct(sensors)  # Works with both variants
```

You can also explicitly specify the product ID:

```python
data = translate_sensor_struct(sensors, product_id=0x11)  # Force CFE translation
```

## Breaking Changes

### Structure Naming

If you were directly referencing `SensorStruct`, it has been renamed to `SensorStructOriginal` for clarity:

**Before (v0.2.x):**
```python
from benchlab_pycore.core import SensorStruct
```

**After (v0.3.0):**
```python
from benchlab_pycore.core import SensorStructOriginal
# Or use the generic translate_sensor_struct() which handles both
```

### Module Exports

The `__init__.py` now exports variant-specific constants and structures. Update your imports if you were relying on internal module paths.

## Migration Steps

### Step 1: Update Dependencies

Update your project to use benchlab-pycore v0.3.0:

```bash
pip install --upgrade benchlab-pycore
```

Or add to your `requirements.txt`:
```
benchlab-pycore>=0.3.0
```

### Step 2: Update Direct Structure References

If your code directly references `SensorStruct`, update it to use `SensorStructOriginal`:

```python
# Old
from benchlab_pycore.core import SensorStruct
if isinstance(data, SensorStruct):
    # ...

# New
from benchlab_pycore.core import SensorStructOriginal
if isinstance(data, SensorStructOriginal):
    # ...
```

### Step 3: Use the Dispatcher Function

Instead of calling variant-specific translation functions, use the main `translate_sensor_struct()` which auto-detects the variant:

```python
# Old (v0.2.x)
from benchlab_pycore.core import translate_sensor_struct
data = translate_sensor_struct(sensors)

# New (v0.3.0) - same API, but now supports both variants automatically
from benchlab_pycore.core import translate_sensor_struct
data = translate_sensor_struct(sensors)  # Auto-detects ORIGINAL or CFE
```

### Step 4: Handle New Sensor Fields (CFE devices)

If you're working with CFE devices, your code may need to handle additional sensor fields:

**Additional Power Sensors (CFE only):**
- `HPWR1_W1` through `HPWR1_W6`
- `HPWR2_W1` through `HPWR2_W6`

**Additional Temperature Sensors (CFE only):**
- `TS_HPWR1_IN`, `TS_HPWR1_OUT`
- `TS_HPWR2_IN`, `TS_HPWR2_OUT`

Example of handling variant-specific sensors:

```python
from benchlab_pycore.core import read_device, read_sensors, translate_sensor_struct, BENCHLAB_CFE_PRODUCT_ID

# Read device info to determine variant
device_info = read_device(ser)
if device_info and device_info['ProductId'] == BENCHLAB_CFE_PRODUCT_ID:
    print("CFE device detected - additional sensors available")
    
sensors = read_sensors(ser)
data = translate_sensor_struct(sensors)

# Access sensors that exist on all variants
print(f"CPU Power: {data['CPU_Power']}W")

# Access CFE-specific sensors (check if they exist)
if 'HPWR1_W1_Voltage' in data:
    print(f"CFE extended power sensor available")
```

### Step 5: Update Type Hints

If you use type hints, update them to accept both variant types:

```python
from typing import Union
from benchlab_pycore.core import SensorStructOriginal, SensorStructCFE

def process_sensors(sensors: Union[SensorStructOriginal, SensorStructCFE]) -> dict:
    # ...
```

## Code Examples

### Basic Usage (Both Variants)

```python
import serial
from benchlab_pycore.core import get_fleet_info, read_sensors, translate_sensor_struct

# Discover devices
devices = get_fleet_info()
for device in devices:
    ser = serial.Serial(device['port'], 115200, timeout=1)
    
    # Read and translate sensors (auto-detects variant)
    sensors = read_sensors(ser)
    if sensors:
        data = translate_sensor_struct(sensors)
        
        # Common sensors available on all variants
        print(f"System Power: {data['SYS_Power']}W")
        print(f"Chip Temp: {data['Chip_Temp']}°C")
        
    ser.close()
```

### Variant-Specific Handling

```python
from benchlab_pycore.core import (
    read_device, read_sensors, translate_sensor_struct,
    BENCHLAB_ORIGINAL_PRODUCT_ID, BENCHLAB_CFE_PRODUCT_ID
)

def read_all_sensor_data(ser):
    """Read sensor data with variant awareness."""
    device_info = read_device(ser)
    if not device_info:
        return None, None
    
    product_id = device_info['ProductId']
    variant = "ORIGINAL" if product_id == BENCHLAB_ORIGINAL_PRODUCT_ID else "CFE"
    
    sensors = read_sensors(ser)
    data = translate_sensor_struct(sensors, product_id=product_id)
    
    return variant, data

# Usage
variant, data = read_all_sensor_data(ser)
print(f"Device variant: {variant}")
print(f"Available sensors: {list(data.keys())}")
```

## FAQ

**Q: Will my existing code still work?**  
A: Yes, the `translate_sensor_struct()` function maintains backward compatibility. If you were using it with ORIGINAL devices, it will continue to work.

**Q: How do I know which variant I have?**  
A: Use `read_device()` to get the product ID, or check the `ProductId` field in the returned dictionary.

**Q: Can I still access raw sensor structures?**  
A: Yes, `read_sensors()` returns the appropriate structure type (`SensorStructOriginal` or `SensorStructCFE`) based on the connected device.

**Q: What if I need to support only one variant?**  
A: You can still use the same API. The library will auto-detect the variant and handle it appropriately.

## Support

For issues or questions, please refer to:
- [GitHub Issues](https://github.com/BenchLab-io/benchlab-pycore/issues)
- [BENCHLAB Documentation](https://benchlab.io/docs)