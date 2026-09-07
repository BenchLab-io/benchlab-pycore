"""
Sensor data translation for BENCHLAB device variants.

This module provides functions to translate raw sensor data structures
into human-readable dictionaries suitable for CSV export, graphs, MQTT, etc.

Each device variant has its own dedicated translation function that handles
the specific sensor counts and naming conventions for that variant.
"""

from typing import Dict, Any, Union

from .structures import (
    # Original variant constants and structures
    SENSOR_VIN_NUM_ORIGINAL,
    SENSOR_POWER_NUM_ORIGINAL,
    SENSOR_TS_NUM_ORIGINAL,
    SENSOR_POWER_NAMES_ORIGINAL,
    SENSOR_TS_NAMES_ORIGINAL,
    SensorStructOriginal,

    # BL2 variant constants and structures
    SENSOR_VIN_NUM_BL2,
    SENSOR_POWER_NUM_BL2,
    SENSOR_TS_NUM_BL2,
    SENSOR_POWER_NAMES_BL2,
    SENSOR_TS_NAMES_BL2,
    SensorStructBL2,

    # Product IDs for variant detection
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    BENCHLAB_BL2_PRODUCT_ID,
)
from .utils import format_chip_temp, format_temp


# =============================================================================
# Dispatcher Function
# =============================================================================

def translate_sensor_struct(
    sensor_struct: Union[SensorStructOriginal, SensorStructBL2],
    product_id: int = None,
    fw_version: int = None,
) -> Dict[str, Any]:
    """Return a flat dict of interpreted sensor values suitable for CSV, graphs, MQTT, etc.

    This function automatically detects the sensor structure type and dispatches
    to the appropriate variant-specific translator.

    Args:
        sensor_struct: Raw sensor data from read_sensors(). Can be either
                      SensorStructOriginal or SensorStructBL2.
        product_id: Optional product ID to help with variant detection.
                   If provided, takes precedence over type detection.

    Returns:
        Dict[str, Any]: Dictionary containing human-readable sensor values.

    Example:
        >>> from benchlab_pycore.core import read_sensors, translate_sensor_struct
        >>> ser = serial.Serial('COM3', 115200)
        >>> sensors = read_sensors(ser)
        >>> if sensors:
        >>>     data = translate_sensor_struct(sensors)
        >>>     print(f"CPU Power: {data['CPU_Power']}W")
    """
    # Use product_id for detection if provided
    if product_id == BENCHLAB_BL2_PRODUCT_ID:
        return translate_sensor_struct_bl2(sensor_struct, product_id, fw_version)
    elif product_id == BENCHLAB_ORIGINAL_PRODUCT_ID:
        return translate_sensor_struct_original(sensor_struct, product_id, fw_version)

    # Fall back to type-based detection
    if isinstance(sensor_struct, SensorStructBL2):
        return translate_sensor_struct_bl2(sensor_struct, product_id, fw_version)

    return translate_sensor_struct_original(sensor_struct, product_id, fw_version)


# =============================================================================
# ORIGINAL Variant Translation
# =============================================================================

def translate_sensor_struct_original(
    sensor_struct: SensorStructOriginal,
    product_id: int = None,
    fw_version: int = None,
) -> Dict[str, Any]:
    """Translate ORIGINAL BENCHLAB device sensor data to human-readable dictionary.

    Handles:
    - 11 power sensors with standard naming
    - 4 temperature sensors (TS_1 through TS_4)
    - 9 fans

    Args:
        sensor_struct: Raw sensor data from ORIGINAL device.

    Returns:
        Dictionary with translated sensor values.
    """
    data = {}
    power = sensor_struct.PowerReadings

    # ---- Power Calculations ----
    power_cpu = (power[0].Power + power[1].Power) / 1000
    power_gpu = sum(power[i].Power for i in range(6, 11)) / 1000
    power_mb = sum(power[i].Power for i in range(2, 6)) / 1000
    power_system = power_cpu + power_gpu + power_mb
    data.update({
        "SYS_Power": power_system,
        "CPU_Power": power_cpu,
        "GPU_Power": power_gpu,
        "MB_Power": power_mb,
    })

    # ---- Individual Power Sensor Readings ----
    for i in range(SENSOR_POWER_NUM_ORIGINAL):
        name = SENSOR_POWER_NAMES_ORIGINAL[i]
        data[f"{name}_Voltage"] = power[i].Voltage / 1000
        data[f"{name}_Current"] = power[i].Current / 1000
        data[f"{name}_Power"] = power[i].Power / 1000

    # ---- VIN Sensors ----
    for i in range(SENSOR_VIN_NUM_ORIGINAL):
        raw = sensor_struct.Vin[i]
        data[f"VIN_{i}"] = None if raw == 0x7FFF else raw / 1000
    data["Vdd"] = sensor_struct.Vdd / 1000
    data["Vref"] = sensor_struct.Vref / 1000

    # ---- Temperature Sensors ----
    data["Chip_Temp"] = format_chip_temp(sensor_struct.Tchip, product_id, fw_version)
    data["Ambient_Temp"] = format_temp(sensor_struct.Tamb)
    data["Humidity"] = sensor_struct.Hum / 10
    for i in range(SENSOR_TS_NUM_ORIGINAL):
        data[SENSOR_TS_NAMES_ORIGINAL[i]] = format_temp(sensor_struct.Ts[i])

    # ---- Fan Sensors ----
    for i, f in enumerate(sensor_struct.Fans):
        data[f"Fan{i+1}_Duty"] = f.Duty
        data[f"Fan{i+1}_RPM"] = f.Tach
        data[f"Fan{i+1}_Status"] = f.Enable
    data["FanExtDuty"] = None if sensor_struct.FanExtDuty == 255 else sensor_struct.FanExtDuty

    return data


