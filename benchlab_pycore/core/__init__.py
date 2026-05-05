# benchlab/core/__init__.py

from .serial_io import (
    get_benchlab_ports,
    find_benchlab_devices,
    get_fleet_info,
    read_uart,
    read_device,
    read_sensors,
    read_uid,
)
from .sensor_translation import (
    translate_sensor_struct,
    translate_sensor_struct_original,
    translate_sensor_struct_cfe,
)
from .structures import (
    # Shared structures
    VendorDataStruct,
    PowerSensor,
    FanSensor,
    BENCHLAB_CMD,
    # Shared constants
    BENCHLAB_VENDOR_ID,
    FAN_NUM,
    # ORIGINAL variant
    SensorStructOriginal,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    BENCHLAB_ORIGINAL_FIRMWARE_VERSION,
    SENSOR_VIN_NUM_ORIGINAL,
    SENSOR_POWER_NUM_ORIGINAL,
    SENSOR_TS_NUM_ORIGINAL,
    SENSOR_POWER_NAMES_ORIGINAL,
    SENSOR_TS_NAMES_ORIGINAL,
    # CFE variant
    SensorStructCFE,
    BENCHLAB_CFE_PRODUCT_ID,
    BENCHLAB_CFE_FIRMWARE_VERSION,
    SENSOR_VIN_NUM_CFE,
    SENSOR_POWER_NUM_CFE,
    SENSOR_TS_NUM_CFE,
    SENSOR_POWER_NAMES_CFE,
    SENSOR_TS_NAMES_CFE,
)
from .utils import format_temp, format_chip_temp

__all__ = [
    # serial_io
    "get_benchlab_ports",
    "find_benchlab_devices",
    "get_fleet_info",
    "read_uart",
    "read_device",
    "read_sensors",
    "read_uid",
    # sensor_translation
    "translate_sensor_struct",
    "translate_sensor_struct_original",
    "translate_sensor_struct_cfe",
    # Shared structures
    "VendorDataStruct",
    "PowerSensor",
    "FanSensor",
    "BENCHLAB_CMD",
    # Shared constants
    "BENCHLAB_VENDOR_ID",
    "FAN_NUM",
    # ORIGINAL variant
    "SensorStructOriginal",
    "BENCHLAB_ORIGINAL_PRODUCT_ID",
    "BENCHLAB_ORIGINAL_FIRMWARE_VERSION",
    "SENSOR_VIN_NUM_ORIGINAL",
    "SENSOR_POWER_NUM_ORIGINAL",
    "SENSOR_TS_NUM_ORIGINAL",
    "SENSOR_POWER_NAMES_ORIGINAL",
    "SENSOR_TS_NAMES_ORIGINAL",
    # CFE variant
    "SensorStructCFE",
    "BENCHLAB_CFE_PRODUCT_ID",
    "BENCHLAB_CFE_FIRMWARE_VERSION",
    "SENSOR_VIN_NUM_CFE",
    "SENSOR_POWER_NUM_CFE",
    "SENSOR_TS_NUM_CFE",
    "SENSOR_POWER_NAMES_CFE",
    "SENSOR_TS_NAMES_CFE",
    # utils
    "format_temp",
    "format_chip_temp",
]