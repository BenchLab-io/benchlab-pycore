"""
Core structures, enums, and constants for BENCHLAB device variants.

All structures are derived directly from the firmware header (benchlab.h)
and are packed to match the STM32 memory layout exactly.

Variants:
    - ORIGINAL: The original BENCHLAB device (Product ID: 0x10)
    - BL2: The extended BENCHLAB-2 device (Product ID: 0x11)
"""

from ctypes import Structure, c_uint8, c_uint16, c_int16, c_int32
from enum import IntEnum

# =============================================================================
# Shared Constants
# =============================================================================
BENCHLAB_VENDOR_ID = 0xEE
FAN_NUM = 9

# =============================================================================
# ORIGINAL Variant Constants
# =============================================================================
BENCHLAB_ORIGINAL_PRODUCT_ID       = 0x10
BENCHLAB_ORIGINAL_FIRMWARE_VERSION = 0x03   # FIRMWARE_VERSION in benchlab.h

SENSOR_VIN_NUM_ORIGINAL   = 13   # SENSOR_VIN_NUM
SENSOR_POWER_NUM_ORIGINAL = 11   # SENSOR_POWER_NUM
SENSOR_TS_NUM_ORIGINAL    = 4    # TS_NUM

SENSOR_POWER_NAMES_ORIGINAL = [
    "EPS1", "EPS2", "ATX3V", "ATX5V", "ATX5VSB", "ATX12V",
    "PCIE1", "PCIE2", "PCIE3", "HPWR1", "HPWR2",
]

SENSOR_TS_NAMES_ORIGINAL = ["TS_1", "TS_2", "TS_3", "TS_4"]

# =============================================================================
# BL2 Variant Constants
# =============================================================================
BENCHLAB_BL2_PRODUCT_ID       = 0x11
BENCHLAB_BL2_FIRMWARE_VERSION = 0x04   # FIRMWARE_VERSION in benchlab.h

SENSOR_VIN_NUM_BL2   = 13
SENSOR_POWER_NUM_BL2 = 23
SENSOR_TS_NUM_BL2    = 8

SENSOR_POWER_NAMES_BL2 = [
    "EPS1", "EPS2", "ATX3V", "ATX5V", "ATX5VSB", "ATX12V",
    "PCIE1", "PCIE2", "PCIE3", "HPWR1", "HPWR2",
    "HPWR1_W1", "HPWR1_W2", "HPWR1_W3", "HPWR1_W4", "HPWR1_W5", "HPWR1_W6",
    "HPWR2_W1", "HPWR2_W2", "HPWR2_W3", "HPWR2_W4", "HPWR2_W5", "HPWR2_W6",
]

SENSOR_TS_NAMES_BL2 = [
    "TS_1", "TS_2", "TS_3", "TS_4",
    "TS_HPWR1_IN", "TS_HPWR1_OUT", "TS_HPWR2_IN", "TS_HPWR2_OUT",
]

# =============================================================================
# Shared Sensor Structures
# =============================================================================

class VendorDataStruct(Structure):
    """Vendor identification — VendorDataStruct in benchlab.h."""
    _fields_ = [
        ('VendorId',  c_uint8),
        ('ProductId', c_uint8),
        ('FwVersion', c_uint8),
    ]


class PowerSensor(Structure):
    """Power sensor reading — PowerSensor in benchlab.h."""
    _fields_ = [
        ('Voltage', c_int16),
        ('Current', c_int32),
        ('Power',   c_int32),
    ]


class FanSensor(Structure):
    """Fan sensor reading — FanSensor in benchlab.h."""
    _fields_ = [
        ('Enable', c_uint8),
        ('Duty',   c_uint8),
        ('Tach',   c_uint16),
    ]


