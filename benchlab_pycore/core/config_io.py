"""
Device configuration I/O for BENCHLAB devices.

This module provides read/write functions for every configuration command
exposed by the BENCHLAB firmware (UART_CMD_* cases in usbd_cdc_if.c):

    Command                  | Function(s)
    -------------------------|-----------------------------------------------
    UART_CMD_WELCOME         | ping()
    UART_CMD_READ_NAME       | read_name()
    UART_CMD_WRITE_NAME      | write_name()
    UART_CMD_READ_FAN_PROFILE| read_fan_profile()
    UART_CMD_WRITE_FAN_PROFILE| write_fan_profile()
    UART_CMD_READ_RGB        | read_rgb_profile()
    UART_CMD_WRITE_RGB       | write_rgb_profile()
    UART_CMD_READ_CALIBRATION| read_calibration()
    UART_CMD_WRITE_CALIBRATION| write_calibration_chunk() / write_calibration()
    UART_CMD_LOAD_CALIBRATION| load_calibration()
    UART_CMD_STORE_CALIBRATION| store_calibration()
    UART_CMD_ACTION          | send_action()

Notes:
    - All write functions send the raw bytes the firmware expects and return
      True/False to indicate success (the firmware sends no ACK for writes).
    - FAN_PROFILE_NUM, RGB_PROFILE_NUM, CAL_NUM are validated before sending.
    - Calibration writes larger than ~60 bytes are chunked automatically to
      stay within USB CDC packet limits.

Example::

    import serial
    from benchlab_pycore.core import read_sensors
    from benchlab_pycore.core.config_io import (
        ping, read_name, write_name,
        read_fan_profile, write_fan_profile,
        read_rgb_profile, write_rgb_profile,
        read_calibration, write_calibration,
        load_calibration, store_calibration,
    )

    with serial.Serial("COM3", 115200, timeout=1) as ser:
        if ping(ser):
            print("Device found:", read_name(ser))
"""

import logging
import sys
import os
from ctypes import sizeof, memmove, create_string_buffer, addressof
from typing import Optional, Union

import serial
import time

from .structures import (
    BENCHLAB_CMD,
    BenchlabNvmCmd,
    BENCHLAB_BL2_PRODUCT_ID,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    FAN_PROFILE_NUM,
    FAN_NUM,
    FAN_CURVE_POINTS,
    RGB_PROFILE_NUM,
    CAL_NUM,
    CAL_FACTORY,
    CAL_USER,
    CalSlot,
    resolve_cal_slot,
    FRIENDLY_NAME_LEN,
    FanConfigStruct,
    RGBConfigStruct,
    CalibrationStruct,
    CalibrationStructBL2,
    DeviceConfigStruct,
)
from .serial_io import read_uart

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("benchlab_pycore.core.config_io")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)

# Maximum bytes to write in a single CDC packet (conservative USB FS limit).
_CDC_MAX_WRITE = 64

# Fixed 2-byte "write key" the firmware expects as the first two bytes of the
# UART_CMD_NVM_CONFIG payload (Device_BenchLab.cs:1214-1216). Not computed —
# a literal constant the firmware checks for.
_NVM_WRITE_KEY = bytes([0x34, 0x12])

# Firmware version at which config read/write is known-bugged and must be
# refused, mirroring the C# service's guard (Device_BenchLab.cs:907-910,
# :898). NOT independently verified against firmware/device behavior here.
_CONFIG_BUGGED_VERSION = 0x01


def _crc16(data: bytes) -> int:
    """CRC16 used for DeviceConfigStruct integrity checking.

    Direct port of the C# service's ``Helper.CRC16_Calc`` (BENCHLAB_Core/
    Helper.cs), confirmed against the actual upstream source (not
    independently verified against real firmware/device behavior, since
    the attached test device's firmware doesn't implement
    UART_CMD_READ_CONFIG/WRITE_CONFIG at all).
    """
    crc = 0xFFFF
    for byte in data:
        x = ((crc >> 8) ^ byte) & 0xFF
        x ^= (x >> 4)
        crc = ((crc << 8) ^ (x << 12) ^ (x << 5) ^ x) & 0xFFFF
    return crc


