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
    format_temp,
    format_chip_temp,
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
    assert callable(format_temp)
    assert callable(format_chip_temp)
    
    # ctypes structures
    assert isinstance(VendorDataStruct(), Structure)
    assert isinstance(PowerSensor(), Structure)
    assert isinstance(FanSensor(), Structure)
    assert isinstance(SensorStruct(), Structure)


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


@patch("benchlab_pycore.core.serial_io.serial.tools.list_ports.comports")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_find_benchlab_devices_success(mock_serial, mock_comports):
    """Test find_benchlab_devices with mock devices."""
    # Mock port objects
    mock_port = Mock()
    mock_port.device = "COM3"
    mock_port.hwid = "USB VID:PID=0483:5740"
    
    mock_comports.return_value = [("COM3", "desc", "USB VID:PID=0483:5740")]
    
    # Mock serial connection
    mock_ser = Mock()
    mock_ser.readline.side_effect = [b"123456789ABC\n", b"1.0\n"]
    mock_serial.return_value = mock_ser
    
    result = find_benchlab_devices()
    assert len(result) == 1
    assert result[0]["port"] == "COM3"
    assert result[0]["uid"] == "123456789ABC"
    assert result[0]["fw"] == "1.0"


@patch("benchlab_pycore.core.serial_io.serial.tools.list_ports.comports")
@patch("benchlab_pycore.core.serial_io.serial.Serial")
def test_find_benchlab_devices_serial_failure(mock_serial, mock_comports):
    """Test find_benchlab_devices with serial connection failure."""
    mock_comports.return_value = [("COM3", "desc", "USB VID:PID=0483:5740")]
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
def test_read_sensors_success(mock_read_uart):
    """Test read_sensors with successful read."""
    mock_read_uart.return_value = bytes([0] * sizeof(SensorStruct))
    
    mock_ser = Mock()
    result = read_sensors(mock_ser)
    
    assert isinstance(result, SensorStruct)


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
# Test sensor translation
# -----------------------
def test_sensor_translation_comprehensive():
    """Test translate_sensor_struct with comprehensive sensor data."""
    s = SensorStruct()
    
    # Set up power readings
    for i in range(11):
        s.PowerReadings[i].Voltage = 12000  # 12V
        s.PowerReadings[i].Current = 5000   # 5A
        s.PowerReadings[i].Power = 60000    # 60W
    
    # Set up VIN readings
    for i in range(SENSOR_VIN_NUM):
        s.Vin[i] = i * 1000  # 0V, 1V, 2V, ..., 12V
    
    # Set up other values
    s.Vdd = 3300
    s.Vref = 2500
    s.Tchip = 420  # 42.0°C
    s.Tamb = 255   # 25.5°C
    s.Hum = 450    # 45.0%
    
    for i in range(4):
        s.Ts[i] = (i + 1) * 100  # 10.0°C, 20.0°C, 30.0°C, 40.0°C
    
    # Set up fans
    for i in range(9):
        s.Fans[i].Enable = 1
        s.Fans[i].Duty = i * 10  # 0%, 10%, 20%, ..., 80%
        s.Fans[i].Tach = 1000 + i * 100  # 1000, 1100, 1200, ..., 1800 RPM
    
    s.FanExtDuty = 50
    
    translated = translate_sensor_struct(s)
    
    # Check power calculations
    assert translated["SYS_Power"] == 660.0  # 11 * 60W
    assert translated["CPU_Power"] == 120.0  # 2 * 60W
    assert translated["GPU_Power"] == 300.0  # 5 * 60W
    assert translated["MB_Power"] == 240.0   # 4 * 60W
    
    # Check voltage conversions
    assert translated["Vdd"] == 3.3
    assert translated["Vref"] == 2.5
    assert translated["VIN_0"] == 0.0
    assert translated["VIN_1"] == 1.0
    assert translated["VIN_12"] == 12.0
    
    # Check temperature conversions
    assert translated["Chip_Temp"] == 42.0
    assert translated["Ambient_Temp"] == 25.5
    assert translated["Humidity"] == 45.0
    assert translated["Temp_Sensor_1"] == 10.0
    assert translated["Temp_Sensor_4"] == 40.0
    
    # Check fan values
    assert translated["Fan1_Duty"] == 0
    assert translated["Fan1_RPM"] == 1000
    assert translated["Fan1_Status"] == 1
    assert translated["Fan9_Duty"] == 80
    assert translated["Fan9_RPM"] == 1800
    assert translated["FanExtDuty"] == 50


# -----------------------
# Test utility functions
# -----------------------
def test_format_temp_valid_range():
    """Test format_temp with valid temperature values."""
    assert format_temp(255) == 25.5      # 25.5°C
    assert format_temp(-42) == -4.2      # -4.2°C
    assert format_temp(0) == 0.0         # 0.0°C
    assert format_temp(1000) == 100.0    # 100.0°C
    assert format_temp(-1000) == -100.0  # -100.0°C


def test_format_temp_invalid_range():
    """Test format_temp with values outside valid range."""
    assert format_temp(1001) is None     # > 100.0°C
    assert format_temp(-1001) is None    # < -100.0°C
    assert format_temp(1500) is None     # > 100.0°C


def test_format_chip_temp():
    """Test format_chip_temp utility."""
    assert format_chip_temp(420) == 42.0
    assert format_chip_temp(0) == 0.0
    assert format_chip_temp(-100) == -10.0
    assert format_chip_temp(1000) == 100.0


def test_format_chip_temp_invalid_range():
    """Test format_chip_temp with values outside valid range."""
    assert format_chip_temp(1001) is None
    assert format_chip_temp(-1001) is None
    assert format_chip_temp(1500) is None


# -----------------------
# Test error handling and edge cases
# -----------------------
def test_sensor_translation_empty_struct():
    """Test translate_sensor_struct with empty SensorStruct."""
    s = SensorStruct()
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
    # When serial exception occurs, the device is not added to the fleet
    assert len(result) == 0


# -----------------------
# Test integration scenarios
# -----------------------
def test_complete_sensor_reading_workflow():
    """Test a complete sensor reading workflow with mock data."""
    # This test simulates reading from a real device
    s = SensorStruct()
    
    # Simulate realistic sensor data
    # CPU power (EPS1 + EPS2)
    s.PowerReadings[0].Power = 150000  # 150W
    s.PowerReadings[1].Power = 100000  # 100W
    
    # Motherboard power (ATX rails)
    s.PowerReadings[2].Power = 50000   # 3.3V: 50W
    s.PowerReadings[3].Power = 100000  # 5V: 100W
    s.PowerReadings[4].Power = 20000   # 5VSB: 20W
    s.PowerReadings[5].Power = 120000  # 12V: 120W
    
    # GPU power (PCIe connectors)
    for i in range(6, 11):
        s.PowerReadings[i].Power = 200000  # 200W each
    
    # Temperature and other sensors
    s.Tchip = 650      # 65.0°C
    s.Tamb = 225       # 22.5°C
    s.Hum = 450        # 45.0%
    
    # Translate and verify
    data = translate_sensor_struct(s)
    
    # Verify calculated values
    assert data["CPU_Power"] == 250.0    # 150W + 100W
    assert data["GPU_Power"] == 1000.0   # 5 * 200W
    assert data["MB_Power"] == 290.0     # 50W + 100W + 20W + 120W
    assert data["SYS_Power"] == 1540.0   # Total system power
    
    assert data["Chip_Temp"] == 65.0
    assert data["Ambient_Temp"] == 22.5
    assert data["Humidity"] == 45.0