class SensorStructOriginal(Structure):
    """Sensor data for ORIGINAL BENCHLAB — SensorStruct in benchlab.h."""
    _fields_ = [
        ('Vin',             c_int16  * SENSOR_VIN_NUM_ORIGINAL),
        ('Vdd',             c_uint16),
        ('Vref',            c_uint16),
        ('Tchip',           c_int16),
        ('Ts',              c_int16  * SENSOR_TS_NUM_ORIGINAL),
        ('Tamb',            c_int16),
        ('Hum',             c_uint16),
        ('FanSwitchStatus', c_uint8),
        ('RGBSwitchStatus', c_uint8),
        ('RgbExtStatus',    c_uint8),
        ('FanExtDuty',      c_uint8),
        ('PowerReadings',   PowerSensor * SENSOR_POWER_NUM_ORIGINAL),
        ('Fans',            FanSensor   * FAN_NUM),
    ]


class SensorStructBL2(Structure):
    """Sensor data for BENCHLAB-2 (extended variant)."""
    _fields_ = [
        ('Vin',             c_int16  * SENSOR_VIN_NUM_BL2),
        ('Vdd',             c_uint16),
        ('Vref',            c_uint16),
        ('Tchip',           c_int16),
        ('Ts',              c_int16  * SENSOR_TS_NUM_BL2),
        ('Tamb',            c_int16),
        ('Hum',             c_uint16),
        ('FanSwitchStatus', c_uint8),
        ('RGBSwitchStatus', c_uint8),
        ('RgbExtStatus',    c_uint8),
        ('FanExtDuty',      c_uint8),
        ('PowerReadings',   PowerSensor * SENSOR_POWER_NUM_BL2),
        ('Fans',            FanSensor   * FAN_NUM),
    ]


# =============================================================================
# UART Command Enum
# =============================================================================

class BENCHLAB_CMD(IntEnum):
    """UART commands — UART_CMD enum in usbd_cdc_if.c."""
    UART_CMD_WELCOME          = 0
    UART_CMD_READ_SENSORS     = 1
    UART_CMD_ACTION           = 2
    UART_CMD_READ_NAME        = 3
    UART_CMD_WRITE_NAME       = 4
    UART_CMD_READ_FAN_PROFILE = 5
    UART_CMD_WRITE_FAN_PROFILE= 6
    UART_CMD_READ_RGB         = 7
    UART_CMD_WRITE_RGB        = 8
    UART_CMD_READ_CALIBRATION = 9
    UART_CMD_WRITE_CALIBRATION= 10
    UART_CMD_LOAD_CALIBRATION = 11
    UART_CMD_STORE_CALIBRATION= 12
    UART_CMD_READ_UID         = 13
    UART_CMD_READ_VENDOR_DATA = 14
    # Ends at 14, matching the firmware contract. Commands 15-20 (READ_CONFIG,
    # WRITE_CONFIG, NVM_CONFIG, WRITE_FAN_DUTY, RESET, BOOTLOADER) were ported
    # speculatively from the C# reference and are implemented by no firmware;
    # they were removed in v0.6.0. See migrate.md.

    def toByte(self):
        return self.value.to_bytes(1, 'little')


# =============================================================================
# Configuration Constants
# =============================================================================

FAN_PROFILE_NUM    = 3    # FAN_PROFILE_NUM  in benchlab.h
RGB_PROFILE_NUM    = 2    # RGB_PROFILE_NUM  in benchlab.h
CAL_NUM            = 2    # CAL_NUM          in benchlab.h

# WARNING: the numeric values of CAL_FACTORY and CAL_USER are NOT stable across
# firmware versions -- they swapped in fw03 (ORIGINAL) and fw04 (BL2):
#
#     firmware              CAL_FACTORY   CAL_USER
#     ORIGINAL fw02, BL2 fw03      0          1
#     ORIGINAL fw03, BL2 fw04      1          0
#
# These module-level names are bound to the *current* firmware's values for
# backwards compatibility. Passing them to a device running older firmware
# targets the wrong slot, and because storing is destructive that means
# overwriting the factory calibration. Prefer the CalSlot enum with
# resolve_cal_slot(), which reads the correct value from that device's
# contract; see load_calibration()/store_calibration() in config_io.py.
CAL_FACTORY        = 1    # CAL_FACTORY      in benchlab.h (current firmware)
CAL_USER           = 0    # CAL_USER         in benchlab.h (current firmware)


