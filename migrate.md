# Migration Guide to benchlab-pycore v0.6.0

This guide covers breaking changes and new features introduced in each version.

---

## Migrating to v0.6.0

### Calibration slot ids are firmware-dependent (action required)

**If you call `store_calibration()` or `load_calibration()` with a raw integer
or with `CAL_FACTORY` / `CAL_USER`, read this before upgrading.**

The firmware swapped the numeric values of these two constants: in ORIGINAL
fw03 and BL2 fw04 they are the opposite of what they were in ORIGINAL fw02 and
BL2 fw03.

| Firmware | `CAL_FACTORY` | `CAL_USER` |
|---|---|---|
| ORIGINAL fw02, BL2 fw03 | 0 | 1 |
| ORIGINAL fw03, BL2 fw04 | **1** | **0** |

Previous releases hardcoded the older pair, and `cal_id` is written straight
onto the wire with no validation the device can reject. On current firmware
that means **`store_calibration(CAL_USER)` wrote to the factory slot.**

If you ran `store_calibration()` against fw03 (ORIGINAL) or fw04 (BL2) with an
affected release, your device's factory calibration slot may hold user data.
The factory values are not recoverable from the host -- contact support if you
need the device re-calibrated.

#### What to change

Name the slot instead of passing a number, and pass the device identity so the
value is resolved from that firmware's contract:

```python
from benchlab_pycore.core import read_device, store_calibration, CalSlot

info = read_device(ser)
store_calibration(ser, CalSlot.USER, info["ProductId"], info["FwVersion"])
```

Raw integers still work unchanged, so existing code keeps compiling -- but it
is only correct if you already know which firmware you are talking to. The
module-level `CAL_FACTORY` / `CAL_USER` now hold the *current* firmware's
values, so code that used them against current hardware is now correct, and
code that relied on the old values against old firmware is now wrong. Use
`CalSlot` and stop having to care.

Unknown `(ProductId, FwVersion)` pairs raise `UnknownFirmwareError` rather than
guessing, since guessing on a destructive path can cost the factory slot.

### Removed: device config / NVM / reset commands (breaking)

The six commands added in v0.5.1 for "forward compatibility with the intended
protocol" are removed, along with everything that supported them:

```python
# No longer available:
read_config, write_config, save_config, load_config, reset_config,
set_fan_duty, reset_device          # from benchlab_pycore.core.config_io
DeviceConfigStruct, BenchlabNvmCmd  # from benchlab_pycore.core.structures
```

`BENCHLAB_CMD` now ends at `UART_CMD_READ_VENDOR_DATA = 14`; the members
`UART_CMD_READ_CONFIG` (15) through `UART_CMD_BOOTLOADER` (20) are gone.

**Why:** no firmware implements them. The published wire contract stops at
command 14, which the v0.5.1 notes already acknowledged. The wire has no error
response, so calling one just times out. None of these names were exported from
`benchlab_pycore.core` or documented in the README, and their protocol details
(the CRC16 and the NVM write key) were transcribed from the C# reference and
never validated against a device — so if firmware does implement these
commands, this code would need rewriting rather than reviving.

`send_action()` is **not** affected: it uses `UART_CMD_ACTION` (command 2),
which firmware does implement, and remains the way to trigger save/load/reset
config actions.

**If you called any of these:** they could not have worked against real
hardware, so there is no working behaviour to preserve. Remove the calls.

### Firmware contracts are now vendored

`benchlab_pycore/contracts/` holds the machine-readable wire contracts
published by the firmware repo, and the test suite checks every ctypes struct
size and field offset against them. They are not used to decode at runtime --
the hand-written structures still do that -- so there is no behavioural change
and no new runtime dependency.

At import, struct sizes are checked against the contracts and a mismatch raises
`ContractMismatchError` instead of the previous bare `AssertionError`. This
check now also runs under `python -O`, where the old `assert` was stripped.

### `TempSrc` gained BL2's HPWR sources

