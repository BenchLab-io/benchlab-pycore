"""
Core structures, enums, and constants for BENCHLAB device variants.

This module defines the data structures and constants for all supported
BENCHLAB device variants. Each variant has its own set of constants
and sensor structures.

Variants:
    - ORIGINAL: The original BENCHLAB device (Product ID: 0x10)
    - CFE: The extended BENCHLAB-CFE device (Product ID: 0x11)
"""

from ctypes import Structure, c_uint8, c_uint16, c_int16, c_int32
from enum import IntEnum

# =============================================================================
# Shared Constants
# =============================================================================
BENCHLAB_VENDOR_ID = 0xEE
FAN_NUM = 9  # Same for all variants

# =============================================================================
# ORIGINAL Variant Constants
# =============================================================================
BENCHLAB_ORIGINAL_PRODUCT_ID = 0x10
BENCHLAB_ORIGINAL_FIRMWARE_VERSION = 0x01
SENSOR_VIN_NUM_ORIGINAL = 13
SENSOR_POWER_NUM_ORIGINAL = 11
SENSOR_TS_NUM_ORIGINAL = 4

# Original power sensor names (indices 0-10)
SENSOR_POWER_NAMES_ORIGINAL = [
    "EPS1", "EPS2", "ATX3V", "ATX5V", "ATX5VSB", "ATX12V",
    "PCIE1", "PCIE2", "PCIE3", "HPWR1", "HPWR2",
]

# Original temperature sensor names (indices 0-3)
SENSOR_TS_NAMES_ORIGINAL = [
    "TS_1", "TS_2", "TS_3", "TS_4",
]

# =============================================================================
# CFE Variant Constants
# =============================================================================
BENCHLAB_CFE_PRODUCT_ID = 0x11
BENCHLAB_CFE_FIRMWARE_VERSION = 0xFF
SENSOR_VIN_NUM_CFE = 13
SENSOR_POWER_NUM_CFE = 23
SENSOR_TS_NUM_CFE = 8

# CFE power sensor names (indices 0-22)
SENSOR_POWER_NAMES_CFE = [
    "EPS1", "EPS2", "ATX3V", "ATX5V", "ATX5VSB", "ATX12V",
    "PCIE1", "PCIE2", "PCIE3", "HPWR1", "HPWR2",
    "HPWR1_W1", "HPWR1_W2", "HPWR1_W3", "HPWR1_W4", "HPWR1_W5", "HPWR1_W6",
    "HPWR2_W1", "HPWR2_W2", "HPWR2_W3", "HPWR2_W4", "HPWR2_W5", "HPWR2_W6",
]

# CFE temperature sensor names (indices 0-7)
SENSOR_TS_NAMES_CFE = [
    "TS_1", "TS_2", "TS_3", "TS_4",
    "TS_HPWR1_IN", "TS_HPWR1_OUT", "TS_HPWR2_IN", "TS_HPWR2_OUT",
]

# =============================================================================
# Shared Structures (used by all variants)
# =============================================================================

class VendorDataStruct(Structure):
    """Vendor identification data structure (same for all variants)."""
    _fields_ = [
        ('VendorId', c_uint8),
        ('ProductId', c_uint8),
        ('FwVersion', c_uint8),
    ]


class PowerSensor(Structure):
    """Power sensor reading structure (same for all variants)."""
    _fields_ = [
        ('Voltage', c_int16),
        ('Current', c_int32),
        ('Power', c_int32),
    ]


class FanSensor(Structure):
    """Fan sensor reading structure (same for all variants)."""
    _fields_ = [
        ('Enable', c_uint8),
        ('Duty', c_uint8),
        ('Tach', c_uint16),
    ]


# =============================================================================
# Variant-Specific Sensor Structures
# =============================================================================

class SensorStructOriginal(Structure):
    """Sensor data structure for ORIGINAL BENCHLAB device.
    
    Supports:
    - 13 VIN sensors
    - 11 power sensors
    - 4 temperature sensors (Ts)
    - 9 fans
    """
    _fields_ = [
        ('Vin', c_int16 * SENSOR_VIN_NUM_ORIGINAL),
        ('Vdd', c_uint16),
        ('Vref', c_uint16),
        ('Tchip', c_int16),
        ('Ts', c_int16 * SENSOR_TS_NUM_ORIGINAL),
        ('Tamb', c_int16),
        ('Hum', c_int16),
        ('FanSwitchStatus', c_uint8),
        ('RGBSwitchStatus', c_uint8),
        ('RGBExtStatus', c_uint8),
        ('FanExtDuty', c_uint8),
        ('PowerReadings', PowerSensor * SENSOR_POWER_NUM_ORIGINAL),
        ('Fans', FanSensor * FAN_NUM),
    ]


class SensorStructCFE(Structure):
    """Sensor data structure for BENCHLAB-CFE device.
    
    Supports:
    - 13 VIN sensors
    - 23 power sensors (12 more than original)
    - 8 temperature sensors (4 more than original)
    - 9 fans
    """
    _fields_ = [
        ('Vin', c_int16 * SENSOR_VIN_NUM_CFE),
        ('Vdd', c_uint16),
        ('Vref', c_uint16),
        ('Tchip', c_int16),
        ('Ts', c_int16 * SENSOR_TS_NUM_CFE),
        ('Tamb', c_int16),
        ('Hum', c_int16),
        ('FanSwitchStatus', c_uint8),
        ('RGBSwitchStatus', c_uint8),
        ('RGBExtStatus', c_uint8),
        ('FanExtDuty', c_uint8),
        ('PowerReadings', PowerSensor * SENSOR_POWER_NUM_CFE),
        ('Fans', FanSensor * FAN_NUM),
    ]


# =============================================================================
# UART Command Enum (same for all variants)
# =============================================================================

class BENCHLAB_CMD(IntEnum):
    """UART commands supported by all BENCHLAB device variants."""
    UART_CMD_WELCOME = 0
    UART_CMD_READ_SENSORS = 1
    UART_CMD_ACTION = 2
    UART_CMD_READ_NAME = 3
    UART_CMD_WRITE_NAME = 4
    UART_CMD_READ_FAN_PROFILE = 5
    UART_CMD_WRITE_FAN_PROFILE = 6
    UART_CMD_READ_RGB = 7
    UART_CMD_WRITE_RGB = 8
    UART_CMD_READ_CALIBRATION = 9
    UART_CMD_WRITE_CALIBRATION = 10
    UART_CMD_LOAD_CALIBRATION = 11
    UART_CMD_STORE_CALIBRATION = 12
    UART_CMD_READ_UID = 13
    UART_CMD_READ_VENDOR_DATA = 14

    def toByte(self):
        return self.value.to_bytes(1, 'little')