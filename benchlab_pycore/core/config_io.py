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
import time
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
    BENCHLAB_CFE_PRODUCT_ID,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    FAN_PROFILE_NUM,
    FAN_NUM,
    FAN_CURVE_POINTS,
    RGB_PROFILE_NUM,
    CAL_NUM,
    CAL_FACTORY,
    CAL_USER,
    FRIENDLY_NAME_LEN,
    FanConfigStruct,
    RGBConfigStruct,
    CalibrationStruct,
    CalibrationStructCFE,
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
    # Strip null terminator and trailing nulls
    return data.rstrip(b"\x00").decode("utf-8", errors="replace")


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
        name: New friendly name (max 31 UTF-8 bytes; truncated if longer).

    Returns:
        True if the bytes were sent successfully (no ACK from firmware).

    Example::

        >>> write_name(ser, "My BENCHLAB")
        True
    """
    # Cap at FRIENDLY_NAME_LEN - 2 so that total packet (cmd + payload) is at
    # most FRIENDLY_NAME_LEN - 1 bytes, safely within the firmware's memcpy.
    max_name_bytes = FRIENDLY_NAME_LEN - 1  # 31 bytes; keeps total packet at FRIENDLY_NAME_LEN
    encoded = name.encode("utf-8")[:max_name_bytes]
    payload = bytes([BENCHLAB_CMD.UART_CMD_WRITE_NAME]) + encoded
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
    command ``[cmd, fan_profile, fan_id]``.  Depending on firmware version it
    Mirrors ``UART_CMD_READ_FAN_PROFILE``.  The firmware expects a 3-byte
    command ``[cmd, fan_profile, fan_id]`` and responds with exactly
    ``sizeof(FanConfigStruct)`` (13) bytes.

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
            fan_profile, fan_id, config.Mode, config.FixedDuty,
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
) -> Optional[Union[CalibrationStruct, CalibrationStructCFE]]:
    """Read the full calibration table from the device.

    Mirrors ``UART_CMD_READ_CALIBRATION`` (single-byte command).

    Args:
        ser:        Open serial connection to the device.
        product_id: Product ID to select the correct calibration structure.
                    Use ``BENCHLAB_CFE_PRODUCT_ID`` for CFE devices, or
                    ``BENCHLAB_ORIGINAL_PRODUCT_ID`` / None for ORIGINAL.

    Returns:
        :class:`CalibrationStructCFE` for CFE devices,
        :class:`CalibrationStruct` for ORIGINAL devices,
        or None on failure.

    Example::

        >>> cal = read_calibration(ser)
        >>> print(cal.Entries[0].Offset, cal.Entries[0].Scale)
    """
    if product_id == BENCHLAB_CFE_PRODUCT_ID:
        struct_type = CalibrationStructCFE
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
                    bounds checking. Use ``BENCHLAB_CFE_PRODUCT_ID`` for CFE
                    devices, or None for ORIGINAL.

    Returns:
        True if bytes were sent successfully.

    Raises:
        ValueError: If *offset* + ``len(chunk)`` exceeds the struct size,
                    or if *offset* > 255 (firmware uses a single byte).
    """
    if product_id == BENCHLAB_CFE_PRODUCT_ID:
        cal_size = sizeof(CalibrationStructCFE)
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
    calibration: Union[CalibrationStruct, CalibrationStructCFE],
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
                     :class:`CalibrationStructCFE` to write.
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


def load_calibration(ser: serial.Serial, cal_id: int) -> bool:
    """Load a calibration slot from flash into the active calibration table.

    Mirrors ``UART_CMD_LOAD_CALIBRATION``.

    Args:
        ser:    Open serial connection to the device.
        cal_id: Slot to load — ``0`` = user calibration,
                ``1`` = factory calibration.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *cal_id* is out of range.

    Example::

        >>> load_calibration(ser, 0)   # restore user cal
        True
        >>> load_calibration(ser, 1)   # restore factory cal
        True
    """
    if cal_id not in (CAL_FACTORY, CAL_USER):
        raise ValueError(f"cal_id must be CAL_FACTORY ({CAL_FACTORY}) or CAL_USER ({CAL_USER}), got {cal_id}")
    payload = bytes([BENCHLAB_CMD.UART_CMD_LOAD_CALIBRATION, cal_id])
    ok = _write(ser, payload)
    if ok:
        slot = "factory" if cal_id == CAL_FACTORY else "user"
        logger.info("load_calibration: loaded %s slot (%d)", slot, cal_id)
    return ok


def store_calibration(ser: serial.Serial, cal_id: int) -> bool:
    """Save the active calibration table to a flash slot.

    Mirrors ``UART_CMD_STORE_CALIBRATION``.

    Args:
        ser:    Open serial connection to the device.
        cal_id: Destination slot — ``0`` = user calibration,
                ``1`` = factory calibration.

    Returns:
        True if bytes were sent (no ACK from firmware).

    Raises:
        ValueError: If *cal_id* is out of range.

    Example::

        >>> store_calibration(ser, 0)   # persist user cal
        True
    """
    if cal_id not in (CAL_FACTORY, CAL_USER):
        raise ValueError(f"cal_id must be CAL_FACTORY ({CAL_FACTORY}) or CAL_USER ({CAL_USER}), got {cal_id}")
    payload = bytes([BENCHLAB_CMD.UART_CMD_STORE_CALIBRATION, cal_id])
    ok = _write(ser, payload)
    if ok:
        slot = "factory" if cal_id == CAL_FACTORY else "user"
        logger.info("store_calibration: stored to %s slot (%d)", slot, cal_id)
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