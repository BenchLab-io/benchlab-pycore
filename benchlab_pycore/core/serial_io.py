"""
Serial communication helpers for BENCHLAB devices.

This module provides functions for discovering, connecting to, and communicating
with BENCHLAB hardware devices via serial communication. It handles device
discovery, vendor information reading, sensor data acquisition, and UID reading.

Supports multiple device variants:
    - ORIGINAL: BENCHLAB Original (Product ID: 0x10)
    - CFE: BENCHLAB-CFE (Product ID: 0x11)

Example:
    >>> from benchlab_pycore.core import get_fleet_info, read_sensors
    >>> devices = get_fleet_info()
    >>> if devices:
    >>>     # Connect to first device
    >>>     import serial
    >>>     ser = serial.Serial(devices[0]['port'], 115200, timeout=1)
    >>>     sensors = read_sensors(ser)
    >>>     ser.close()
"""

import os
import sys
import time
import logging
import serial
import serial.tools.list_ports
from ctypes import sizeof
from typing import List, Dict, Optional, Union

from benchlab_pycore.core.structures import (
    VendorDataStruct,
    SensorStructOriginal,
    SensorStructCFE,
    BENCHLAB_CMD,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    BENCHLAB_CFE_PRODUCT_ID,
)

# --- Logger setup ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("benchlab_pycore.core.serial_io")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# VID:PID for all BENCHLAB devices (checked case-insensitively).
_BENCHLAB_VID_PID = "VID:PID=0483:5740"


# --- Serial port helpers ---

def get_benchlab_ports() -> List[Dict[str, str]]:
    """Return all Benchlab COM ports without opening them.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing port information.
                             Each dict has a 'port' key with the COM port name.

    Raises:
        serial.SerialException: If serial port enumeration fails.

    Example:
        >>> ports = get_benchlab_ports()
        >>> print(ports)
        [{'port': 'COM3'}, {'port': 'COM4'}]
    """
    try:
        ports = serial.tools.list_ports.comports()
    except serial.SerialException as e:
        logger.error("Failed to enumerate serial ports: %s", e)
        raise

    benchlab_ports = []
    for p in ports:
        if _BENCHLAB_VID_PID in p.hwid.upper():
            benchlab_ports.append({"port": p.device})
    return benchlab_ports


def find_benchlab_devices() -> List[Dict[str, str]]:
    """Scan and return all connected BENCHLAB devices.

    Returns:
        List[Dict[str, str]]: List of dictionaries containing device information.
                             Each dict contains 'port', 'uid', and 'fw' keys.

    Raises:
        serial.SerialException: If serial port enumeration fails.

    Note:
        This function opens and closes serial connections to read device info.
        It may take several seconds if multiple devices are connected.

    Example:
        >>> devices = find_benchlab_devices()
        >>> print(devices)
        [{'port': 'COM3', 'uid': '123456789ABC', 'fw': '1.0'}, ...]
    """
    devices = []
    for port_info in get_benchlab_ports():
        port = port_info["port"]
        uid, fw = "?", "?"
        try:
            with serial.Serial(port, baudrate=115200, timeout=1) as ser:
                device_info = read_device(ser)
                uid = read_uid(ser) or "?"
                fw = str(device_info.get("FwVersion")) if device_info else "?"
            logger.info("Found device on %s: UID=%s, FW=%s", port, uid, fw)
        except serial.SerialException as e:
            logger.warning("Failed to open serial port %s: %s", port, e)
        except Exception as e:
            logger.warning("Failed to read device on %s: %s", port, e)
        devices.append({"port": port, "uid": uid, "fw": fw})
    return devices


def get_fleet_info() -> List[Dict[str, Union[str, int]]]:
    """Return a list of all BENCHLAB devices with UID and firmware info.

    Returns:
        List[Dict[str, Union[str, int]]]: List of dictionaries containing device
                                        information with 'port', 'firmware', and 'uid' keys.

    Note:
        This function opens and closes serial connections to read device info.
        It may take several seconds if multiple devices are connected.

    Example:
        >>> fleet = get_fleet_info()
        >>> print(fleet)
        [{'port': 'COM3', 'firmware': 1, 'uid': '123456789ABC'}, ...]
    """
    fleet = []
    benchlab_ports = [p["port"] for p in get_benchlab_ports()]

    for port in benchlab_ports:
        try:
            with serial.Serial(port, 115200, timeout=1) as ser:
                device_info = read_device(ser)
                uid = read_uid(ser)
                fleet.append(
                    {
                        "port": port,
                        "firmware": (
                            device_info.get("FwVersion") if device_info else "?"
                        ),
                        "uid": uid,
                    }
                )
                logger.debug("Added device to fleet: %s", uid)
        except serial.SerialException as e:
            logger.warning("Failed to open serial port %s: %s", port, e)
        except Exception as e:
            logger.warning("Failed to get device info from %s: %s", port, e)
    return fleet


# --- UART helpers ---