# ===========================================================================
# Internal helpers
# ===========================================================================

def _write(ser: serial.Serial, data: bytes) -> bool:
    """Write *data* to *ser*, return True on success."""
    try:
        written = ser.write(data)
        return written == len(data)
    except serial.SerialException as exc:
        logger.error("Serial write failed: %s", exc)
        return False


def _struct_to_bytes(struct_instance) -> bytes:
    """Convert a ctypes Structure to raw bytes."""
    size = sizeof(struct_instance)
    buf = create_string_buffer(size)
    memmove(buf, addressof(struct_instance), size)
    return bytes(buf)


def _checked_read(ser: serial.Serial, cmd_bytes: bytes, size: int, label: str) -> Optional[bytes]:
    """Send *cmd_bytes* then read exactly *size* bytes, with length validation.

    This is the multi-byte-command equivalent of read_uart(): it provides the
    same incomplete-read guard for commands that require more than a single
    command byte (e.g. READ_FAN_PROFILE sends [cmd, profile, fan_id]).

    Args:
        ser:       Open serial connection.
        cmd_bytes: Full command byte sequence to send.
        size:      Expected number of bytes in the response.
        label:     Caller name used in log messages.

    Returns:
        Raw response bytes, or None if the write failed or the read was short.
    """
    try:
        ser.reset_input_buffer()
        ser.write(cmd_bytes)
    except serial.SerialException as exc:
        logger.error("%s: write failed: %s", label, exc)
        return None

    time.sleep(0.05)   # give firmware time to process and queue the response
    raw = ser.read(size)
    if len(raw) != size:
        logger.warning(
            "%s: expected %d bytes, got %d", label, size, len(raw)
        )
        return None
    return raw


# ===========================================================================
# Ping / welcome
# ===========================================================================

def ping(ser: serial.Serial) -> bool:
    """Send UART_CMD_WELCOME and verify the device responds with 'BENCHLAB'.

    Mirrors the ``UART_CMD_WELCOME`` firmware case which transmits the
    null-terminated string ``"BENCHLAB"`` (9 bytes including ``\\0``).

    Args:
        ser: Open serial connection to the device.

    Returns:
        True if the device acknowledged with the expected welcome string.

    Example::

        >>> assert ping(ser), "Device not found"
    """
    WELCOME = b"BENCHLAB\x00"
    data = read_uart(ser, BENCHLAB_CMD.UART_CMD_WELCOME, len(WELCOME))
    if data is None:
        logger.warning("ping: no response")
        return False
    ok = data == WELCOME
    if not ok:
        logger.warning("ping: unexpected response %r", data)
    return ok


# ===========================================================================
# Friendly name
# ===========================================================================

def read_name(ser: serial.Serial) -> Optional[str]:
    """Read the device friendly name.

    Mirrors ``UART_CMD_READ_NAME``.  The firmware transmits exactly
    ``FRIENDLY_NAME_LEN`` (32) bytes, null-padded.

    Args:
        ser: Open serial connection to the device.

    Returns:
        Decoded friendly name string, or None on failure.

    Example::

        >>> name = read_name(ser)
        >>> print(f"Device name: {name}")
    """
    data = read_uart(ser, BENCHLAB_CMD.UART_CMD_READ_NAME, FRIENDLY_NAME_LEN)
    if data is None:
        logger.warning("read_name: failed to read name")
        return None
    # Take only the part before the first null terminator
    # (rstrip only removes trailing nulls, not embedded ones)
    name_bytes = data.split(b"\x00", 1)[0]
    return name_bytes.decode("utf-8", errors="replace")


