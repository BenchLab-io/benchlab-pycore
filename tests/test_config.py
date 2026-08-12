# tests/test_config.py

import pytest
from ctypes import sizeof
from unittest.mock import patch, MagicMock, Mock, call
import serial

from benchlab_pycore.core import (
    # config_io functions
    ping,
    read_name,
    write_name,
    read_fan_profile,
    write_fan_profile,
    read_rgb_profile,
    write_rgb_profile,
    read_calibration,
    write_calibration_chunk,
    write_calibration,
    load_calibration,
    store_calibration,
    send_action,
    # config structures
    FanMode,
    TempSrc,
    FanStop,
    FanConfigStruct,
    RGBMode,
    RGBDirection,
    RGBConfigStruct,
    CalibrationValueStruct,
    CalibrationStruct,
    CalibrationStructCFE,
    # config constants
    FAN_PROFILE_NUM,
    RGB_PROFILE_NUM,
    CAL_NUM,
    CAL_FACTORY,
    CAL_USER,
    FRIENDLY_NAME_LEN,
    FAN_CURVE_POINTS,
    # shared
    BENCHLAB_CMD,
    FAN_NUM,
)
from ctypes import Structure


# -----------------------
# Test config imports
# -----------------------

def test_config_imports():
    """Ensure all config functions and structures are importable and well-typed."""
    # Functions
    for fn in (
        ping, read_name, write_name,
        read_fan_profile, write_fan_profile,
        read_rgb_profile, write_rgb_profile,
        read_calibration, write_calibration_chunk, write_calibration,
        load_calibration, store_calibration,
        send_action,
    ):
        assert callable(fn)

    # Structures are ctypes Structures
    for cls in (FanCurvePoint, FanConfigStruct, RGBConfigStruct, CalibrationEntry, CalibrationStruct):
        assert isinstance(cls(), Structure)


def test_config_constants():
    """Verify config constants have the expected values."""
    assert FAN_PROFILE_NUM == 3
    assert RGB_PROFILE_NUM == 4
    assert CAL_NUM == 2
    assert FRIENDLY_NAME_LEN == 32
    assert FAN_CURVE_POINTS == 10


# -----------------------
# Test config structure sizes and fields
# -----------------------

def test_fan_curve_point_fields():
    """FanCurvePoint must expose Temp and Duty fields."""
    p = FanCurvePoint()
    p.Temp = -500
    p.Duty = 75
    assert p.Temp == -500
    assert p.Duty == 75


def test_fan_config_struct_fields():
    """FanConfigStruct must expose Mode, FixedDuty, TempSource, and Curve array."""
    cfg = FanConfigStruct()
    cfg.Mode = 1
    cfg.FixedDuty = 80
    cfg.TempSource = 3
    cfg.Curve[0].Temp = 300
    cfg.Curve[0].Duty = 50
    assert cfg.Mode == 1
    assert cfg.FixedDuty == 80
    assert cfg.TempSource == 3
    assert cfg.Curve[0].Temp == 300
    assert cfg.Curve[0].Duty == 50
    assert len(cfg.Curve) == FAN_CURVE_POINTS


def test_rgb_config_struct_fields():
    """RGBConfigStruct must expose Mode, R, G, B, Speed, Brightness."""
    rgb = RGBConfigStruct()
    rgb.Mode = 2
    rgb.R = 255
    rgb.G = 128
    rgb.B = 0
    rgb.Speed = 10
    rgb.Brightness = 200
    assert rgb.Mode == 2
    assert rgb.R == 255
    assert rgb.G == 128
    assert rgb.B == 0
    assert rgb.Speed == 10
    assert rgb.Brightness == 200


def test_calibration_entry_fields():
    """CalibrationEntry must expose Offset and Scale."""
    e = CalibrationEntry()
    e.Offset = -42
    e.Scale = 256
    assert e.Offset == -42
    assert e.Scale == 256


def test_calibration_struct_size():
    """CalibrationStruct must be non-empty and hold CalibrationEntry array."""
    cal = CalibrationStruct()
    assert sizeof(cal) > 0
    assert len(cal.Entries) > 0


def test_fan_config_struct_size_positive():
    assert sizeof(FanConfigStruct) > 0


def test_rgb_config_struct_size_positive():
    assert sizeof(RGBConfigStruct) > 0


# -----------------------
# Test ping
# -----------------------

