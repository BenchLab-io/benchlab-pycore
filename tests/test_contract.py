# tests/test_contract.py
"""Check the hand-written ctypes layer against the vendored firmware contracts.

The contracts are generated from the firmware headers and frozen at release
time, so they are the source of truth for sizes, offsets, opcodes, enums and
constants. Everything asserted here is read from them -- no size or offset is
hardcoded in this file. Re-vendor a contract and these tests follow.

Tests that currently fail are marked xfail(strict=True) rather than skipped, so
they are visible and flip automatically when the library is fixed.
"""

import ctypes

import pytest

from benchlab_pycore.core.contract import (
    UnknownFirmwareError,
    available,
    contract_for,
)
from benchlab_pycore.core import structures as st


# =============================================================================
# Parametrisation
# =============================================================================

ALL_PAIRS = sorted(available())

# Which pycore ctypes class implements each contract struct, per variant. The
# contract names both variants' sensor/calibration structs "SensorStruct" and
# "CalibrationStruct"; pycore splits them into Original and BL2 classes.
_COMMON = {
    "VendorDataStruct": st.VendorDataStruct,
    "PowerSensor": st.PowerSensor,
    "FanSensor": st.FanSensor,
    "FanConfigStruct": st.FanConfigStruct,
    "RGBConfigStruct": st.RGBConfigStruct,
    "CalibrationValueStruct": st.CalibrationValueStruct,
}
_BY_VARIANT = {
    "benchlab-original": dict(
        _COMMON,
        SensorStruct=st.SensorStructOriginal,
        CalibrationStruct=st.CalibrationStruct,
    ),
    "benchlab2": dict(
        _COMMON,
        SensorStruct=st.SensorStructBL2,
        CalibrationStruct=st.CalibrationStructBL2,
    ),
}


def structs_for(contract):
    return _BY_VARIANT[contract.variant]


def pairs_ids(pair):
    pid, fw = pair
    return "pid{:#04x}-fw{:02d}".format(pid, fw)


@pytest.fixture(params=ALL_PAIRS, ids=pairs_ids)
def contract(request):
    """Every vendored contract, one test per (ProductId, FwVersion)."""
    return contract_for(*request.param)


# =============================================================================
# Loader
# =============================================================================

def test_all_indexed_contracts_load():
    assert ALL_PAIRS, "no contracts vendored -- run tools/sync_contracts.py"
    for pid, fw in ALL_PAIRS:
        assert contract_for(pid, fw).fw_version == fw


def test_contract_identity_matches_its_key(contract):
    """A contract's own identity block must agree with its index entry."""
    assert contract.product_id == contract.constant("PRODUCT_ID")
    assert contract.fw_version == contract.constant("FIRMWARE_VERSION")
    assert contract.vendor_id == contract.constant("VENDOR_ID")


def test_unknown_firmware_raises_and_lists_known():
    with pytest.raises(UnknownFirmwareError) as excinfo:
        contract_for(0x11, 0x63)
    message = str(excinfo.value)
    assert "0x11" in message
    # The error must name what *is* available, so the reader can act on it.
    assert "0x04" in message


# =============================================================================
# Struct sizes and field offsets
# =============================================================================

def test_struct_sizes(contract):
    for name, cls in structs_for(contract).items():
        assert ctypes.sizeof(cls) == contract.struct_size(name), (
            "{} vs {} in {}".format(cls.__name__, name, contract.filename)
        )


def test_field_offsets_and_sizes(contract):
    """Every field the contract records must sit at the same offset in ctypes.

    This is the check that makes the hand-written structures safe to keep: a
    field inserted or resized in firmware shows up here rather than as garbage
    sensor readings.
    """
    for name, cls in structs_for(contract).items():
        for field in contract.fields(name):
            attr = getattr(cls, field["name"], None)
            assert attr is not None, (
                "{} is missing field {} required by {} in {}".format(
                    cls.__name__, field["name"], name, contract.filename)
            )
            assert attr.offset == field["offset"], (
                "{}.{} offset {} != contract {}".format(
                    cls.__name__, field["name"], attr.offset, field["offset"])
            )
            assert attr.size == field["size"], (
                "{}.{} size {} != contract {}".format(
                    cls.__name__, field["name"], attr.size, field["size"])
            )