`TempSrc` now includes `TS_HPWR1_IN`, `TS_HPWR1_OUT`, `TS_HPWR2_IN` and
`TS_HPWR2_OUT` (values 6-9). These are BL2 only; the ORIGINAL firmware stops
at `TAMB`. Existing members are unchanged.

### Firmware version constants

`BENCHLAB_BL2_FIRMWARE_VERSION` was the placeholder `0xFF` and was never read;
it is now `4`. `BENCHLAB_ORIGINAL_FIRMWARE_VERSION` moves from `2` to `3`. Both
now correspond to a real released firmware.

### Python 3.8 is no longer supported

The floor is now 3.9, where `importlib.resources.files()` is available
unconditionally. Python 3.8 reached end of life in October 2024.

---

## Migrating to v0.5.2

v0.5.2 is a non-breaking release. No code changes are required to upgrade.

### New in v0.5.2

Adds automated GitHub Actions workflows for running tests on pull requests
and publishing releases to PyPI on tagged pushes. No changes to library
behavior.

---

## Migrating to v0.5.1

v0.5.1 is a non-breaking release. No code changes are required to upgrade.

### New in v0.5.1

#### Device config / NVM / reset commands

Added Python wrappers for six previously-unavailable UART commands, matching
the protocol implemented in the BenchLab BL_Service (C#) reference:

```python
from benchlab_pycore.core.config_io import (
    read_config, write_config,
    save_config, load_config, reset_config,
    set_fan_duty,
    reset_device,
)
```

**Note:** as of this release, none of these six commands are implemented in
any currently shipping or in-development BENCHLAB firmware build. Calling
them against real hardware will fail (no response) until firmware support
lands. They are included now for forward compatibility with the intended
protocol.

#### Sensor sentinel handling fix

`translate_sensor_struct_original()` / `translate_sensor_struct_bl2()` now
return `None` for VIN and `FanExtDuty` readings when the firmware reports
its "sensor not populated" sentinel value (`0x7FFF` for VIN, `255` for
`FanExtDuty`), instead of passing the sentinel through as a literal value:

```python
# Before: a disabled VIN channel could report a nonsensical 32.767 V
# After:  a disabled VIN channel reports None

# Before: FanExtDuty could report 255 as if it were a real duty percentage
# After:  FanExtDuty reports None when the MCU has embedded control
```

`format_temp()` / `format_chip_temp()` also now check the `0x7FFF` sentinel
explicitly rather than relying on the incidental range-check fallback.

---

## Migrating to v0.5.0

v0.5.0 renames the BL2 variant's identifiers from `CFE` to `BL2` to match the
final SKU name (`BENCHLAB-2`, not `BENCHLAB-CFE`), and fixes several
correctness bugs found in a full review of the protocol, config I/O, and test
suite.

### Breaking Changes

#### CFE identifiers renamed to BL2

Every `CFE`/`cfe` identifier is renamed. The device itself was always the
same hardware — only the name changes:

```python
# Before
from benchlab_pycore.core import (
    SensorStructCFE, CalibrationStructCFE,
    BENCHLAB_CFE_PRODUCT_ID,
    translate_sensor_struct_cfe,
    SENSOR_VIN_NUM_CFE, SENSOR_POWER_NUM_CFE, SENSOR_TS_NUM_CFE,
    SENSOR_POWER_NAMES_CFE, SENSOR_TS_NAMES_CFE,
)

# After
from benchlab_pycore.core import (
    SensorStructBL2, CalibrationStructBL2,
    BENCHLAB_BL2_PRODUCT_ID,
    translate_sensor_struct_bl2,
    SENSOR_VIN_NUM_BL2, SENSOR_POWER_NUM_BL2, SENSOR_TS_NUM_BL2,
    SENSOR_POWER_NAMES_BL2, SENSOR_TS_NAMES_BL2,
)
```

The product-name string reported in logs and docstrings also changed from
`"BENCHLAB-CFE"` to `"BENCHLAB-2"`.

#### write_name() raises instead of silently truncating

Previously, a name longer than 30 UTF-8 bytes was silently truncated (and
could split a multi-byte character) while still returning `True`. It now
raises `ValueError` so callers can't mistake a truncated write for success:

```python
# Before
write_name(ser, very_long_name)  # -> True, but device got a truncated name

# After
write_name(ser, very_long_name)  # -> raises ValueError
```

#### find_benchlab_devices() dict key and protocol fix

`find_benchlab_devices()` previously spoke a nonstandard protocol and
returned firmware version under the key `"firmware"` despite its docstring
promising `"fw"`. It now uses the same UART protocol as the rest of the
library and returns `"fw"` as documented:

```python
devices = find_benchlab_devices()
devices[0]["fw"]  # now populated correctly; "firmware" key no longer exists
```

#### load_calibration() / store_calibration() cal_id documentation corrected

The docstrings previously had `cal_id` 0/1 backwards relative to the actual
`CAL_FACTORY=0` / `CAL_USER=1` constants. The code's behavior was always
correct — only the documented examples were wrong and have been fixed. If
you copied the docstring's (incorrect) example, double-check which slot
you're actually targeting.

---

## Migrating to v0.4.0

v0.4.0 adds full device configuration support — fan profiles, RGB profiles, calibration, and config persistence — along with struct corrections derived from the firmware headers of both ORIGINAL and BL2 devices.

### New in v0.4.0

#### Full configuration API

All firmware configuration commands now have Python functions:

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

#### Enums for all configuration fields

```python
from benchlab_pycore.core import (
    FanMode,       # TEMP_CONTROL=0, FIXED=1, EXT=2
    TempSrc,       # AUTO=0, TS1=1, TS2=2, TS3=3, TS4=4, TAMB=5
    FanStop,       # OFF=0, ON=1
    RGBMode,       # RAINBOW_CYCLE=0 … SINGLE_COLOR=9
    RGBDirection,  # CLOCKWISE=0, COUNTER_CLOCKWISE=1
)
```

#### CalibrationStruct for both variants

```python
from benchlab_pycore.core import CalibrationStruct, CalibrationStructBL2, CalibrationValueStruct
```

#### Interactive configuration tool

`tests/test_deviceConfig.py` provides a numbered-menu interactive tool for reading and writing all configuration on a live device. All write operations require explicit confirmation.

```bash
python tests/test_deviceConfig.py          # auto-detects device
python tests/test_deviceConfig.py COM4     # explicit port
```

#### Safer hardware test script

`tests/test_device.py` now runs read-only tests by default. Write tests require `--destructive` and prompt for confirmation before each write.

```bash
python tests/test_device.py                # safe, read-only
python tests/test_device.py --destructive  # write tests with confirmation prompts
```

---

## Migrating to v0.3.0

v0.3.0 added multi-variant device support for ORIGINAL and BL2 devices.

### Breaking Changes

#### SensorStruct renamed to SensorStructOriginal

```python
# Before
from benchlab_pycore.core import SensorStruct

# After
from benchlab_pycore.core import SensorStructOriginal
```

### New in v0.3.0

- `SensorStructBL2` for BL2 devices (23 power sensors, 8 temperature sensors)
- `translate_sensor_struct()` auto-detects variant from struct type or `product_id`
- `read_sensors(ser, product_id=...)` selects the correct struct for the connected device
- Variant-specific constants: `BENCHLAB_BL2_PRODUCT_ID`, `SENSOR_POWER_NUM_BL2`, etc.

---

## Full Changelog Summary

| Version | Key Changes |
|---------|-------------|
| v0.5.0 | CFE -> BL2 rename (matches final BENCHLAB-2 SKU name); write_name() raises on truncation instead of silently succeeding; find_benchlab_devices() protocol/key fix; calibration docstring corrections |
| v0.4.0 | Full config API; corrected FanConfigStruct, RGBConfigStruct, CalibrationStruct; enums; interactive tool; safer test script |
| v0.3.0 | BL2 multi-variant support; SensorStructOriginal / SensorStructBL2; translate dispatcher |

## Support

For issues or questions:
- [GitHub Issues](https://github.com/BenchLab-io/benchlab-pycore/issues)
- [BENCHLAB Documentation](https://benchlab.io/docs)