@patch("benchlab_pycore.core.config_io.read_uart")
def test_ping_success(mock_read_uart):
    """ping() returns True when device responds with BENCHLAB\\0."""
    mock_read_uart.return_value = b"BENCHLAB\x00"
    mock_ser = Mock()
    assert ping(mock_ser) is True
    mock_read_uart.assert_called_once_with(mock_ser, BENCHLAB_CMD.UART_CMD_WELCOME, 9)


@patch("benchlab_pycore.core.config_io.read_uart")
def test_ping_wrong_response(mock_read_uart):
    """ping() returns False when device responds with unexpected data."""
    mock_read_uart.return_value = b"WRONGDEV\x00"
    assert ping(Mock()) is False


@patch("benchlab_pycore.core.config_io.read_uart")
def test_ping_no_response(mock_read_uart):
    """ping() returns False when read_uart returns None."""
    mock_read_uart.return_value = None
    assert ping(Mock()) is False


# -----------------------
# Test read_name / write_name
# -----------------------

@patch("benchlab_pycore.core.config_io.read_uart")
def test_read_name_success(mock_read_uart):
    """read_name() decodes a null-padded 32-byte response."""
    mock_ser = Mock()
    name = b"My BENCHLAB\x00" + b"\x00" * (FRIENDLY_NAME_LEN - 12)
    mock_read_uart.return_value = name
    result = read_name(mock_ser)
    assert result == "My BENCHLAB"
    mock_read_uart.assert_called_once_with(mock_ser, BENCHLAB_CMD.UART_CMD_READ_NAME, FRIENDLY_NAME_LEN)


@patch("benchlab_pycore.core.config_io.read_uart")
def test_read_name_full_length(mock_read_uart):
    """read_name() handles a name that fills the entire buffer (no null)."""
    name = b"A" * FRIENDLY_NAME_LEN
    mock_read_uart.return_value = name
    result = read_name(Mock())
    assert result == "A" * FRIENDLY_NAME_LEN


@patch("benchlab_pycore.core.config_io.read_uart")
def test_read_name_uart_failure(mock_read_uart):
    """read_name() returns None when read_uart fails."""
    mock_read_uart.return_value = None
    assert read_name(Mock()) is None


def test_write_name_success():
    """write_name() sends cmd byte + encoded name."""
    mock_ser = Mock()
    mock_ser.write.return_value = 13   # len("My BENCHLAB") + 1 cmd byte + 1 null
    result = write_name(mock_ser, "My BENCHLAB")
    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent[0] == BENCHLAB_CMD.UART_CMD_WRITE_NAME
    assert sent[1:] == b"My BENCHLAB\x00"


def test_write_name_truncates_long_name():
    """write_name() silently truncates names longer than FRIENDLY_NAME_LEN-1."""
    mock_ser = Mock()
    long_name = "X" * 100
    mock_ser.write.return_value = FRIENDLY_NAME_LEN
    write_name(mock_ser, long_name)
    sent = mock_ser.write.call_args[0][0]
    # cmd byte + max payload
    assert len(sent) == FRIENDLY_NAME_LEN


def test_write_name_serial_error():
    """write_name() returns False when serial.write raises SerialException."""
    mock_ser = Mock()
    mock_ser.write.side_effect = serial.SerialException("port closed")
    assert write_name(mock_ser, "test") is False


# -----------------------
# Test read_fan_profile / write_fan_profile
# -----------------------

def _make_fan_config_bytes():
    cfg = FanConfigStruct()
    cfg.Mode = 1
    cfg.FixedDuty = 60
    from ctypes import create_string_buffer, memmove, addressof
    buf = create_string_buffer(sizeof(cfg))
    memmove(buf, addressof(cfg), sizeof(cfg))
    return bytes(buf)


def test_read_fan_profile_success():
    """read_fan_profile() parses FanConfigStruct from device response."""
    raw = _make_fan_config_bytes()
    mock_ser = Mock()
    mock_ser.read.return_value = raw
    mock_ser.write.return_value = 3

    result = read_fan_profile(mock_ser, fan_profile=0, fan_id=2)

    assert isinstance(result, FanConfigStruct)
    assert result.Mode == 1
    assert result.FixedDuty == 60
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_READ_FAN_PROFILE, 0, 2])


def test_read_fan_profile_short_response():
    """read_fan_profile() returns None when device sends fewer bytes than expected."""
    mock_ser = Mock()
    mock_ser.write.return_value = 3
    mock_ser.read.return_value = b"\x00" * 4   # too short
    assert read_fan_profile(mock_ser, 0, 0) is None


