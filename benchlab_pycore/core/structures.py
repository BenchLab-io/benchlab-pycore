"""
Core structures, enums, and constants for BENCHLAB device variants.

All structures are derived directly from the firmware header (benchlab.h)
and are packed to match the STM32 memory layout exactly.

Variants:
    - ORIGINAL: The original BENCHLAB device (Product ID: 0x10)
    - BL2: The extended BENCHLAB-2 device (Product ID: 0x11)
"""

from ctypes import Structure, c_uint8, c_uint16, c_int16, c_int32, c_uint64, c_char
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
BENCHLAB_ORIGINAL_FIRMWARE_VERSION = 0x05   # FIRMWARE_VERSION in benchlab.h

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
BENCHLAB_BL2_FIRMWARE_VERSION = 0x06   # FIRMWARE_VERSION in benchlab.h

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

FAULT_NUM        = 34   # FAULT_NUM in benchlab.h (BL2 only)
FAULT_ACTION_NUM = 6    # FAULT_ACTION_NUM in benchlab.h (BL2 only)


class Fault(IntEnum):
    """FAULT enum in benchlab.h — indexes FaultConfigStruct.MaxLimit/MinDuration
    and the SensorStructBL2.FaultStatus/FaultLog bitmasks. BL2 only."""
    OTP_TCHIP                    = 0
    OTP_TS1                      = 1
    OTP_TS2                      = 2
    OTP_TS3                      = 3
    OTP_TS4                      = 4
    OTP_TS_HPWR1_IN               = 5
    OTP_TS_HPWR1_OUT              = 6
    OTP_TS_HPWR2_IN               = 7
    OTP_TS_HPWR2_OUT              = 8
    OCP_CPU1                      = 9
    OCP_CPU2                      = 10
    OCP_ATX3V                     = 11
    OCP_ATX5V                     = 12
    OCP_ATX5VSB                   = 13
    OCP_ATX12V                    = 14
    OCP_GPU1                       = 15
    OCP_GPU2                       = 16
    OCP_GPU3                       = 17
    OCP_HPWR1                      = 18
    OCP_HPWR2                      = 19
    WIRE_OCP_HPWR1_WIRE1           = 20
    WIRE_OCP_HPWR1_WIRE2           = 21
    WIRE_OCP_HPWR1_WIRE3           = 22
    WIRE_OCP_HPWR1_WIRE4           = 23
    WIRE_OCP_HPWR1_WIRE5           = 24
    WIRE_OCP_HPWR1_WIRE6           = 25
    WIRE_OCP_HPWR2_WIRE1           = 26
    WIRE_OCP_HPWR2_WIRE2           = 27
    WIRE_OCP_HPWR2_WIRE3           = 28
    WIRE_OCP_HPWR2_WIRE4           = 29
    WIRE_OCP_HPWR2_WIRE5           = 30
    WIRE_OCP_HPWR2_WIRE6           = 31
    CURRENT_IMBALANCE_HPWR1        = 32
    CURRENT_IMBALANCE_HPWR2        = 33


class FaultAction(IntEnum):
    """FAULT_ACTION enum in benchlab.h — indexes FaultConfigStruct.ActionEnable/
    ActionWaitTime. BL2 only."""
    LED         = 0
    BUZZER      = 1
    SOFT_POWER  = 2
    HARD_POWER  = 3
    RESET       = 4
    FIVE_VSB_POWER = 5

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


class SensorStructBL2Legacy(Structure):
    """Sensor data for BENCHLAB-2, pre-fw05 (368 bytes, no fault fields).

    BL2 fw03/fw04 send this shorter layout -- READ_SENSORS did not grow
    FaultStatus/FaultLog until fw05. read_sensors() selects this class for
    those older firmware versions; a device still running one would
    otherwise get a short read against the newer 384-byte SensorStructBL2.
    """
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


class SensorStructBL2(Structure):
    """Sensor data for BENCHLAB-2, fw05+ (extended variant).

    FaultStatus/FaultLog were added in fw05 — bitmasks over the Fault enum,
    one bit per FAULT_NUM member. FaultStatus is the live fault state;
    FaultLog is the latched (sticky) history. See SensorStructBL2Legacy for
    the pre-fw05 (368-byte) layout.
    """
    _fields_ = SensorStructBL2Legacy._fields_ + [
        ('FaultStatus',     c_uint64),
        ('FaultLog',        c_uint64),
    ]


# fw05 is the first BL2 firmware to send FaultStatus/FaultLog on READ_SENSORS.
BENCHLAB_BL2_SENSOR_FAULT_FIELDS_FROM = 5


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
    UART_CMD_READ_FAULT          = 15   # BENCHLAB 2 only; fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_WRITE_FAULT         = 16   # BENCHLAB 2 only; fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_LOAD_CONFIG         = 17   # fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_STORE_CONFIG        = 18   # fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_READ_DEFAULT_CONFIG = 19   # fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_STATUS              = 20   # fw05 (ORIGINAL)/fw06 (BL2)
    UART_CMD_RESET               = 0xF0
    UART_CMD_BOOTLOADER          = 0xF1
    UART_CMD_NOP                 = 0xFF
    # NOP is reserved in COMMAND_ID but has no dispatch handler on any
    # released firmware; sending it is a no-op that STATUS reports as
    # UNKNOWN_OPCODE. Declared for contract completeness; config_io has no
    # function for it since there is nothing useful to do with it.

    def toByte(self):
        return self.value.to_bytes(1, 'little')