class CalSlot(IntEnum):
    """Which calibration slot to act on, independent of its wire value.

    The wire value differs by firmware version, so name the slot and let
    resolve_cal_slot() supply the number for the device in hand.
    """
    FACTORY = 0
    USER    = 1


def resolve_cal_slot(slot, product_id, fw_version):
    """Wire value for *slot* on the firmware a device is actually running.

    Args:
        slot:       A CalSlot member.
        product_id: ProductId as reported by read_device().
        fw_version: FwVersion as reported by read_device().

    Returns:
        The integer this firmware uses for that slot.

    Raises:
        UnknownFirmwareError: If no contract matches the pair. Refusing is
            deliberate: guessing here can overwrite factory calibration.
    """
    from .contract import contract_for
    name = "CAL_FACTORY" if CalSlot(slot) is CalSlot.FACTORY else "CAL_USER"
    return contract_for(product_id, fw_version).constant(name)
FRIENDLY_NAME_LEN  = 32   # CONFIG_STR_LEN   in benchlab.h
FAN_CURVE_POINTS   = 2    # FAN_CURVE_NUM_POINTS in benchlab.h


# =============================================================================
# Fan Configuration — FanConfigStruct in benchlab.h
# =============================================================================

class FanMode(IntEnum):
    """FAN_MODE enum in benchlab.h."""
    TEMP_CONTROL = 0   # FAN_MODE_TEMP_CONTROL
    FIXED        = 1   # FAN_MODE_FIXED
    EXT          = 2   # FAN_MODE_EXT


class TempSrc(IntEnum):
    """TEMP_SRC enum in benchlab.h.

    Values 6-9 are BL2 only; the ORIGINAL variant's firmware stops at TAMB.
    Selecting an HPWR source on an ORIGINAL device is not meaningful.
    """
    AUTO          = 0   # TEMP_SRC_AUTO
    TS1           = 1   # TEMP_SRC_TS1
    TS2           = 2   # TEMP_SRC_TS2
    TS3           = 3   # TEMP_SRC_TS3
    TS4           = 4   # TEMP_SRC_TS4
    TAMB          = 5   # TEMP_SRC_TAMB
    TS_HPWR1_IN   = 6   # TEMP_SRC_TS_HPWR1_IN  (BL2 only)
    TS_HPWR1_OUT  = 7   # TEMP_SRC_TS_HPWR1_OUT (BL2 only)
    TS_HPWR2_IN   = 8   # TEMP_SRC_TS_HPWR2_IN  (BL2 only)
    TS_HPWR2_OUT  = 9   # TEMP_SRC_TS_HPWR2_OUT (BL2 only)


class FanStop(IntEnum):
    """FAN_STOP enum in benchlab.h."""
    OFF = 0   # FAN_STOP_OFF
    ON  = 1   # FAN_STOP_ON