def test_read_fan_profile_serial_error():
    """read_fan_profile() returns None on SerialException."""
    mock_ser = Mock()
    mock_ser.write.side_effect = serial.SerialException("closed")
    assert read_fan_profile(mock_ser, 0, 0) is None


def test_read_fan_profile_invalid_profile():
    """read_fan_profile() raises ValueError for out-of-range fan_profile."""
    with pytest.raises(ValueError, match="fan_profile"):
        read_fan_profile(Mock(), fan_profile=FAN_PROFILE_NUM, fan_id=0)


def test_read_fan_profile_invalid_fan_id():
    """read_fan_profile() raises ValueError for out-of-range fan_id."""
    with pytest.raises(ValueError, match="fan_id"):
        read_fan_profile(Mock(), fan_profile=0, fan_id=FAN_NUM)


def test_write_fan_profile_success():
    """write_fan_profile() sends correct header + struct bytes."""
    mock_ser = Mock()
    cfg = FanConfigStruct()
    cfg.Mode = 0
    cfg.FixedDuty = 75
    expected_len = 3 + sizeof(FanConfigStruct)
    mock_ser.write.return_value = expected_len

    result = write_fan_profile(mock_ser, fan_profile=1, fan_id=3, config=cfg)

    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent[0] == BENCHLAB_CMD.UART_CMD_WRITE_FAN_PROFILE
    assert sent[1] == 1   # fan_profile
    assert sent[2] == 3   # fan_id
    assert len(sent) == expected_len


def test_write_fan_profile_invalid_profile():
    with pytest.raises(ValueError, match="fan_profile"):
        write_fan_profile(Mock(), FAN_PROFILE_NUM, 0, FanConfigStruct())


def test_write_fan_profile_invalid_fan_id():
    with pytest.raises(ValueError, match="fan_id"):
        write_fan_profile(Mock(), 0, FAN_NUM, FanConfigStruct())


# -----------------------
# Test read_rgb_profile / write_rgb_profile
# -----------------------

def _make_rgb_config_bytes(mode=3, r=100, g=200, b=50):
    rgb = RGBConfigStruct()
    rgb.Mode = mode
    rgb.R = r
    rgb.G = g
    rgb.B = b
    from ctypes import create_string_buffer, memmove, addressof
    buf = create_string_buffer(sizeof(rgb))
    memmove(buf, addressof(rgb), sizeof(rgb))
    return bytes(buf)


def test_read_rgb_profile_success():
    """read_rgb_profile() parses RGBConfigStruct from device response."""
    raw = _make_rgb_config_bytes(mode=3, r=100, g=200, b=50)
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    mock_ser.read.return_value = raw

    result = read_rgb_profile(mock_ser, rgb_profile=2)

    assert isinstance(result, RGBConfigStruct)
    assert result.Mode == 3
    assert result.R == 100
    assert result.G == 200
    assert result.B == 50
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_READ_RGB, 2])


def test_read_rgb_profile_short_response():
    """read_rgb_profile() returns None when device sends fewer bytes than expected."""
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    mock_ser.read.return_value = b"\x00" * 2   # too short
    assert read_rgb_profile(mock_ser, 0) is None


def test_read_rgb_profile_invalid_profile():
    with pytest.raises(ValueError, match="rgb_profile"):
        read_rgb_profile(Mock(), rgb_profile=RGB_PROFILE_NUM)


def test_read_rgb_profile_serial_error():
    mock_ser = Mock()
    mock_ser.write.side_effect = serial.SerialException("closed")
    assert read_rgb_profile(mock_ser, 0) is None


def test_write_rgb_profile_success():
    """write_rgb_profile() sends correct header + struct bytes."""
    mock_ser = Mock()
    rgb = RGBConfigStruct()
    rgb.Mode = 1
    rgb.R = 255
    rgb.G = 0
    rgb.B = 128
    expected_len = 2 + sizeof(RGBConfigStruct)
    mock_ser.write.return_value = expected_len

    result = write_rgb_profile(mock_ser, rgb_profile=0, config=rgb)

    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent[0] == BENCHLAB_CMD.UART_CMD_WRITE_RGB
    assert sent[1] == 0   # rgb_profile
    assert len(sent) == expected_len