def test_no_extra_ctypes_fields(contract):
    """pycore must not define fields the firmware does not send."""
    for name, cls in structs_for(contract).items():
        contract_fields = {f["name"] for f in contract.fields(name)}
        ctypes_fields = {f[0] for f in cls._fields_}
        assert ctypes_fields <= contract_fields, (
            "{} has fields absent from {} in {}: {}".format(
                cls.__name__, name, contract.filename,
                sorted(ctypes_fields - contract_fields))
        )


# =============================================================================
# Cardinality constants
# =============================================================================

def test_sensor_cardinality(contract):
    """Array lengths pycore uses must match the firmware's counts.

    Sensor *names* are not in the contract, so this checks cardinality only.
    """
    is_bl2 = contract.variant == "benchlab2"
    expected = {
        "SENSOR_VIN_NUM": st.SENSOR_VIN_NUM_BL2 if is_bl2 else st.SENSOR_VIN_NUM_ORIGINAL,
        "SENSOR_POWER_NUM": st.SENSOR_POWER_NUM_BL2 if is_bl2 else st.SENSOR_POWER_NUM_ORIGINAL,
        "TS_NUM": st.SENSOR_TS_NUM_BL2 if is_bl2 else st.SENSOR_TS_NUM_ORIGINAL,
        "FAN_NUM": st.FAN_NUM,
    }
    for const, value in expected.items():
        assert value == contract.constant(const), "{} in {}".format(const, contract.filename)


def test_config_constants(contract):
    for const, value in [
        ("CAL_NUM", st.CAL_NUM),
        ("FAN_PROFILE_NUM", st.FAN_PROFILE_NUM),
        ("RGB_PROFILE_NUM", st.RGB_PROFILE_NUM),
        ("CONFIG_STR_LEN", st.FRIENDLY_NAME_LEN),
        ("FAN_CURVE_NUM_POINTS", st.FAN_CURVE_POINTS),
    ]:
        assert value == contract.constant(const), "{} in {}".format(const, contract.filename)


# =============================================================================
# Opcodes
# =============================================================================

# pycore prefixes its enum members; the contract does not.
_CMD_PREFIX = "UART_CMD_"

# Declared by pycore but present in no firmware contract: ported speculatively
# from the C# reference and known to fail against hardware. Pinned here so the
# gap is asserted rather than tripped over; see issue #7.
_SPECULATIVE = {
    "READ_CONFIG",
    "WRITE_CONFIG",
    "NVM_CONFIG",
    "WRITE_FAN_DUTY",
    "RESET",
    "BOOTLOADER",
}


def test_opcode_values_match(contract):
    """Every command the firmware defines must have the same value in pycore."""
    for name, opcode in contract.opcodes().items():
        member = getattr(st.BENCHLAB_CMD, _CMD_PREFIX + name, None)
        assert member is not None, (
            "pycore lacks {} ({}) from {}".format(name, opcode, contract.filename)
        )
        assert member.value == opcode, "{} in {}".format(name, contract.filename)


def test_speculative_opcodes_are_exactly_the_unbacked_ones(contract):
    """Pin the known gap: no contract backs these, and nothing else is unbacked."""
    declared = {c.name[len(_CMD_PREFIX):] for c in st.BENCHLAB_CMD}
    unbacked = declared - set(contract.opcodes())
    assert unbacked == _SPECULATIVE, (
        "unbacked commands changed for {}: {}".format(
            contract.filename, sorted(unbacked))
    )


# =============================================================================
# Enums
# =============================================================================

def _assert_enum_matches(contract, contract_enum, py_enum, prefix, allow_missing=()):
    """Compare a pycore IntEnum against a contract enum.

    Contract members are prefixed (RGB_MODE_RAINBOW vs pycore's RAINBOW), so the
    prefix is stripped before comparing. ``allow_missing`` names contract members
    pycore deliberately does not model.
    """
    expected = {
        name[len(prefix):]: value
        for name, value in contract.enum(contract_enum).items()
        if name[len(prefix):] not in allow_missing
    }
    actual = {member.name: member.value for member in py_enum}
    assert actual == expected, "{} vs {} in {}".format(
        py_enum.__name__, contract_enum, contract.filename)


def test_fan_mode_enum(contract):
    _assert_enum_matches(contract, "FAN_MODE", st.FanMode, "FAN_MODE_")


def test_fan_stop_enum(contract):
    _assert_enum_matches(contract, "FAN_STOP", st.FanStop, "FAN_STOP_")


