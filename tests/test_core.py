# tests/test_core.py

import pytest
from ctypes import Structure, sizeof
from unittest.mock import patch, MagicMock, Mock
import serial

from benchlab_pycore.core import (
    get_benchlab_ports,
    find_benchlab_devices,
    get_fleet_info,
    read_uart,
    read_device,
    read_sensors,
    read_uid,
    translate_sensor_struct,
    translate_sensor_struct_original,
    translate_sensor_struct_bl2,
    format_temp,
    format_chip_temp,
    VendorDataStruct,
    PowerSensor,
    FanSensor,
    SensorStructOriginal,
    SensorStructBL2,
    BENCHLAB_CMD,
    # ORIGINAL variant constants
    SENSOR_VIN_NUM_ORIGINAL,
    SENSOR_POWER_NUM_ORIGINAL,
    SENSOR_TS_NUM_ORIGINAL,
    SENSOR_POWER_NAMES_ORIGINAL,
    SENSOR_TS_NAMES_ORIGINAL,
    BENCHLAB_ORIGINAL_PRODUCT_ID,
    # BL2 variant constants
    SENSOR_VIN_NUM_BL2,
    SENSOR_POWER_NUM_BL2,
    SENSOR_TS_NUM_BL2,
    SENSOR_POWER_NAMES_BL2,
    SENSOR_TS_NAMES_BL2,
    BENCHLAB_BL2_PRODUCT_ID,
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
    assert callable(translate_sensor_struct_original)
    assert callable(translate_sensor_struct_bl2)
    assert callable(format_temp)
    assert callable(format_chip_temp)
    
    # ctypes structures
    assert isinstance(VendorDataStruct(), Structure)
    assert isinstance(PowerSensor(), Structure)
    assert isinstance(FanSensor(), Structure)
    assert isinstance(SensorStructOriginal(), Structure)
    assert isinstance(SensorStructBL2(), Structure)


# -----------------------
# Test device discovery functions
# -----------------------
@patch("benchlab_pycore.core.serial_io.serial.tools.list_ports.comports")
def test_get_benchlab_ports_success(mock_comports):
    """Test get_benchlab_ports with mock ports."""
    # Mock port objects
    mock_port1 = Mock()
    mock_port1.device = "COM3"
    mock_port1.hwid = "USB VID:PID=0483:5740"
    
    mock_port2 = Mock()
    mock_port2.device = "COM4"
    mock_port2.hwid = "USB VID:PID=1234:5678"  # Not BENCHLAB
    
    mock_comports.return_value = [mock_port1, mock_port2]
    
    result = get_benchlab_ports()
    assert result == [{"port": "COM3"}]


@patch("benchlab_pycore.core.serial_io.serial.tools.list_ports.comports")
def test_get_benchlab_ports_serial_exception(mock_comports):
    """Test get_benchlab_ports with serial exception."""
    mock_comports.side_effect = serial.SerialException("Port enumeration failed")
    
    with pytest.raises(serial.SerialException):
        get_benchlab_ports()


@patch("benchlab_pycore.core.serial_io.get_benchlab_ports")
@patch("benchlab_pycore.core.serial_io.read_device")
@patch("benchlab_pycore.core.serial_io.read_uid")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_find_benchlab_devices_success(mock_serial, mock_read_uid, mock_read_device, mock_get_ports):
    """Test find_benchlab_devices with mock devices."""
    mock_get_ports.return_value = [{"port": "COM3"}]
    mock_read_device.return_value = {"FwVersion": "1.0"}
    mock_read_uid.return_value = "123456789ABC"

    result = find_benchlab_devices()
    assert len(result) == 1
    assert result[0]["port"] == "COM3"
    assert result[0]["uid"] == "123456789ABC"
    assert result[0]["fw"] == "1.0"


@patch("benchlab_pycore.core.serial_io.get_benchlab_ports")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_find_benchlab_devices_serial_failure(mock_serial, mock_get_ports):
    """Test find_benchlab_devices with serial connection failure."""
    mock_get_ports.return_value = [{"port": "COM3"}]
    mock_serial.side_effect = serial.SerialException("Cannot open port")

    result = find_benchlab_devices()
    assert len(result) == 1
    assert result[0]["port"] == "COM3"
    assert result[0]["uid"] == "?"
    assert result[0]["fw"] == "?"


# -----------------------
# Test serial communication functions
# -----------------------
@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_device_success(mock_read_uart):
    """Test read_device with successful read."""
    mock_read_uart.return_value = bytes([0xEE, 0x10, 0x01])
    
    mock_ser = Mock()
    result = read_device(mock_ser)
    
    assert result == {
        "VendorId": 0xEE,
        "ProductId": 0x10,
        "FwVersion": 0x01,
    }


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_device_uart_failure(mock_read_uart):
    """Test read_device with UART read failure."""
    mock_read_uart.return_value = None
    
    mock_ser = Mock()
    result = read_device(mock_ser)
    
    assert result is None


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_sensors_original_success(mock_read_uart):
    """Test read_sensors with ORIGINAL product_id returns SensorStructOriginal."""
    mock_read_uart.return_value = bytes([0] * sizeof(SensorStructOriginal))
    
    mock_ser = Mock()
    result = read_sensors(mock_ser, product_id=BENCHLAB_ORIGINAL_PRODUCT_ID)
    
    assert isinstance(result, SensorStructOriginal)


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_sensors_bl2_success(mock_read_uart):
    """Test read_sensors with BL2 product_id returns SensorStructBL2."""
    mock_read_uart.return_value = bytes([0] * sizeof(SensorStructBL2))
    
    mock_ser = Mock()
    result = read_sensors(mock_ser, product_id=BENCHLAB_BL2_PRODUCT_ID)
    
    assert isinstance(result, SensorStructBL2)


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_sensors_uart_failure(mock_read_uart):
    """Test read_sensors with UART read failure."""
    mock_read_uart.return_value = None
    
    mock_ser = Mock()
    result = read_sensors(mock_ser)
    
    assert result is None


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_uid_success(mock_read_uart):
    """Test read_uid with successful read."""
    mock_read_uart.return_value = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x11, 0x22, 0x33, 0x44])
    
    mock_ser = Mock()
    result = read_uid(mock_ser)
    
    assert result == "123456789ABCDEF011223344"


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_uid_retries(mock_read_uart):
    """Test read_uid with retries."""
    mock_read_uart.side_effect = [None, None, bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x11, 0x22, 0x33, 0x44])]
    
    mock_ser = Mock()
    result = read_uid(mock_ser, retries=3, delay=0.1)
    
    assert result == "123456789ABCDEF011223344"
    assert mock_read_uart.call_count == 3


