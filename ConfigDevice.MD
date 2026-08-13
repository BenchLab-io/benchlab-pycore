# BENCHLAB Device Configuration Commands

This document is a comprehensive reference for all device configuration commands in `benchlab-pycore` v0.4.0. These commands allow you to read and write fan profiles, RGB profiles, calibration data, and device identification over USB CDC serial.

## Table of Contents

- [Overview](#overview)
- [UART Command Protocol](#uart-command-protocol)
- [Friendly Name](#friendly-name)
- [Fan Profiles](#fan-profiles)
- [RGB Profiles](#rgb-profiles)
- [Calibration](#calibration)
- [Config Actions](#config-actions)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Overview

Configuration commands are implemented in `benchlab_pycore.core.config_io`. Import them directly:

```python
from benchlab_pycore.core import (
    ping,
    read_name, write_name,
    read_fan_profile, write_fan_profile,
    read_rgb_profile, write_rgb_profile,
    read_calibration, write_calibration, write_calibration_chunk,
    load_calibration, store_calibration,
    send_action,
)
```

Or import the supporting structures and constants:

```python
from benchlab_pycore.core import (
    # Fan config
    FanConfigStruct, FanMode, TempSrc, FanStop,
    FAN_PROFILE_NUM, FAN_NUM, FAN_CURVE_POINTS,

    # RGB config
    RGBConfigStruct, RGBMode, RGBDirection,
    RGB_PROFILE_NUM,

    # Calibration
    CalibrationStruct,       # ORIGINAL — 178 bytes
    CalibrationStructBL2,    # BL2      — 294 bytes
    CalibrationValueStruct,

    # Constants
    CAL_NUM, CAL_FACTORY, CAL_USER,
    FRIENDLY_NAME_LEN,
)
```

## UART Command Protocol

Each configuration command maps to a UART command code in `BENCHLAB_CMD`:

| Command | Code | Function(s) |
|---------|------|-------------|
| `UART_CMD_WELCOME` | 0 | `ping()` |
| `UART_CMD_ACTION` | 2 | `send_action()` |
| `UART_CMD_READ_NAME` | 3 | `read_name()` |
| `UART_CMD_WRITE_NAME` | 4 | `write_name()` |
| `UART_CMD_READ_FAN_PROFILE` | 5 | `read_fan_profile()` |
| `UART_CMD_WRITE_FAN_PROFILE` | 6 | `write_fan_profile()` |
| `UART_CMD_READ_RGB` | 7 | `read_rgb_profile()` |
| `UART_CMD_WRITE_RGB` | 8 | `write_rgb_profile()` |
| `UART_CMD_READ_CALIBRATION` | 9 | `read_calibration()` |
| `UART_CMD_WRITE_CALIBRATION` | 10 | `write_calibration_chunk()`, `write_calibration()` |
| `UART_CMD_LOAD_CALIBRATION` | 11 | `load_calibration()` |
| `UART_CMD_STORE_CALIBRATION` | 12 | `store_calibration()` |

The firmware CDC handler accepts at most one command per USB transfer. All library functions flush the input buffer before sending (`reset_input_buffer()`) and wait 50ms after writing before reading, to ensure the firmware has finished processing.

## Friendly Name

A user-configurable string of up to 31 UTF-8 characters that identifies the device. Stored as 32 bytes (null-padded) in `DeviceConfigStruct.FriendlyName`.

### Read

```python
name = read_name(ser)
print(f"Device name: {name!r}")
```

### Write

```python
write_name(ser, "My BENCHLAB")
```

Names longer than 31 characters are silently truncated. The firmware does not send an ACK — `True` means the bytes were sent successfully.

## Fan Profiles

Each device has `FAN_PROFILE_NUM=3` profile slots and `FAN_NUM=9` fan channels, giving 27 independently configurable entries.

### FanConfigStruct

`FanConfigStruct` is 14 bytes packed (includes one trailing padding byte from the C compiler):

| Field | Type | Description |
|-------|------|-------------|
| `FanMode` | `uint8` | Control mode — see `FanMode` enum |
| `TempSource` | `uint8` | Temperature sensor source — see `TempSrc` enum |
| `Temp[2]` | `int16[2]` | Temperature breakpoints in **tenths of °C** (e.g. 300 = 30.0°C) |
| `Duty[2]` | `uint8[2]` | Duty cycle at each breakpoint (0–100%) |
| `RampStep` | `uint8` | Maximum duty-cycle change per control tick |
| `FixedDuty` | `uint8` | Duty cycle used when `FanMode = FIXED` (0–100%) |
| `MinDuty` | `uint8` | Minimum allowed duty cycle (0–100%) |
| `MaxDuty` | `uint8` | Maximum allowed duty cycle (0–100%) |
| `FanStop` | `uint8` | Allow fan to stop below MinDuty — see `FanStop` enum |

**`FanMode` enum:**

| Value | Name | Description |
|-------|------|-------------|
| 0 | `TEMP_CONTROL` | Follow temperature curve (`Temp`/`Duty` breakpoints) |
| 1 | `FIXED` | Run at `FixedDuty` permanently |
| 2 | `EXT` | Controlled by external signal |

**`TempSrc` enum:**

| Value | Name |
|-------|------|
| 0 | `AUTO` |
| 1–4 | `TS1`–`TS4` |
| 5 | `TAMB` |

**`FanStop` enum:** `OFF=0`, `ON=1`

### Read

```python
cfg = read_fan_profile(ser, fan_profile=0, fan_id=0)
if cfg:
    print(f"FanMode={cfg.FanMode}  FixedDuty={cfg.FixedDuty}%")
    print(f"Curve: {cfg.Temp[0]/10:.1f}°C→{cfg.Duty[0]}%  "
          f"{cfg.Temp[1]/10:.1f}°C→{cfg.Duty[1]}%")
```

### Write

```python
from benchlab_pycore.core import FanConfigStruct, FanMode

cfg = FanConfigStruct()
cfg.FanMode    = FanMode.TEMP_CONTROL
cfg.TempSource = 1        # TS1
cfg.Temp[0]    = 250      # 25.0°C
cfg.Duty[0]    = 20       # 20%
cfg.Temp[1]    = 400      # 40.0°C
cfg.Duty[1]    = 100      # 100%
cfg.RampStep   = 2
cfg.FixedDuty  = 50
cfg.MinDuty    = 20
cfg.MaxDuty    = 100
cfg.FanStop    = 0

write_fan_profile(ser, fan_profile=0, fan_id=0, config=cfg)
```

## RGB Profiles

Each device has `RGB_PROFILE_NUM=2` profile slots.

### RGBConfigStruct

`RGBConfigStruct` is 6 bytes packed:

| Field | Type | Description |
|-------|------|-------------|
| `Mode` | `uint8` | LED effect — see `RGBMode` enum |
| `Red` | `uint8` | Red component 0–255 |
| `Green` | `uint8` | Green component 0–255 |
| `Blue` | `uint8` | Blue component 0–255 |
| `Direction` | `uint8` | Animation direction — see `RGBDirection` enum |
| `Speed` | `uint8` | Animation speed |

**`RGBMode` enum:**

| Value | Name |
|-------|------|
| 0 | `RAINBOW_CYCLE` |
| 1 | `RAINBOW_COLOR_CHASE` |
| 2 | `RAINBOW` |
| 3 | `TWINKLE` |
| 4 | `METEOR_SHOWER` |
| 5 | `COLOR_WIPE` |
| 6 | `THEATRE_CHASE` |
| 7 | `FADE_IN_OUT` |
| 8 | `SINGLE_COLOR_CHASE` |
| 9 | `SINGLE_COLOR` |

**`RGBDirection` enum:** `CLOCKWISE=0`, `COUNTER_CLOCKWISE=1`

### Read

```python
rgb = read_rgb_profile(ser, rgb_profile=0)
if rgb:
    print(f"Mode={rgb.Mode} R={rgb.Red} G={rgb.Green} B={rgb.Blue}")
```

`None` means the firmware returned no data for that slot (slot not initialised).

### Write

```python
from benchlab_pycore.core import RGBConfigStruct, RGBMode

rgb = RGBConfigStruct()
rgb.Mode      = RGBMode.SINGLE_COLOR
rgb.Red       = 0
rgb.Green     = 255
rgb.Blue      = 0
rgb.Direction = 0
rgb.Speed     = 10

write_rgb_profile(ser, rgb_profile=0, config=rgb)
```

## Calibration

Calibration adjusts sensor readings. The struct layout is **device-scoped** — ORIGINAL and BL2 have different sizes because they have different sensor counts.

| Variant | Struct | Size |
|---------|--------|------|
| ORIGINAL | `CalibrationStruct` | 178 bytes |
| BL2 | `CalibrationStructBL2` | 294 bytes |

Pass `product_id` to all calibration functions so the correct struct is selected automatically.

### CalibrationStruct layout

Both variants share the same field structure, scaled to their respective sensor counts:

| Field | ORIGINAL | BL2 |
|-------|----------|-----|
| `Crc` | `uint16` | `uint16` |
| `Vin[N]` | N=13 | N=13 |
| `Vdd`, `Vref` | 1 each | 1 each |
| `Ts[N]` | N=4 | N=8 |
| `TsB[N]` (thermistor B-coefficient) | N=4 | N=8 |
| `Tamb`, `Hum` | 1 each | 1 each |
| `PowerReadingVoltage[N]` | N=11 | N=23 |
| `PowerReadingCurrent[N]` | N=11 | N=23 |

Each `CalibrationValueStruct` entry:
- `Offset` (`int16`): Additive offset in raw ADC units
- `GainOffset` (`int16`): Multiplicative gain offset (Q12 fixed-point, `CAL_MUL=4096`)

The `Crc` field is computed by the firmware. Do not set it manually — it is updated automatically when calibration is stored to flash via `store_calibration()`.

### Read

```python
cal = read_calibration(ser, product_id=product_id)
if cal:
    print(f"CRC:  0x{cal.Crc:04X}")
    print(f"Vdd:  Offset={cal.Vdd.Offset}  GainOffset={cal.Vdd.GainOffset}")
    for i, v in enumerate(cal.Vin):
        print(f"Vin[{i}]: Offset={v.Offset}  GainOffset={v.GainOffset}")
```

### Write (RAM only)

```python
# Read current, modify, write back
cal = read_calibration(ser, product_id=product_id)
if cal:
    cal.Vin[0].Offset = 10
    write_calibration(ser, cal, product_id=product_id)
```

`write_calibration()` splits the struct into 62-byte chunks automatically. Changes are in RAM only until `store_calibration()` is called.

### Persist to flash

```python
from benchlab_pycore.core import CAL_FACTORY, CAL_USER

# Save current RAM calibration to user slot
store_calibration(ser, CAL_USER)     # cal_id = 1

# Restore factory calibration into RAM (does not persist)
load_calibration(ser, CAL_FACTORY)   # cal_id = 0

# Save factory cal over user slot (recovery procedure)
store_calibration(ser, CAL_USER)
```

> **Warning:** `store_calibration(ser, CAL_FACTORY)` overwrites the factory calibration slot permanently. Only do this if you have a verified calibration to write.

## Config Actions

`send_action()` triggers one-shot device actions defined in `config.h`:

| `action` | Constant | Effect |
|----------|----------|--------|
| 0 | `CONFIG_ACTION_SAVE` | Save config (name, fan, RGB) to flash |
| 1 | `CONFIG_ACTION_LOAD` | Reload config from flash |
| 2 | `CONFIG_ACTION_RESET` | Reset config to firmware defaults |

```python
send_action(ser, action=0)   # save config to flash
send_action(ser, action=1)   # reload config from flash
send_action(ser, action=2)   # reset to defaults
```

> **Note:** `CONFIG_ACTION_RESET` resets name, fan profiles, and RGB profiles only. It does not touch calibration. Use `load_calibration(ser, CAL_FACTORY)` to restore calibration defaults.

## Error Handling

All read functions return `None` on failure. All write functions return `bool` (`True` = bytes sent, no firmware ACK). `ValueError` is raised for out-of-range arguments.

```python
cfg = read_fan_profile(ser, fan_profile=0, fan_id=0)
if cfg is None:
    print("Read failed — check connection and product_id")

try:
    read_fan_profile(ser, fan_profile=99, fan_id=0)
except ValueError as e:
    print(e)   # "fan_profile must be 0–2, got 99"
```

## Examples

### Complete Configuration Workflow

```python
import serial
from benchlab_pycore.core import (
    read_device, read_name, write_name,
    read_fan_profile, write_fan_profile,
    read_rgb_profile, write_rgb_profile,
    read_calibration, write_calibration, store_calibration,
    FanConfigStruct, FanMode, RGBConfigStruct, RGBMode,
    CAL_USER, BENCHLAB_BL2_PRODUCT_ID,
    send_action,
)

ser = serial.Serial("COM4", 115200, timeout=1)

info = read_device(ser)
product_id = info['ProductId']

# Name
print(f"Name: {read_name(ser)}")
write_name(ser, "My BENCHLAB")

# Fan — set all fans to FIXED 50% in profile 0
cfg = FanConfigStruct()
cfg.FanMode   = FanMode.FIXED
cfg.FixedDuty = 50
cfg.MinDuty   = 20
cfg.MaxDuty   = 100
cfg.RampStep  = 5
for fan_id in range(9):
    write_fan_profile(ser, fan_profile=0, fan_id=fan_id, config=cfg)

# RGB — solid red
rgb = RGBConfigStruct()
rgb.Mode  = RGBMode.SINGLE_COLOR
rgb.Red   = 255
rgb.Green = 0
rgb.Blue  = 0
write_rgb_profile(ser, rgb_profile=0, config=rgb)

# Save config to flash
send_action(ser, action=0)

ser.close()
```

### Calibration Backup and Restore

```python
import json, serial
from benchlab_pycore.core import (
    read_device, read_calibration, write_calibration, store_calibration, CAL_USER,
)

def backup_calibration(ser, product_id, filename):
    cal = read_calibration(ser, product_id=product_id)
    if not cal:
        return False
    data = {
        'Crc':  cal.Crc,
        'Vdd':  {'Offset': cal.Vdd.Offset,  'GainOffset': cal.Vdd.GainOffset},
        'Vref': {'Offset': cal.Vref.Offset, 'GainOffset': cal.Vref.GainOffset},
        'Tamb': {'Offset': cal.Tamb.Offset, 'GainOffset': cal.Tamb.GainOffset},
        'Hum':  {'Offset': cal.Hum.Offset,  'GainOffset': cal.Hum.GainOffset},
        'Vin':  [{'Offset': v.Offset, 'GainOffset': v.GainOffset} for v in cal.Vin],
        'Ts':   [{'Offset': v.Offset, 'GainOffset': v.GainOffset} for v in cal.Ts],
        'TsB':  list(cal.TsB),
        'PowerReadingVoltage': [{'Offset': v.Offset, 'GainOffset': v.GainOffset}
                                for v in cal.PowerReadingVoltage],
        'PowerReadingCurrent': [{'Offset': v.Offset, 'GainOffset': v.GainOffset}
                                for v in cal.PowerReadingCurrent],
    }
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Calibration backed up to {filename}")
    return True

ser = serial.Serial("COM4", 115200, timeout=1)
info = read_device(ser)
backup_calibration(ser, info['ProductId'], "cal_backup.json")
ser.close()
```

## See Also

- [README.md](README.md) — Main library documentation
- [migrate.md](migrate.md) — Migration guide