def write_name(ser: serial.Serial, name: str) -> bool:
    """Write the device friendly name.

    Mirrors ``UART_CMD_WRITE_NAME``.  The firmware accepts a packet of
    ``[cmd(1)] + name_bytes`` and copies ``*Len`` bytes (the full packet
    length) into ``FriendlyName``.  The firmware guard is::

        if (*Len <= sizeof(FriendlyName) + 1)   // i.e. total packet <= 33
            memcpy(&FriendlyName, Buf+1, *Len)  // copies *Len, not *Len-1

    To avoid a one-byte overwrite past ``FriendlyName``, the total packet
    must be at most ``sizeof(FriendlyName)`` (32) bytes, meaning the name
    payload is capped at 31 bytes (leaving room for a null terminator).

    Args:
        ser:  Open serial connection to the device.
        name: New friendly name (max 30 UTF-8 bytes).

    Returns:
        True if the bytes were sent successfully (no ACK from firmware).

    Raises:
        ValueError: If the UTF-8 encoding of *name* exceeds 30 bytes.

    Example::

        >>> write_name(ser, "My BENCHLAB")
        True
    """
    # Cap at FRIENDLY_NAME_LEN - 2 to leave room for cmd byte and null terminator
    # Total packet: [cmd(1)] + [name bytes] + [null(1)] <= FRIENDLY_NAME_LEN
    max_name_bytes = FRIENDLY_NAME_LEN - 2  # 30 bytes for name + 1 for null + 1 for cmd = 32
    encoded = name.encode("utf-8")
    if len(encoded) > max_name_bytes:
        raise ValueError(
            f"name must be at most {max_name_bytes} UTF-8 bytes, got {len(encoded)}"
        )
    # Add null terminator so firmware knows where the name ends
    payload = bytes([BENCHLAB_CMD.UART_CMD_WRITE_NAME]) + encoded + b'\x00'
    ok = _write(ser, payload)
    if ok:
        logger.info("write_name: wrote %r", name)
    return ok


# ===========================================================================
# Fan profiles
# ===========================================================================

def read_fan_profile(
    ser: serial.Serial,
    fan_profile: int,
    fan_id: int,
) -> Optional[FanConfigStruct]:
    """Read one fan channel's configuration from a stored profile.

    Mirrors ``UART_CMD_READ_FAN_PROFILE``.  The firmware expects a 3-byte
    command ``[cmd, fan_profile, fan_id]`` and responds with exactly
    ``sizeof(FanConfigStruct)`` (14) bytes.

    Args:
        ser:         Open serial connection to the device.
        fan_profile: Profile slot index (0 … FAN_PROFILE_NUM-1).
        fan_id:      Fan channel index  (0 … FAN_NUM-1).

    Returns:
        :class:`FanConfigStruct` on success, or None on failure.

    Raises:
        ValueError: If *fan_profile* or *fan_id* are out of range.

    Example::

        >>> cfg = read_fan_profile(ser, fan_profile=0, fan_id=2)
        >>> print(cfg.FixedDuty)
    """
    if not (0 <= fan_profile < FAN_PROFILE_NUM):
        raise ValueError(f"fan_profile must be 0–{FAN_PROFILE_NUM - 1}, got {fan_profile}")
    if not (0 <= fan_id < FAN_NUM):
        raise ValueError(f"fan_id must be 0–{FAN_NUM - 1}, got {fan_id}")

    cmd_bytes = bytes([BENCHLAB_CMD.UART_CMD_READ_FAN_PROFILE, fan_profile, fan_id])
    raw = _checked_read(ser, cmd_bytes, sizeof(FanConfigStruct), "read_fan_profile")
    if raw is None:
        return None
    return FanConfigStruct.from_buffer_copy(raw)
def write_fan_profile(
    ser: serial.Serial,
    fan_profile: int,
    fan_id: int,
    config: FanConfigStruct,
) -> bool:
    """Write one fan channel's configuration into a stored profile.

    Mirrors ``UART_CMD_WRITE_FAN_PROFILE``.  Payload layout::

        [cmd(1)] [fan_profile(1)] [fan_id(1)] [FanConfigStruct(13 bytes)]

    Args:
        ser:         Open serial connection to the device.
        fan_profile: Profile slot index (0 … FAN_PROFILE_NUM-1).
        fan_id:      Fan channel index  (0 … FAN_NUM-1).
        config:      :class:`FanConfigStruct` to write.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *fan_profile* or *fan_id* are out of range.

    Example::

        >>> cfg = FanConfigStruct()
        >>> cfg.Mode = 0        # Fixed
        >>> cfg.FixedDuty = 75
        >>> write_fan_profile(ser, 0, 2, cfg)
        True
    """
    if not (0 <= fan_profile < FAN_PROFILE_NUM):
        raise ValueError(f"fan_profile must be 0–{FAN_PROFILE_NUM - 1}, got {fan_profile}")
    if not (0 <= fan_id < FAN_NUM):
        raise ValueError(f"fan_id must be 0–{FAN_NUM - 1}, got {fan_id}")

    header = bytes([BENCHLAB_CMD.UART_CMD_WRITE_FAN_PROFILE, fan_profile, fan_id])
    payload = header + _struct_to_bytes(config)
    ok = _write(ser, payload)
    if ok:
        logger.info(
            "write_fan_profile: profile=%d fan=%d mode=%d duty=%d",
            fan_profile, fan_id, config.FanMode, config.FixedDuty,
        )
    return ok