@patch("benchlab_pycore.core.serial_io.read_uart")
def test_read_uid_all_retries_fail(mock_read_uart):
    """Test read_uid when all retries fail."""
    mock_read_uart.return_value = None
    
    mock_ser = Mock()
    result = read_uid(mock_ser, retries=3, delay=0.1)
    
    assert result is None
    assert mock_read_uart.call_count == 3


# -----------------------
# Test variant constants
# -----------------------
def test_original_variant_constants():
    """Test that ORIGINAL variant constants are correctly defined."""
    assert BENCHLAB_ORIGINAL_PRODUCT_ID == 0x10
    assert SENSOR_VIN_NUM_ORIGINAL == 13
    assert SENSOR_POWER_NUM_ORIGINAL == 11
    assert SENSOR_TS_NUM_ORIGINAL == 4
    assert len(SENSOR_POWER_NAMES_ORIGINAL) == 11
    assert len(SENSOR_TS_NAMES_ORIGINAL) == 4
    assert SENSOR_POWER_NAMES_ORIGINAL[0] == "EPS1"
    assert SENSOR_TS_NAMES_ORIGINAL[0] == "TS_1"


def test_bl2_variant_constants():
    """Test that BL2 variant constants are correctly defined."""
    assert BENCHLAB_BL2_PRODUCT_ID == 0x11
    assert SENSOR_VIN_NUM_BL2 == 13
    assert SENSOR_POWER_NUM_BL2 == 23
    assert SENSOR_TS_NUM_BL2 == 8
    assert len(SENSOR_POWER_NAMES_BL2) == 23
    assert len(SENSOR_TS_NAMES_BL2) == 8
    assert SENSOR_POWER_NAMES_BL2[0] == "EPS1"
    assert SENSOR_POWER_NAMES_BL2[11] == "HPWR1_W1"
    assert SENSOR_POWER_NAMES_BL2[22] == "HPWR2_W6"
    assert SENSOR_TS_NAMES_BL2[4] == "TS_HPWR1_IN"
    assert SENSOR_TS_NAMES_BL2[7] == "TS_HPWR2_OUT"


# -----------------------
# Test variant structures
# -----------------------
def test_original_structure():
    """Test that ORIGINAL structure is properly defined."""
    s = SensorStructOriginal()
    assert len(s.PowerReadings) == SENSOR_POWER_NUM_ORIGINAL
    assert len(s.Ts) == SENSOR_TS_NUM_ORIGINAL
    assert len(s.Fans) == 9
    assert len(s.Vin) == SENSOR_VIN_NUM_ORIGINAL