class FanConfigStruct(Structure):
    """Fan profile for one channel — FanConfigStruct in benchlab.h.

    Total size: 14 bytes (packed).  The C compiler appends one padding byte
    after FanStop due to struct alignment before it is stored in the
    DeviceConfigStruct array, and the firmware transmits sizeof(FanConfigStruct)
    bytes verbatim, so the trailing byte is always present on the wire.

    Attributes:
        FanMode:    Control mode (see FanMode enum).
        TempSource: Temperature sensor driving the curve (see TempSrc enum).
        Temp:       Two temperature breakpoints in tenths of °C.
        Duty:       Duty cycle (0–100) at each breakpoint.
        RampStep:   Max duty-cycle change per control tick.
        FixedDuty:  Duty used in FIXED mode.
        MinDuty:    Minimum allowed duty cycle.
        MaxDuty:    Maximum allowed duty cycle.
        FanStop:    Whether to allow fan stop below MinDuty (see FanStop enum).
    """
    _fields_ = [
        ('FanMode',    c_uint8),
        ('TempSource', c_uint8),
        ('Temp',       c_int16 * FAN_CURVE_POINTS),
        ('Duty',       c_uint8 * FAN_CURVE_POINTS),
        ('RampStep',   c_uint8),
        ('FixedDuty',  c_uint8),
        ('MinDuty',    c_uint8),
        ('MaxDuty',    c_uint8),
        ('FanStop',    c_uint8),
    ]


# =============================================================================
# RGB Configuration — RGBConfigStruct in benchlab.h
# =============================================================================

class RGBMode(IntEnum):
    """RGB_MODE enum in benchlab.h."""
    RAINBOW_CYCLE       = 0
    RAINBOW_COLOR_CHASE = 1
    RAINBOW             = 2
    TWINKLE             = 3
    METEOR_SHOWER       = 4
    COLOR_WIPE          = 5
    THEATRE_CHASE       = 6
    FADE_IN_OUT         = 7
    SINGLE_COLOR_CHASE  = 8
    SINGLE_COLOR        = 9


class RGBDirection(IntEnum):
    """RGB_DIRECTION enum in benchlab.h."""
    CLOCKWISE         = 0
    COUNTER_CLOCKWISE = 1


class RGBConfigStruct(Structure):
    """RGB LED profile — RGBConfigStruct in benchlab.h.

    Total size: 6 bytes (packed).

    Attributes:
        Mode:      LED effect (see RGBMode enum).
        Red:       Red component 0–255.
        Green:     Green component 0–255.
        Blue:      Blue component 0–255.
        Direction: Animation direction (see RGBDirection enum).
        Speed:     Animation speed.
    """
    _fields_ = [
        ('Mode',      c_uint8),
        ('Red',       c_uint8),
        ('Green',     c_uint8),
        ('Blue',      c_uint8),
        ('Direction', c_uint8),
        ('Speed',     c_uint8),
    ]


# =============================================================================
# Calibration — CalibrationStruct in benchlab.h
# =============================================================================

class CalibrationValueStruct(Structure):
    """Calibration coefficients for one channel — CalibrationValueStruct in benchlab.h.

    Attributes:
        Offset:     Additive offset in raw ADC units.
        GainOffset: Multiplicative gain offset (Q12 fixed-point, per CAL_MUL=4096).
    """
    _fields_ = [
        ('Offset',     c_int16),
        ('GainOffset', c_int16),
    ]


class CalibrationStruct(Structure):
    """Full calibration table for ORIGINAL BENCHLAB — CalibrationStruct in benchlab.h.

    Total size: 178 bytes (packed).

    Attributes:
        Crc:                   CRC of the calibration data (firmware-computed).
        Vin:                   13 VIN channel calibrations.
        Vdd:                   Vdd calibration.
        Vref:                  Vref calibration.
        Ts:                    4 external temperature sensor calibrations.
        TsB:                   Thermistor B-coefficient selection per Ts channel
                               (0 = TS_B_3950, 1 = TS_B_3380).
        Tamb:                  Ambient temperature calibration.
        Hum:                   Humidity calibration.
        PowerReadingVoltage:   11 power sensor voltage calibrations.
        PowerReadingCurrent:   11 power sensor current calibrations.
    """
    _fields_ = [
        ('Crc',                 c_uint16),
        ('Vin',                 CalibrationValueStruct * SENSOR_VIN_NUM_ORIGINAL),
        ('Vdd',                 CalibrationValueStruct),
        ('Vref',                CalibrationValueStruct),
        ('Ts',                  CalibrationValueStruct * SENSOR_TS_NUM_ORIGINAL),
        ('TsB',                 c_uint8 * SENSOR_TS_NUM_ORIGINAL),
        ('Tamb',                CalibrationValueStruct),
        ('Hum',                 CalibrationValueStruct),
        ('PowerReadingVoltage', CalibrationValueStruct * SENSOR_POWER_NUM_ORIGINAL),
        ('PowerReadingCurrent', CalibrationValueStruct * SENSOR_POWER_NUM_ORIGINAL),
    ]


