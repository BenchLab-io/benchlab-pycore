# Migration Guide to benchlab-pycore v0.4.0

This guide covers breaking changes and new features introduced in each version.

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
| v0.4.0 | Full config API; corrected FanConfigStruct, RGBConfigStruct, CalibrationStruct; enums; interactive tool; safer test script |
| v0.3.0 | BL2 multi-variant support; SensorStructOriginal / SensorStructBL2; translate dispatcher |

## Support

For issues or questions:
- [GitHub Issues](https://github.com/BenchLab-io/benchlab-pycore/issues)
- [BENCHLAB Documentation](https://benchlab.io/docs)