def test_bl2_structure():
    """Test that BL2 structure is properly defined."""
    s = SensorStructBL2()
    assert len(s.PowerReadings) == SENSOR_POWER_NUM_BL2
    assert len(s.Ts) == SENSOR_TS_NUM_BL2
    assert len(s.Fans) == 9
    assert len(s.Vin) == SENSOR_VIN_NUM_BL2


def test_bl2_structure_larger_than_original():
    """Test that BL2 structure is larger than ORIGINAL due to more sensors."""
    assert sizeof(SensorStructBL2) > sizeof(SensorStructOriginal)


# -----------------------
# Test ORIGINAL variant translation
# -----------------------
def test_original_sensor_translation():
    """Test translate_sensor_struct_original with comprehensive sensor data."""
    s = SensorStructOriginal()
    
    # Set up power readings
    for i in range(SENSOR_POWER_NUM_ORIGINAL):
        s.PowerReadings[i].Voltage = 12000
        s.PowerReadings[i].Current = 5000
        s.PowerReadings[i].Power = 60000
    
    # Set up VIN readings
    for i in range(SENSOR_VIN_NUM_ORIGINAL):
        s.Vin[i] = (i + 1) * 1000
    
    # Set up other values
    s.Vdd = 3300
    s.Vref = 2500
    s.Tchip = 42
    s.Tamb = 255
    s.Hum = 450
    
    for i in range(SENSOR_TS_NUM_ORIGINAL):
        s.Ts[i] = (i + 1) * 100
    
    # Set up fans
    for i in range(9):
        s.Fans[i].Enable = 1
        s.Fans[i].Duty = i * 10
        s.Fans[i].Tach = 1000 + i * 100
    
    s.FanExtDuty = 50
    
    translated = translate_sensor_struct_original(s)
    
    # Check power calculations
    assert translated["SYS_Power"] == 660.0
    assert translated["CPU_Power"] == 120.0
    assert translated["GPU_Power"] == 300.0
    assert translated["MB_Power"] == 240.0
    
    # Check power sensor names
    assert "EPS1_Voltage" in translated
    assert "HPWR2_Power" in translated
    
    # Check voltage conversions
    assert translated["Vdd"] == 3.3
    assert translated["Vref"] == 2.5
    
    # Check temperature conversions
    assert translated["Chip_Temp"] == 42.0
    assert translated["Ambient_Temp"] == 25.5
    assert translated["TS_1"] == 10.0
    assert translated["TS_4"] == 40.0
    
    # Check fan values
    assert translated["Fan1_Duty"] == 0
    assert translated["Fan9_RPM"] == 1800


# -----------------------
# Test BL2 variant translation
# -----------------------
def test_bl2_sensor_translation():
    """Test translate_sensor_struct_bl2 with comprehensive sensor data."""
    s = SensorStructBL2()
    
    # Set up power readings (23 sensors)
    for i in range(SENSOR_POWER_NUM_BL2):
        s.PowerReadings[i].Voltage = 12000
        s.PowerReadings[i].Current = 5000
        s.PowerReadings[i].Power = 60000
    
    # Set up VIN readings
    for i in range(SENSOR_VIN_NUM_BL2):
        s.Vin[i] = (i + 1) * 1000
    
    # Set up other values
    s.Vdd = 3300
    s.Vref = 2500
    s.Tchip = 42
    s.Tamb = 255
    s.Hum = 450
    
    # Set up 8 temperature sensors
    for i in range(SENSOR_TS_NUM_BL2):
        s.Ts[i] = (i + 1) * 100
    
    # Set up fans
    for i in range(9):
        s.Fans[i].Enable = 1
        s.Fans[i].Duty = i * 10
        s.Fans[i].Tach = 1000 + i * 100
    
    s.FanExtDuty = 50
    
    translated = translate_sensor_struct_bl2(s)
    
    # Check power calculations
    assert translated["SYS_Power"] == 660.0
    assert translated["CPU_Power"] == 120.0
    assert translated["GPU_Power"] == 300.0
    assert translated["MB_Power"] == 240.0
    
    # Check original power sensor names
    assert "EPS1_Voltage" in translated
    assert "HPWR2_Power" in translated
    
    # Check BL2-specific power sensor names
    assert "HPWR1_W1_Voltage" in translated
    assert "HPWR2_W6_Power" in translated
    
    # Check temperature conversions
    assert translated["Chip_Temp"] == 42.0
    assert translated["Ambient_Temp"] == 25.5
    assert translated["TS_1"] == 10.0
    assert translated["TS_4"] == 40.0
    assert translated["TS_HPWR1_IN"] == 50.0
    assert translated["TS_HPWR1_OUT"] == 60.0
    assert translated["TS_HPWR2_IN"] == 70.0
    assert translated["TS_HPWR2_OUT"] == 80.0
    
    # Check fan values
    assert translated["Fan1_Duty"] == 0
    assert translated["Fan9_RPM"] == 1800