# =============================================================================
# BL2 Variant Translation
# =============================================================================

def translate_sensor_struct_bl2(
    sensor_struct: SensorStructBL2,
    product_id: int = None,
    fw_version: int = None,
) -> Dict[str, Any]:
    """Translate BENCHLAB-2 device sensor data to human-readable dictionary.

    Handles:
    - 23 power sensors (12 more than original, with HPWR1_W1-6 and HPWR2_W1-6)
    - 8 temperature sensors (4 more than original, with HPWR1/HPWR2 IN/OUT)
    - 9 fans (same as original)

    SYS_Power is the sum of CPU, GPU, and MB power only. The HPWR wire
    sensors (HPWR1_W1-6 at indices 11-16, HPWR2_W1-6 at indices 17-22)
    are sub-measurements of HPWR1/HPWR2 and are excluded to avoid
    double-counting.

    Args:
        sensor_struct: Raw sensor data from BL2 device.

    Returns:
        Dictionary with translated sensor values.
    """
    data = {}
    power = sensor_struct.PowerReadings

    # ---- Power Calculations ----
    # Core subsystem power (same indices as ORIGINAL)
    power_cpu = (power[0].Power + power[1].Power) / 1000
    power_gpu = sum(power[i].Power for i in range(6, 11)) / 1000
    power_mb = sum(power[i].Power for i in range(2, 6)) / 1000

    # Note: HPWR wire sensors (indices 11-22) are sub-measurements of HPWR1/HPWR2
    # (indices 9-10) and are intentionally excluded from SYS_Power to avoid
    # double-counting. They are still available individually in the output dict.
    power_system = power_cpu + power_gpu + power_mb
    data.update({
        "SYS_Power": power_system,
        "CPU_Power": power_cpu,
        "GPU_Power": power_gpu,
        "MB_Power": power_mb,
    })

    # ---- Individual Power Sensor Readings ----
    for i in range(SENSOR_POWER_NUM_BL2):
        name = SENSOR_POWER_NAMES_BL2[i]
        data[f"{name}_Voltage"] = power[i].Voltage / 1000
        data[f"{name}_Current"] = power[i].Current / 1000
        data[f"{name}_Power"] = power[i].Power / 1000

    # ---- VIN Sensors ----
    for i in range(SENSOR_VIN_NUM_BL2):
        raw = sensor_struct.Vin[i]
        data[f"VIN_{i}"] = None if raw == 0x7FFF else raw / 1000
    data["Vdd"] = sensor_struct.Vdd / 1000
    data["Vref"] = sensor_struct.Vref / 1000

    # ---- Temperature Sensors (all 8 sensors) ----
    data["Chip_Temp"] = format_chip_temp(sensor_struct.Tchip, product_id, fw_version)
    data["Ambient_Temp"] = format_temp(sensor_struct.Tamb)
    data["Humidity"] = sensor_struct.Hum / 10
    for i in range(SENSOR_TS_NUM_BL2):
        data[SENSOR_TS_NAMES_BL2[i]] = format_temp(sensor_struct.Ts[i])

    # ---- Fan Sensors ----
    for i, f in enumerate(sensor_struct.Fans):
        data[f"Fan{i+1}_Duty"] = f.Duty
        data[f"Fan{i+1}_RPM"] = f.Tach
        data[f"Fan{i+1}_Status"] = f.Enable
    data["FanExtDuty"] = None if sensor_struct.FanExtDuty == 255 else sensor_struct.FanExtDuty

    return data