class CalibrationStructBL2(Structure):
    """Full calibration table for BENCHLAB-2.

    Same layout as CalibrationStruct but scaled to BL2 sensor counts.
    Total size: 294 bytes (packed).
    """
    _fields_ = [
        ('Crc',                 c_uint16),
        ('Vin',                 CalibrationValueStruct * SENSOR_VIN_NUM_BL2),
        ('Vdd',                 CalibrationValueStruct),
        ('Vref',                CalibrationValueStruct),
        ('Ts',                  CalibrationValueStruct * SENSOR_TS_NUM_BL2),
        ('TsB',                 c_uint8 * SENSOR_TS_NUM_BL2),
        ('Tamb',                CalibrationValueStruct),
        ('Hum',                 CalibrationValueStruct),
        ('PowerReadingVoltage', CalibrationValueStruct * SENSOR_POWER_NUM_BL2),
        ('PowerReadingCurrent', CalibrationValueStruct * SENSOR_POWER_NUM_BL2),
    ]


# =============================================================================
# Import-time compatibility check
#
# Struct sizes are read from the vendored firmware contracts rather than a
# hardcoded table, so this cannot drift from the firmware silently. It is
# deliberately cheap: sizes only, and only the current firmware of each
# variant. Full per-field offset verification against every contract is the
# test suite's job (tests/test_contract.py), not an import-time cost.
#
# This raises rather than asserts, so it still fires under `python -O`.
# =============================================================================

from ctypes import sizeof as _sizeof

from .contract import ContractMismatchError as _ContractMismatchError
from .contract import contract_for as _contract_for


def _verify_struct_sizes():
    """Compare each variant's structs against its current firmware contract.

    DeviceConfigStruct is deliberately absent: it belongs to the speculative
    READ_CONFIG/WRITE_CONFIG commands that no released firmware implements, so
    no contract describes it and there is nothing to check it against.
    """
    checks = [
        (BENCHLAB_ORIGINAL_PRODUCT_ID, BENCHLAB_ORIGINAL_FIRMWARE_VERSION, {
            "VendorDataStruct": VendorDataStruct,
            "PowerSensor": PowerSensor,
            "FanSensor": FanSensor,
            "FanConfigStruct": FanConfigStruct,
            "RGBConfigStruct": RGBConfigStruct,
            "CalibrationValueStruct": CalibrationValueStruct,
            "SensorStruct": SensorStructOriginal,
            "CalibrationStruct": CalibrationStruct,
        }),
        (BENCHLAB_BL2_PRODUCT_ID, BENCHLAB_BL2_FIRMWARE_VERSION, {
            "SensorStruct": SensorStructBL2,
            "CalibrationStruct": CalibrationStructBL2,
        }),
    ]

    for product_id, fw_version, structs in checks:
        contract = _contract_for(product_id, fw_version)
        for name, cls in structs.items():
            actual = _sizeof(cls)
            expected = contract.struct_size(name)
            if actual != expected:
                raise _ContractMismatchError(
                    "Struct size mismatch for {}: {} bytes, but {} in the "
                    "firmware contract says {} bytes. Check _pack_ settings "
                    "and field layout, or re-vendor the contracts with "
                    "tools/sync_contracts.py.".format(
                        cls.__name__, actual, contract.filename, expected)
                )


_verify_struct_sizes()

del _sizeof, _verify_struct_sizes