# ===========================================================================
# RGB profiles
# ===========================================================================

def read_rgb_profile(
    ser: serial.Serial,
    rgb_profile: int,
) -> Optional[RGBConfigStruct]:
    """Read one RGB LED profile from the device.

    Mirrors ``UART_CMD_READ_RGB``.  The firmware expects a 2-byte command
    ``[cmd, rgb_profile]`` and always responds with exactly
    ``sizeof(RGBConfigStruct)`` bytes.

    Args:
        ser:         Open serial connection to the device.
        rgb_profile: Profile slot index (0 … RGB_PROFILE_NUM-1).

    Returns:
        :class:`RGBConfigStruct` on success, or None on failure.

    Raises:
        ValueError: If *rgb_profile* is out of range.

    Example::

        >>> rgb = read_rgb_profile(ser, 0)
        >>> print(rgb.Mode, rgb.Red, rgb.Green, rgb.Blue)
    """
    if not (0 <= rgb_profile < RGB_PROFILE_NUM):
        raise ValueError(f"rgb_profile must be 0–{RGB_PROFILE_NUM - 1}, got {rgb_profile}")

    cmd_bytes = bytes([BENCHLAB_CMD.UART_CMD_READ_RGB, rgb_profile])
    raw = _checked_read(ser, cmd_bytes, sizeof(RGBConfigStruct), "read_rgb_profile")
    if raw is None:
        return None
    return RGBConfigStruct.from_buffer_copy(raw)


def write_rgb_profile(
    ser: serial.Serial,
    rgb_profile: int,
    config: RGBConfigStruct,
) -> bool:
    """Write one RGB LED profile to the device.

    Mirrors ``UART_CMD_WRITE_RGB``.  Payload layout::

        [cmd(1)] [rgb_profile(1)] [RGBConfigStruct(N)]

    Args:
        ser:         Open serial connection to the device.
        rgb_profile: Profile slot index (0 … RGB_PROFILE_NUM-1).
        config:      :class:`RGBConfigStruct` to write.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *rgb_profile* is out of range.

    Example::

        >>> rgb = RGBConfigStruct()
        >>> rgb.Mode = 1; rgb.Red = 255; rgb.Green = 0; rgb.Blue = 128
        >>> write_rgb_profile(ser, 0, rgb)
        True
    """
    if not (0 <= rgb_profile < RGB_PROFILE_NUM):
        raise ValueError(f"rgb_profile must be 0–{RGB_PROFILE_NUM - 1}, got {rgb_profile}")

    header = bytes([BENCHLAB_CMD.UART_CMD_WRITE_RGB, rgb_profile])
    payload = header + _struct_to_bytes(config)
    ok = _write(ser, payload)
    if ok:
        logger.info(
            "write_rgb_profile: profile=%d mode=%d R=%d G=%d B=%d",
            rgb_profile, config.Mode, config.Red, config.Green, config.Blue,
        )
    return ok


# ===========================================================================
# Calibration
# ===========================================================================