def test_rgb_direction_enum(contract):
    _assert_enum_matches(contract, "RGB_DIRECTION", st.RGBDirection, "RGB_DIRECTION_")


def test_rgb_mode_enum(contract):
    # FAULT (239) and NONE (255) are firmware-internal states, never set by a
    # host writing an RGB profile, so pycore does not model them.
    _assert_enum_matches(
        contract, "RGB_MODE", st.RGBMode, "RGB_MODE_",
        allow_missing={"FAULT", "NONE"},
    )


def test_temp_src_enum_bl2():
    """BL2 defines four HPWR temperature sources on top of the shared six."""
    _assert_enum_matches(contract_for(0x11, 4), "TEMP_SRC", st.TempSrc, "TEMP_SRC_")


def test_temp_src_is_a_superset_for_every_contract(contract):
    """TempSrc is one shared enum, so it is the union across variants.

    The ORIGINAL firmware stops at TAMB, so it is checked as a subset: every
    source that firmware defines must be present with the same value, and
    pycore may know about sources it does not have.
    """
    expected = {
        name[len("TEMP_SRC_"):]: value
        for name, value in contract.enum("TEMP_SRC").items()
    }
    actual = {member.name: member.value for member in st.TempSrc}
    missing = {k: v for k, v in expected.items() if actual.get(k) != v}
    assert not missing, "TempSrc disagrees with {}: {}".format(
        contract.filename, missing)


# =============================================================================
# Calibration slot ids -- the live data-loss bug
# =============================================================================

@pytest.mark.parametrize(
    "pid,fw", ALL_PAIRS, ids=[pairs_ids(p) for p in ALL_PAIRS]
)
def test_resolve_cal_slot_matches_every_firmware(pid, fw):
    """resolve_cal_slot() must produce the right wire value on *every* firmware.

    This is the check that matters: because cal_id goes straight onto the wire
    and storing is destructive, resolving the wrong number means
    store_calibration(USER) overwrites the factory slot. A single pair of
    module constants cannot be right for all four firmwares -- only per-device
    resolution can.
    """
    contract = contract_for(pid, fw)
    assert st.resolve_cal_slot(st.CalSlot.FACTORY, pid, fw) == contract.constant("CAL_FACTORY")
    assert st.resolve_cal_slot(st.CalSlot.USER, pid, fw) == contract.constant("CAL_USER")


def test_module_cal_constants_match_current_firmware():
    """The back-compat module constants track the newest firmware of each variant.

    They are necessarily wrong for older firmware -- that is why
    resolve_cal_slot() exists -- but they must at least match what a device
    fresh out of the box is running.
    """
    for pid, fw in [(st.BENCHLAB_ORIGINAL_PRODUCT_ID, st.BENCHLAB_ORIGINAL_FIRMWARE_VERSION),
                    (st.BENCHLAB_BL2_PRODUCT_ID, st.BENCHLAB_BL2_FIRMWARE_VERSION)]:
        contract = contract_for(pid, fw)
        assert st.CAL_FACTORY == contract.constant("CAL_FACTORY")
        assert st.CAL_USER == contract.constant("CAL_USER")


def test_resolve_cal_slot_refuses_unknown_firmware():
    """Guessing on a destructive path is worse than failing."""
    with pytest.raises(UnknownFirmwareError):
        st.resolve_cal_slot(st.CalSlot.FACTORY, 0x11, 0x63)


def test_calibration_slot_ids_are_swapped_between_versions():
    """Document the swap itself, independently of pycore's current values.

    This is what makes version-aware dispatch necessary: BL2 fw03 and fw04 are
    byte-identical in every struct, so no size or offset check can catch it.
    """
    assert contract_for(0x11, 3).constant("CAL_FACTORY") == 0
    assert contract_for(0x11, 4).constant("CAL_FACTORY") == 1
    assert contract_for(0x10, 2).constant("CAL_FACTORY") == 0
    assert contract_for(0x10, 3).constant("CAL_FACTORY") == 1


# =============================================================================
# Firmware version constants
# =============================================================================

def test_declared_firmware_versions_have_contracts():
    """The versions pycore claims to speak must be ones we have contracts for."""
    assert (st.BENCHLAB_ORIGINAL_PRODUCT_ID,
            st.BENCHLAB_ORIGINAL_FIRMWARE_VERSION) in available()
    assert (st.BENCHLAB_BL2_PRODUCT_ID,
            st.BENCHLAB_BL2_FIRMWARE_VERSION) in available()