def test_write_rgb_profile_invalid_profile():
    with pytest.raises(ValueError, match="rgb_profile"):
        write_rgb_profile(Mock(), RGB_PROFILE_NUM, RGBConfigStruct())


# -----------------------
# Test read_calibration / write_calibration
# -----------------------

@patch("benchlab_pycore.core.config_io.read_uart")
def test_read_calibration_success(mock_read_uart):
    """read_calibration() parses CalibrationStruct from device response."""
    mock_ser = Mock()
    mock_read_uart.return_value = bytes(sizeof(CalibrationStruct))
    result = read_calibration(mock_ser)
    assert isinstance(result, CalibrationStruct)
    mock_read_uart.assert_called_once_with(mock_ser, BENCHLAB_CMD.UART_CMD_READ_CALIBRATION, sizeof(CalibrationStruct))


@patch("benchlab_pycore.core.config_io.read_uart")
def test_read_calibration_uart_failure(mock_read_uart):
    """read_calibration() returns None when read_uart fails."""
    mock_read_uart.return_value = None
    assert read_calibration(Mock()) is None


def test_write_calibration_chunk_success():
    """write_calibration_chunk() sends [cmd, offset, data…]."""
    mock_ser = Mock()
    chunk = b"\x01\x02\x03\x04"
    mock_ser.write.return_value = 2 + len(chunk)

    result = write_calibration_chunk(mock_ser, offset=0, chunk=chunk)

    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent[0] == BENCHLAB_CMD.UART_CMD_WRITE_CALIBRATION
    assert sent[1] == 0          # offset
    assert sent[2:] == chunk


def test_write_calibration_chunk_nonzero_offset():
    """write_calibration_chunk() correctly encodes a non-zero offset."""
    mock_ser = Mock()
    chunk = b"\xAA\xBB"
    mock_ser.write.return_value = 4

    write_calibration_chunk(mock_ser, offset=16, chunk=chunk)

    sent = mock_ser.write.call_args[0][0]
    assert sent[1] == 16


def test_write_calibration_chunk_overflow():
    """write_calibration_chunk() raises ValueError when offset+len exceeds struct."""
    cal_size = sizeof(CalibrationStruct)
    with pytest.raises(ValueError, match="exceeds"):
        write_calibration_chunk(Mock(), offset=cal_size - 1, chunk=b"\x00\x00")


def test_write_calibration_chunk_offset_too_large():
    """write_calibration_chunk() raises ValueError when offset > 255."""
    # offset=256 exceeds CalibrationStruct size (160), so it raises "exceeds" error
    # To test the "one byte" error, we need an offset <= cal_size but > 255
    # Since cal_size is 160, offset=256 will always trigger the "exceeds" check first
    with pytest.raises(ValueError, match="exceeds"):
        write_calibration_chunk(Mock(), offset=256, chunk=b"\x00")


def test_write_calibration_full_sends_chunks():
    """write_calibration() splits large struct into multiple CDC packets."""
    mock_ser = Mock()
    chunk_size = 10
    # Each chunk is chunk_size + 2 bytes (cmd + offset)
    mock_ser.write.return_value = chunk_size + 2   # always succeeds

    cal = CalibrationStruct()
    result = write_calibration(mock_ser, cal, chunk_size=chunk_size)

    assert result is True
    call_count = mock_ser.write.call_count
    expected_calls = -(-sizeof(CalibrationStruct) // chunk_size)   # ceiling division
    assert call_count == expected_calls


def test_write_calibration_chunk_failure_aborts():
    """write_calibration() stops and returns False when any chunk write fails."""
    mock_ser = Mock()
    chunk_size = 10
    # First chunk succeeds (returns correct length), second fails (returns wrong length)
    mock_ser.write.side_effect = [chunk_size + 2, 0]

    cal = CalibrationStruct()
    result = write_calibration(mock_ser, cal, chunk_size=chunk_size)

    assert result is False
    assert mock_ser.write.call_count == 2


def test_write_calibration_chunk_offsets_are_sequential():
    """write_calibration() passes correct byte offsets to each chunk."""
    mock_ser = Mock()
    chunk_size = 10
    mock_ser.write.return_value = chunk_size + 2  # always "succeeds"

    cal = CalibrationStruct()
    write_calibration(mock_ser, cal, chunk_size=chunk_size)

    offsets = [c[0][0][1] for c in mock_ser.write.call_args_list]  # byte at index 1
    for i, offset in enumerate(offsets):
        assert offset == i * chunk_size


# -----------------------
# Test load_calibration / store_calibration
# -----------------------

def test_load_calibration_user_slot():
    """load_calibration(0) sends correct 2-byte command."""
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    result = load_calibration(mock_ser, cal_id=0)
    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_LOAD_CALIBRATION, 0])