# -----------------------
# Test dispatcher function
# -----------------------
def test_translate_sensor_struct_dispatcher_original():
    """Test that dispatcher routes to original translator correctly."""
    s = SensorStructOriginal()
    for i in range(SENSOR_POWER_NUM_ORIGINAL):
        s.PowerReadings[i].Power = 10000
    s.Tchip = 30
    s.Tamb = 200
    s.Hum = 500
    
    # Should use original translator by default
    translated = translate_sensor_struct(s)
    assert "EPS1_Power" in translated
    assert "TS_1" in translated


def test_translate_sensor_struct_dispatcher_bl2():
    """Test that dispatcher routes to BL2 translator correctly."""
    s = SensorStructBL2()
    for i in range(SENSOR_POWER_NUM_BL2):
        s.PowerReadings[i].Power = 10000
    s.Tchip = 30
    s.Tamb = 200
    s.Hum = 500
    for i in range(SENSOR_TS_NUM_BL2):
        s.Ts[i] = (i + 1) * 100
    
    # Should use BL2 translator by type detection
    translated = translate_sensor_struct(s)
    assert "HPWR1_W1_Power" in translated
    assert "TS_HPWR1_IN" in translated
    
    # Should also use BL2 translator with explicit product_id
    translated2 = translate_sensor_struct(s, product_id=BENCHLAB_BL2_PRODUCT_ID)
    assert "HPWR2_W6_Power" in translated2


# -----------------------
# Test utility functions
# -----------------------
def test_format_temp_valid_range():
    """Test format_temp with valid temperature values."""
    assert format_temp(255) == 25.5
    assert format_temp(-42) == -4.2
    assert format_temp(0) == 0.0
    assert format_temp(1000) == 100.0
    assert format_temp(-1000) == -100.0


def test_format_temp_invalid_range():
    """Test format_temp with values outside valid range."""
    assert format_temp(1001) is None
    assert format_temp(-1001) is None
    assert format_temp(1500) is None


def test_format_chip_temp():
    """Test format_chip_temp utility."""
    assert format_chip_temp(42) == 42.0
    assert format_chip_temp(0) == 0.0
    assert format_chip_temp(-100) == -100.0
    assert format_chip_temp(100) == 100.0


def test_format_chip_temp_invalid_range():
    """Test format_chip_temp with values outside valid range."""
    assert format_chip_temp(1001) is None
    assert format_chip_temp(-1001) is None
    assert format_chip_temp(1500) is None


# -----------------------
# Test error handling and edge cases
# -----------------------
def test_sensor_translation_empty_struct():
    """Test translate_sensor_struct with empty SensorStructOriginal."""
    s = SensorStructOriginal()
    translated = translate_sensor_struct(s)
    
    # Should still return a dict with all expected keys
    assert isinstance(translated, dict)
    assert "SYS_Power" in translated
    assert "CPU_Power" in translated
    assert "Chip_Temp" in translated
    assert "Fan1_Duty" in translated


@patch("benchlab_pycore.core.serial_io.get_benchlab_ports")
@patch("benchlab_pycore.core.serial_io.read_device")
@patch("benchlab_pycore.core.serial_io.read_uid")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_get_fleet_info_no_devices(mock_serial, mock_read_uid, mock_read_device, mock_get_ports):
    """Test get_fleet_info when no devices are found."""
    mock_get_ports.return_value = []
    
    result = get_fleet_info()
    assert result == []


@patch("benchlab_pycore.core.serial_io.get_benchlab_ports")
@patch("benchlab_pycore.core.serial_io.read_device")
@patch("benchlab_pycore.core.serial_io.read_uid")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_get_fleet_info_device_read_failure(mock_serial, mock_read_uid, mock_read_device, mock_get_ports):
    """Test get_fleet_info when device reading fails."""
    mock_get_ports.return_value = [{"port": "COM3"}]
    mock_read_device.return_value = None
    mock_read_uid.return_value = "123456789ABC"
    mock_serial.side_effect = serial.SerialException("Cannot open port")
    
    result = get_fleet_info()
    assert len(result) == 0