def read_calibration(
    ser: serial.Serial,
    product_id: Optional[int] = None,
) -> Optional[Union[CalibrationStruct, CalibrationStructBL2]]:
    """Read the full calibration table from the device.

    Mirrors ``UART_CMD_READ_CALIBRATION`` (single-byte command).

    Args:
        ser:        Open serial connection to the device.
        product_id: Product ID to select the correct calibration structure.
                    Use ``BENCHLAB_BL2_PRODUCT_ID`` for BL2 devices, or
                    ``BENCHLAB_ORIGINAL_PRODUCT_ID`` / None for ORIGINAL.

    Returns:
        :class:`CalibrationStructBL2` for BL2 devices,
        :class:`CalibrationStruct` for ORIGINAL devices,
        or None on failure.

    Example::

        >>> cal = read_calibration(ser)
        >>> print(cal.Entries[0].Offset, cal.Entries[0].Scale)
    """
    if product_id == BENCHLAB_BL2_PRODUCT_ID:
        struct_type = CalibrationStructBL2
    else:
        struct_type = CalibrationStruct

    data = read_uart(
        ser,
        BENCHLAB_CMD.UART_CMD_READ_CALIBRATION,
        sizeof(struct_type),
    )
    if data is None:
        logger.warning("read_calibration: failed")
        return None
    return struct_type.from_buffer_copy(data)


def write_calibration_chunk(
    ser: serial.Serial,
    offset: int,
    chunk: bytes,
    product_id: Optional[int] = None,
) -> bool:
    """Write a raw byte slice into the device calibration struct.

    Mirrors the ``UART_CMD_WRITE_CALIBRATION`` firmware case which accepts::

        [cmd(1)] [offset(1)] [data…]

    This low-level function is useful when you want to update only part of
    the calibration table without a full round-trip.

    Args:
        ser:        Open serial connection to the device.
        offset:     Byte offset into the calibration struct.
        chunk:      Raw bytes to write starting at *offset*.
        product_id: Product ID used to determine the correct struct size for
                    bounds checking. Use ``BENCHLAB_BL2_PRODUCT_ID`` for BL2
                    devices, or None for ORIGINAL.

    Returns:
        True if bytes were sent successfully.

    Raises:
        ValueError: If *offset* + ``len(chunk)`` exceeds the struct size,
                    or if *offset* > 255 (firmware uses a single byte).
    """
    if product_id == BENCHLAB_BL2_PRODUCT_ID:
        cal_size = sizeof(CalibrationStructBL2)
    else:
        cal_size = sizeof(CalibrationStruct)

    if offset + len(chunk) > cal_size:
        raise ValueError(
            f"offset({offset}) + len(chunk)({len(chunk)}) = "
            f"{offset + len(chunk)} exceeds CalibrationStruct size {cal_size}"
        )
    if offset > 0xFF:
        raise ValueError(f"offset must fit in one byte (0–255), got {offset}")

    payload = bytes([BENCHLAB_CMD.UART_CMD_WRITE_CALIBRATION, offset]) + chunk
    return _write(ser, payload)


def write_calibration(
    ser: serial.Serial,
    calibration: Union[CalibrationStruct, CalibrationStructBL2],
    chunk_size: int = _CDC_MAX_WRITE - 2,
    product_id: Optional[int] = None,
) -> bool:
    """Write the full calibration table to the device.

    The struct is split into chunks to stay within USB CDC packet limits.
    Each chunk triggers one ``UART_CMD_WRITE_CALIBRATION`` transaction with
    the appropriate byte offset.

    Args:
        ser:         Open serial connection to the device.
        calibration: Populated :class:`CalibrationStruct` or
                     :class:`CalibrationStructBL2` to write.
        chunk_size:  Max payload bytes per packet (default: 62).
        product_id:  Product ID forwarded to ``write_calibration_chunk`` for
                     bounds checking.

    Returns:
        True if all chunks were written successfully.

    Example::

        >>> cal = read_calibration(ser)
        >>> cal.Entries[0].Offset = 10
        >>> write_calibration(ser, cal)
        True
    """
    raw = _struct_to_bytes(calibration)
    offset = 0
    while offset < len(raw):
        chunk = raw[offset: offset + chunk_size]
        if not write_calibration_chunk(ser, offset, chunk, product_id=product_id):
            logger.error(
                "write_calibration: failed at offset %d/%d", offset, len(raw)
            )
            return False
        offset += len(chunk)
    logger.info("write_calibration: wrote %d bytes in chunks of %d", len(raw), chunk_size)
    return True