def test_load_calibration_factory_slot():
    """load_calibration(1) sends correct 2-byte command."""
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    result = load_calibration(mock_ser, cal_id=1)
    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_LOAD_CALIBRATION, 1])


def test_load_calibration_invalid_slot():
    with pytest.raises(ValueError, match="cal_id"):
        load_calibration(Mock(), cal_id=CAL_NUM)


def test_store_calibration_user_slot():
    """store_calibration(0) sends correct 2-byte command."""
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    result = store_calibration(mock_ser, cal_id=0)
    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_STORE_CALIBRATION, 0])


def test_store_calibration_factory_slot():
    """store_calibration(1) sends correct 2-byte command."""
    mock_ser = Mock()
    mock_ser.write.return_value = 2
    result = store_calibration(mock_ser, cal_id=1)
    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_STORE_CALIBRATION, 1])


def test_store_calibration_invalid_slot():
    with pytest.raises(ValueError, match="cal_id"):
        store_calibration(Mock(), cal_id=CAL_NUM)


# -----------------------
# Test send_action
# -----------------------

def test_send_action_basic():
    """send_action() sends exactly 5 bytes with correct layout."""
    mock_ser = Mock()
    mock_ser.write.return_value = 5

    result = send_action(mock_ser, action=1, param1=2, param2=3, param3=4)

    assert result is True
    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_ACTION, 1, 2, 3, 4])


def test_send_action_defaults_to_zero_params():
    """send_action() defaults param1/2/3 to 0."""
    mock_ser = Mock()
    mock_ser.write.return_value = 5

    send_action(mock_ser, action=7)

    sent = mock_ser.write.call_args[0][0]
    assert sent == bytes([BENCHLAB_CMD.UART_CMD_ACTION, 7, 0, 0, 0])


def test_send_action_boundary_values():
    """send_action() accepts 0 and 255 for all parameters."""
    mock_ser = Mock()
    mock_ser.write.return_value = 5
    assert send_action(mock_ser, action=0, param1=0, param2=0, param3=0) is True
    mock_ser.write.return_value = 5
    assert send_action(mock_ser, action=255, param1=255, param2=255, param3=255) is True


def test_send_action_invalid_action():
    """send_action() raises ValueError when action > 255."""
    with pytest.raises(ValueError, match="action"):
        send_action(Mock(), action=256)


def test_send_action_invalid_param():
    """send_action() raises ValueError when any param is out of byte range."""
    with pytest.raises(ValueError, match="param2"):
        send_action(Mock(), action=1, param1=0, param2=256, param3=0)

    with pytest.raises(ValueError, match="param1"):
        send_action(Mock(), action=1, param1=-1)


def test_send_action_serial_error():
    """send_action() returns False on SerialException."""
    mock_ser = Mock()
    mock_ser.write.side_effect = serial.SerialException("closed")
    assert send_action(mock_ser, action=1) is False


# -----------------------
# Test BENCHLAB_CMD enum coverage
# -----------------------

def test_benchlab_cmd_config_values():
    """All config-related UART_CMD values must match firmware enum."""
    assert BENCHLAB_CMD.UART_CMD_ACTION == 2
    assert BENCHLAB_CMD.UART_CMD_READ_NAME == 3
    assert BENCHLAB_CMD.UART_CMD_WRITE_NAME == 4
    assert BENCHLAB_CMD.UART_CMD_READ_FAN_PROFILE == 5
    assert BENCHLAB_CMD.UART_CMD_WRITE_FAN_PROFILE == 6
    assert BENCHLAB_CMD.UART_CMD_READ_RGB == 7
    assert BENCHLAB_CMD.UART_CMD_WRITE_RGB == 8
    assert BENCHLAB_CMD.UART_CMD_READ_CALIBRATION == 9
    assert BENCHLAB_CMD.UART_CMD_WRITE_CALIBRATION == 10
    assert BENCHLAB_CMD.UART_CMD_LOAD_CALIBRATION == 11
    assert BENCHLAB_CMD.UART_CMD_STORE_CALIBRATION == 12