class CommandStatus(IntEnum):
    """COMMAND_STATUS enum in benchlab.h -- the single-byte response to
    STATUS (0x14), describing the outcome of the *previous* command handled
    on the shared dispatcher, not of STATUS itself."""
    OK              = 0
    BAD_LENGTH      = 1
    BAD_PARAMETER   = 2
    UNKNOWN_OPCODE  = 3
    BUSY            = 4


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


# =============================================================================
# Fault Configuration — FaultConfigStruct in benchlab.h (BENCHLAB 2 only)
# =============================================================================

class FaultConfigStruct(Structure):
    """Fault-protection configuration — FaultConfigStruct in benchlab.h.

    Payload of READ_FAULT (0x0F) / WRITE_FAULT (0x10). BENCHLAB 2 only; frozen
    in fw06 (see benchlab2/v0.6.1). Total size: 128 bytes (8-byte aligned by
    the uint64 array).

    Attributes:
        ActionEnable:   One 64-bit bitmask per FaultAction, bit N set means
                         that action fires on Fault(N).
        ActionWaitTime: Per-action wait time, in 1000 ms intervals.
        MaxLimit:       Per-fault trip threshold, indexed by Fault
                         (0.1V/0.5A/1degC/10W units depending on fault type).
        MinDuration:    Per-fault minimum duration before tripping, indexed
                         by Fault, in 1000 ms intervals.
    """
    _fields_ = [
        ('ActionEnable',   c_uint64 * FAULT_ACTION_NUM),
        ('ActionWaitTime', c_uint8  * FAULT_ACTION_NUM),
        ('MaxLimit',       c_uint8  * FAULT_NUM),
        ('MinDuration',    c_uint8  * FAULT_NUM),
    ]


# =============================================================================
# Device Configuration — DeviceConfigStruct in benchlab.h
#
# ORIGINAL fw05 / BL2 fw06 shipped this contract without a FanProfile entry
# in structs.DeviceConfigStruct.fields (BENCHLAB-FW#50); fixed in
# benchlab1/v0.5.2 and benchlab2/v0.6.2 (BENCHLAB-FW#51), which added
# FanProfile at offset 36, size 378 -- matching the layout below and
# PROTOCOL.md Sec 5.6. Fully checked field-by-field like every other struct
# (see tests/test_contract.py) once those patch releases are vendored.
# =============================================================================

class DeviceConfigStruct(Structure):
    """EEPROM-persisted device configuration for ORIGINAL BENCHLAB.

    Payload of READ_DEFAULT_CONFIG (0x13) -- the compiled-in default, not the
    live EEPROM copy. Total size: 426 bytes.
    """
    _fields_ = [
        ('Version',     c_uint8),
        ('Crc',         c_uint16),
        ('FriendlyName', c_char * FRIENDLY_NAME_LEN),
        ('FanProfile',  FanConfigStruct * FAN_NUM * FAN_PROFILE_NUM),
        ('RGBConfig',   RGBConfigStruct * RGB_PROFILE_NUM),
    ]


class DeviceConfigStructBL2(Structure):
    """EEPROM-persisted device configuration for BENCHLAB-2.

    Same layout as DeviceConfigStruct plus a trailing FaultConfig. Total
    size: 560 bytes.
    """
    _fields_ = [
        ('Version',     c_uint8),
        ('Crc',         c_uint16),
        ('FriendlyName', c_char * FRIENDLY_NAME_LEN),
        ('FanProfile',  FanConfigStruct * FAN_NUM * FAN_PROFILE_NUM),
        ('RGBConfig',   RGBConfigStruct * RGB_PROFILE_NUM),
        ('FaultConfig', FaultConfigStruct),
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
    """Compare each variant's structs against its current firmware contract."""
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
            "DeviceConfigStruct": DeviceConfigStruct,
        }),
        (BENCHLAB_BL2_PRODUCT_ID, BENCHLAB_BL2_FIRMWARE_VERSION, {
            "SensorStruct": SensorStructBL2,
            "CalibrationStruct": CalibrationStructBL2,
            "FaultConfigStruct": FaultConfigStruct,
            "DeviceConfigStruct": DeviceConfigStructBL2,
        }),
        # The last released pre-fault BL2 firmware -- checks
        # SensorStructBL2Legacy against the shorter, still-supported
        # READ_SENSORS layout that fw03/fw04 send.
        (BENCHLAB_BL2_PRODUCT_ID, BENCHLAB_BL2_SENSOR_FAULT_FIELDS_FROM - 1, {
            "SensorStruct": SensorStructBL2Legacy,
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