def _resolve_slot(cal_id, product_id, fw_version, func_name):
    """Turn a caller's slot argument into the byte this firmware expects.

    A CalSlot member is resolved against the device's contract, which is the
    safe path: the numeric values swapped between firmware versions. A plain
    int is passed through unchanged for backwards compatibility, since that is
    what the published API accepted -- but it is only correct if the caller
    already knows the running firmware.
    """
    if isinstance(cal_id, CalSlot):
        if product_id is None or fw_version is None:
            raise ValueError(
                "{}: product_id and fw_version are required when passing a "
                "CalSlot, because the wire value differs between firmware "
                "versions. Take them from read_device().".format(func_name)
            )
        return resolve_cal_slot(cal_id, product_id, fw_version)

    if cal_id not in (CAL_FACTORY, CAL_USER):
        raise ValueError(
            "cal_id must be CAL_FACTORY ({}) or CAL_USER ({}), got {}".format(
                CAL_FACTORY, CAL_USER, cal_id)
        )
    return cal_id


def load_calibration(ser: serial.Serial, cal_id, product_id: Optional[int] = None,
                     fw_version: Optional[int] = None) -> bool:
    """Load a calibration slot from flash into the active calibration table.

    Mirrors ``UART_CMD_LOAD_CALIBRATION``.

    Args:
        ser:        Open serial connection to the device.
        cal_id:     ``CalSlot.FACTORY`` or ``CalSlot.USER`` (preferred), or a
                    raw int for backwards compatibility.
        product_id: ProductId from ``read_device()``. Required with a CalSlot.
        fw_version: FwVersion from ``read_device()``. Required with a CalSlot.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *cal_id* is out of range, or a CalSlot was given
            without the device identity needed to resolve it.
        UnknownFirmwareError: If no contract matches the device.

    Example::

        >>> info = read_device(ser)
        >>> load_calibration(ser, CalSlot.USER,
        ...                  info["ProductId"], info["FwVersion"])
        True
    """
    cal_id = _resolve_slot(cal_id, product_id, fw_version, "load_calibration")
    payload = bytes([BENCHLAB_CMD.UART_CMD_LOAD_CALIBRATION, cal_id])
    ok = _write(ser, payload)
    if ok:
        logger.info("load_calibration: loaded slot %d", cal_id)
    return ok


def store_calibration(ser: serial.Serial, cal_id, product_id: Optional[int] = None,
                      fw_version: Optional[int] = None) -> bool:
    """Save the active calibration table to a flash slot.

    Mirrors ``UART_CMD_STORE_CALIBRATION``.

    .. warning::
        This is destructive and unacknowledged. The slot numbers swapped in
        firmware (fw03 ORIGINAL, fw04 BL2), so passing a raw int that was
        correct on older firmware writes the *other* slot -- on current
        firmware, a raw ``1`` means factory. Pass a CalSlot with the device
        identity so the value is resolved from that firmware's contract.

    Args:
        ser:        Open serial connection to the device.
        cal_id:     ``CalSlot.FACTORY`` or ``CalSlot.USER`` (preferred), or a
                    raw int for backwards compatibility.
        product_id: ProductId from ``read_device()``. Required with a CalSlot.
        fw_version: FwVersion from ``read_device()``. Required with a CalSlot.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *cal_id* is out of range, or a CalSlot was given
            without the device identity needed to resolve it.
        UnknownFirmwareError: If no contract matches the device.

    Example::

        >>> info = read_device(ser)
        >>> store_calibration(ser, CalSlot.USER,
        ...                   info["ProductId"], info["FwVersion"])
        True
    """
    cal_id = _resolve_slot(cal_id, product_id, fw_version, "store_calibration")
    payload = bytes([BENCHLAB_CMD.UART_CMD_STORE_CALIBRATION, cal_id])
    ok = _write(ser, payload)
    if ok:
        logger.info("store_calibration: stored to slot %d", cal_id)
    return ok


# ===========================================================================
# Action command
# ===========================================================================