def read_uart(ser: serial.Serial, cmd: BENCHLAB_CMD, size: int) -> Optional[bytes]:
    """Send a command and read bytes from the device.

    Args:
        ser (serial.Serial): Opened serial connection to the device.
        cmd (BENCHLAB_CMD): Command to send to the device.
        size (int): Expected number of bytes to read.

    Returns:
        Optional[bytes]: Raw bytes read from device, or None if read failed.

    Note:
        This function logs warnings if the read is incomplete but doesn't raise exceptions.
        Callers should handle None returns appropriately.

    Example:
        >>> ser = serial.Serial('COM3', 115200)
        >>> data = read_uart(ser, BENCHLAB_CMD.UART_CMD_READ_SENSORS, 100)
        >>> if data:
        >>>     # Process the data
        >>>     pass
    """
    ser.reset_input_buffer()
    ser.write(cmd.toByte())
    time.sleep(0.05)   # give firmware time to process and queue the response
    buffer = ser.read(size)
    if len(buffer) != size:
        logger.warning(
            "UART read incomplete: expected %d, got %d bytes",
            size,
            len(buffer)
        )
        return None
    return buffer


def read_device(ser: serial.Serial) -> Optional[Dict[str, int]]:
    """Read vendor info from the device.

    Args:
        ser (serial.Serial): Opened serial connection to the device.

    Returns:
        Optional[Dict[str, int]]: Dictionary with 'VendorId', 'ProductId', and 'FwVersion' keys,
                                 or None if read failed.

    Example:
        >>> ser = serial.Serial('COM3', 115200)
        >>> info = read_device(ser)
        >>> if info:
        >>>     print(f"Device: {info['VendorId']:02X}:{info['ProductId']:02X}")
    """
    try:
        buffer = read_uart(
            ser,
            BENCHLAB_CMD.UART_CMD_READ_VENDOR_DATA,
            sizeof(VendorDataStruct)
        )
        if buffer is None:
            logger.warning("Failed to read vendor data from device")
            return None
        vendor_struct = VendorDataStruct.from_buffer_copy(buffer)
        return {
            "VendorId": vendor_struct.VendorId,
            "ProductId": vendor_struct.ProductId,
            "FwVersion": vendor_struct.FwVersion,
        }
    except (serial.SerialException, OSError, ValueError, TypeError) as e:
        logger.warning("Failed to read device: %s", e)
        return None


def read_sensors(
    ser: serial.Serial,
    product_id: Optional[int] = None
) -> Optional[Union[SensorStructOriginal, SensorStructCFE]]:
    """Read all sensors from the device.

    Args:
        ser (serial.Serial): Opened serial connection to the device.
        product_id (Optional[int]): Product ID to determine which sensor structure
                                    to use. Use BENCHLAB_CFE_PRODUCT_ID for CFE devices,
                                    or BENCHLAB_ORIGINAL_PRODUCT_ID (or None) for original.

    Returns:
        Optional[Union[SensorStructOriginal, SensorStructCFE]]: Sensor structure object
            containing all sensor data, or None if read failed.
            - Returns SensorStructCFE for CFE devices (product_id=0x11)
            - Returns SensorStructOriginal for original devices (default)

    Note:
        The returned sensor structure contains raw sensor values. Use translate_sensor_struct()
        to convert to human-readable format.

    Example:
        >>> ser = serial.Serial('COM3', 115200)
        >>> # For CFE device
        >>> sensors = read_sensors(ser, product_id=0x11)
        >>> if sensors:
        >>>     # Access raw sensor data
        >>>     voltage = sensors.Vin[0]
    """
    if product_id == BENCHLAB_CFE_PRODUCT_ID:
        buffer = read_uart(
            ser,
            BENCHLAB_CMD.UART_CMD_READ_SENSORS,
            sizeof(SensorStructCFE)
        )
        if buffer is None:
            logger.warning("Failed to read sensors from BENCHLAB-CFE device")
            return None
        return SensorStructCFE.from_buffer_copy(buffer)
    else:
        buffer = read_uart(
            ser,
            BENCHLAB_CMD.UART_CMD_READ_SENSORS,
            sizeof(SensorStructOriginal)
        )
        if buffer is None:
            logger.warning("Failed to read sensors from device")
            return None
        return SensorStructOriginal.from_buffer_copy(buffer)


def read_uid(ser: serial.Serial, retries: int = 3, delay: float = 0.2) -> Optional[str]:
    """Read UID from device with optional retries.

    Args:
        ser (serial.Serial): Opened serial connection to the device.
        retries (int): Number of retry attempts if read fails. Defaults to 3.
        delay (float): Delay in seconds between retry attempts. Defaults to 0.2.

    Returns:
        Optional[str]: Device UID as uppercase hex string, or None if all retries failed.

    Example:
        >>> ser = serial.Serial('COM3', 115200)
        >>> uid = read_uid(ser)
        >>> if uid:
        >>>     print(f"Device UID: {uid}")
    """
    for attempt in range(1, retries + 1):
        buffer = read_uart(
            ser,
            BENCHLAB_CMD.UART_CMD_READ_UID,
            12
        )
        if buffer:
            uid_hex = buffer.hex().upper()
            logger.debug("Raw UID bytes: %s", buffer)
            logger.debug("UID read: %s", uid_hex)
            return uid_hex
        else:
            logger.warning(
                "Attempt %d: Failed to read UID from device",
                attempt
            )
            time.sleep(delay)
    logger.error("Failed to read UID after %d attempts", retries)
    return None