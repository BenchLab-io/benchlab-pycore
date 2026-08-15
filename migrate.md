# Migration Guide to benchlab-pycore v0.5.2

This guide covers breaking changes and new features introduced in each version.

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