def send_action(
    ser: serial.Serial,
    action: int,
    param1: int = 0,
    param2: int = 0,
    param3: int = 0,
) -> bool:
    """Send a one-shot action command to the device.

    Mirrors ``UART_CMD_ACTION``.  The firmware accepts exactly 5 bytes::

        [cmd(1)] [action(1)] [param1(1)] [param2(1)] [param3(1)]

    The firmware will silently ignore the command if another action is
    already pending (``ActionCommand.Action != ACTION_NONE``).

    Args:
        ser:    Open serial connection to the device.
        action: Action code (device-specific, e.g. save config, reboot).
        param1: First action parameter (default 0).
        param2: Second action parameter (default 0).
        param3: Third action parameter (default 0).

    Returns:
        True if bytes were sent.

    Raises:
        ValueError: If any argument does not fit in one unsigned byte.

    Example::

        >>> send_action(ser, action=1)   # trigger save
        True
    """
    for name, val in (
        ("action", action), ("param1", param1), ("param2", param2), ("param3", param3)
    ):
        if not (0 <= val <= 0xFF):
            raise ValueError(f"{name} must be 0–255, got {val}")

    payload = bytes([BENCHLAB_CMD.UART_CMD_ACTION, action, param1, param2, param3])
    ok = _write(ser, payload)
    if ok:
        logger.info(
            "send_action: action=%d p1=%d p2=%d p3=%d",
            action, param1, param2, param3,
        )
    return ok


# ===========================================================================
# Full device configuration
#
# NOTE: as of the BenchLab-io/BENCHLAB-FW firmware repo's current master and
# cfe branches, none of UART_CMD_READ_CONFIG / WRITE_CONFIG / NVM_CONFIG /
# WRITE_FAN_DUTY / RESET / BOOTLOADER (commands 15-20) are implemented in
# firmware — the command dispatcher only handles commands 0-14. Confirmed by
# direct probing against real hardware (zero-byte response) and by reading
# the firmware source directly (usbd_cdc_if.c / command.c switch statements,
# and the UART_CMD/COMMAND_ID enums themselves, all stop at command 14).
# The functions below implement the C# service's (Device_BenchLab.cs)
# intended protocol for these commands, which is speculative/forward-looking
# relative to any currently shipping or in-development firmware. They will
# not work against real devices until firmware support is added, and the C#
# reference implementation for these specific commands has NOT itself been
# exercised by any automated or manual test in that service's repo.
# ===========================================================================

def read_config(ser: serial.Serial) -> Optional[DeviceConfigStruct]:
    """Read the full device config blob (name + fan profiles + RGB profiles).

    Mirrors ``UART_CMD_READ_CONFIG`` — NOT YET IMPLEMENTED IN FIRMWARE, see
    module note above. Verifies the CRC16 over the struct
    bytes starting at offset 2 (past Version+Crc), matching the C# service's
    ``Helper.CRC16_Calc(rxBuffer, 2, rxBuffer.Length - 2)``. If
    ``Version == 0x01``, the firmware may report ``Crc == 0`` when config
    hasn't yet been loaded from NVM, and the check is skipped in that case.

    Returns:
        :class:`DeviceConfigStruct` on success (CRC valid or skipped), or
        None on failure / CRC mismatch.
    """
    size = sizeof(DeviceConfigStruct)
    raw = read_uart(ser, BENCHLAB_CMD.UART_CMD_READ_CONFIG, size)
    if raw is None:
        logger.warning("read_config: failed to read config")
        return None

    config = DeviceConfigStruct.from_buffer_copy(raw)
    if config.Version == _CONFIG_BUGGED_VERSION and config.Crc == 0:
        logger.warning("read_config: config not yet loaded from NVM (version 0x01, crc 0)")
        return config

    expected_crc = _crc16(raw[2:])
    if config.Crc != expected_crc:
        logger.error(
            "read_config: CRC mismatch (got 0x%04X, expected 0x%04X)",
            config.Crc, expected_crc,
        )
        return None
    return config


