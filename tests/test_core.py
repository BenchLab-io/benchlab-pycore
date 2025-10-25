# tests/test_core.py

import pytest
from ctypes import Structure, sizeof
from unittest.mock import patch, MagicMock

from benchlab.core import (
    get_benchlab_ports,
    find_benchlab_devices,
    get_fleet_info,
    read_uart,
    read_device,
    read_sensors,
    read_uid,
    translate_sensor_struct,
    format_temp,
    VendorDataStruct,
    PowerSensor,
    FanSensor,
    SensorStruct,
    BENCHLAB_CMD,
    SENSOR_VIN_NUM
)

# -----------------------
# Test core imports
# -----------------------
def test_imports():
    """Ensure all core functions and classes exist and structures are correct."""
    # functions
    assert callable(get_benchlab_ports)
    assert callable(find_benchlab_devices)
    assert callable(get_fleet_info)
    assert callable(read_sensors)
    assert callable(read_uid)
    assert callable(read_device)
    assert callable(translate_sensor_struct)
    
    # ctypes structures
    assert isinstance(VendorDataStruct(), Structure)
    assert isinstance(PowerSensor(), Structure)
    assert isinstance(FanSensor(), Structure)
    assert isinstance(SensorStruct(), Structure)


# -----------------------
# Test mocked serial functions
# -----------------------
@patch("benchlab.core.serial_io.read_uart")
def test_mocked_functions(mock_read_uart):
    """Test core functions using mocks (no hardware needed)."""
    
    # Mock read_uart for read_uid
    mock_read_uart.return_value = bytes(range(12))
    uid = read_uid(MagicMock())
    assert uid == bytes(range(12)).hex().upper()
    
    # Mock read_uart for read_device
    mock_read_uart.return_value = bytes([0xEE, 0x10, 0x01])
    dev_info = read_device(MagicMock())
    assert dev_info == {
        "VendorId": 0xEE,
        "ProductId": 0x10,
        "FwVersion": 0x01,
    }
    
    # Mock read_uart for read_sensors
    mock_read_uart.return_value = bytes([0] * sizeof(SensorStruct))
    sensors = read_sensors(MagicMock())
    assert isinstance(sensors, SensorStruct)


# -----------------------
# Test translate_sensor_struct
# -----------------------
def test_sensor_translation():
    """Test translate_sensor_struct with a sample SensorStruct."""
    s = SensorStruct()
    # Fill sample values
    for i in range(SENSOR_VIN_NUM):
        s.Vin[i] = i * 10
    s.Vdd = 3300
    s.Tchip = 42

    translated = translate_sensor_struct(s)
    
    # Check keys exist and values are reasonable
    # Adapt these depending on how translate_sensor_struct formats keys
    assert isinstance(translated, dict)
    # Example keys
    assert "12V_Voltage" in translated
    assert translated["12V_Voltage"] == 0.0
    assert "3.3V_Current" in translated
    assert translated["3.3V_Current"] == 0.0


# -----------------------
# Test format_temp
# -----------------------
def test_format_temp():
    """Test format_temp utility."""
    val = 0
    formatted = format_temp(val)
    assert isinstance(formatted, float)
    assert formatted == 0.0

    val = 255
    formatted = format_temp(val)
    assert isinstance(formatted, float)
    assert formatted == 25.5

    val = -42
    formatted = format_temp(val)
    assert isinstance(formatted, float)
    assert formatted == -4.2