def write_config(ser: serial.Serial, config: DeviceConfigStruct) -> bool:
    """Write the full device config blob in one shot.

    Mirrors ``UART_CMD_WRITE_CONFIG``. Computes the CRC16 over the struct
    bytes at offset 2 onward and overwrites bytes 0-1 (the Version+Crc
    fields) of the outgoing buffer with the freshly computed CRC before
    sending, matching the C# service's behavior.

    Refuses to write if ``config.Version == 0x01`` ("write config is
    bugged"), matching the C# guard.

    Returns:
        True if the command and payload were sent successfully.
    """
    if config.Version == _CONFIG_BUGGED_VERSION:
        logger.error("write_config: refusing write for bugged config version 0x01")
        return False

    raw = bytearray(_struct_to_bytes(config))
    crc = _crc16(bytes(raw[2:]))
    raw[0:2] = crc.to_bytes(2, 'little')

    ok = _write(ser, bytes([BENCHLAB_CMD.UART_CMD_WRITE_CONFIG])) and _write(ser, bytes(raw))
    if ok:
        logger.info("write_config: wrote %d bytes (crc=0x%04X)", len(raw), crc)
    return ok


def _send_nvm_command(ser: serial.Serial, sub_cmd: BenchlabNvmCmd) -> bool:
    payload = bytes([BENCHLAB_CMD.UART_CMD_NVM_CONFIG]) + _NVM_WRITE_KEY + bytes([sub_cmd])
    return _write(ser, payload)


def save_config(ser: serial.Serial) -> bool:
    """Persist the active config to the device's NVM. Mirrors ``SaveConfig()``."""
    ok = _send_nvm_command(ser, BenchlabNvmCmd.CONFIG_SAVE)
    if ok:
        logger.info("save_config: config saved to NVM")
    return ok


def load_config(ser: serial.Serial) -> bool:
    """Restore the active config from the device's NVM. Mirrors ``LoadConfig()``."""
    ok = _send_nvm_command(ser, BenchlabNvmCmd.CONFIG_LOAD)
    if ok:
        logger.info("load_config: config loaded from NVM")
    return ok


def reset_config(ser: serial.Serial) -> bool:
    """Reset the active config to defaults in NVM. Mirrors ``ResetConfig()``."""
    ok = _send_nvm_command(ser, BenchlabNvmCmd.CONFIG_RESET)
    if ok:
        logger.info("reset_config: config reset")
    return ok


# ===========================================================================
# Direct fan duty override
# ===========================================================================

def set_fan_duty(ser: serial.Serial, fan_id: int, duty: int) -> bool:
    """Directly override one fan's duty cycle, bypassing profile curves.

    Mirrors ``UART_CMD_WRITE_FAN_DUTY``.

    Args:
        ser:    Open serial connection to the device.
        fan_id: Fan channel index (0 … FAN_NUM-1).
        duty:   0-100 (0x00-0x64) for an explicit duty percentage, or 255
                (0xFF) to hand control back to the MCU's embedded fan-curve
                logic.

    Returns:
        True if bytes were sent successfully.

    Raises:
        ValueError: If *fan_id* or *duty* are out of range.
    """
    if not (0 <= fan_id < FAN_NUM):
        raise ValueError(f"fan_id must be 0–{FAN_NUM - 1}, got {fan_id}")
    if not (0 <= duty <= 100 or duty == 255):
        raise ValueError(f"duty must be 0-100 or 255 (MCU control), got {duty}")

    payload = bytes([BENCHLAB_CMD.UART_CMD_WRITE_FAN_DUTY, fan_id, duty])
    ok = _write(ser, payload)
    if ok:
        logger.info("set_fan_duty: fan=%d duty=%d", fan_id, duty)
    return ok


# ===========================================================================
# Device reset / bootloader
# ===========================================================================

def reset_device(ser: serial.Serial, bootloader: bool = False) -> bool:
    """Reset the device, optionally into bootloader/DFU mode.

    Mirrors ``UART_CMD_RESET`` / ``UART_CMD_BOOTLOADER``. No response is
    expected — the device is about to reset/disconnect.

    Args:
        ser:        Open serial connection to the device.
        bootloader: If True, reset into bootloader/DFU mode instead of a
                    normal soft-reset.

    Returns:
        True if the command byte was sent successfully.
    """
    cmd = BENCHLAB_CMD.UART_CMD_BOOTLOADER if bootloader else BENCHLAB_CMD.UART_CMD_RESET
    ok = _write(ser, cmd.toByte())
    if ok:
        logger.info("reset_device: bootloader=%s", bootloader)
    return ok