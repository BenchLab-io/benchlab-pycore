#!/usr/bin/env python3
"""
BENCHLAB Device Testing Script

This script provides comprehensive testing for BENCHLAB devices to ensure
the benchlab-pycore library is working correctly with physical hardware.

Usage:
    python test_device.py

Requirements:
    - benchlab-pycore library installed
    - BENCHLAB device connected via USB
    - pyserial >= 3.5
"""

import sys
import serial
import logging
from typing import List, Dict, Optional

# Set up logger for sensor readings
logger = logging.getLogger("test_device")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def print_header(title: str) -> None:
    """Print a formatted test header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_success(message: str) -> None:
    """Print a success message."""
    print(f"SUCCESS: {message}")

def print_error(message: str) -> None:
    """Print an error message."""
    print(f"ERROR: {message}")

def print_info(message: str) -> None:
    """Print an informational message."""
    print(f"INFO: {message}")

def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"WARNING: {message}")

def test_device_discovery() -> List[Dict[str, str]]:
    """Test device discovery functionality."""
    print_header("DEVICE DISCOVERY TEST")
    
    try:
        from benchlab_pycore.core import get_benchlab_ports, find_benchlab_devices, get_fleet_info
    except ImportError as e:
        print_error(f"Failed to import benchlab_pycore.core: {e}")
        return []
    
    # Test 1: Port Discovery
    print_info("Testing port discovery...")
    try:
        ports = get_benchlab_ports()
        print_success(f"Found {len(ports)} BENCHLAB port(s)")
        for port in ports:
            print_info(f"  - {port['port']}")
    except Exception as e:
        print_error(f"Port discovery failed: {e}")
        return []
    
    if not ports:
        print_warning("No BENCHLAB ports found. Please check device connection.")
        return []
    
    # Test 2: Device Discovery
    print_info("\nTesting device discovery...")
    try:
        devices = find_benchlab_devices()
        print_success(f"Found {len(devices)} device(s)")
        for device in devices:
            print_info(f"  - Port: {device['port']}")
            print_info(f"    UID: {device['uid']}")
            print_info(f"    Firmware: {device['firmware']}")
    except Exception as e:
        print_error(f"Device discovery failed: {e}")
        return []
    
    # Test 3: Fleet Info
    print_info("\nTesting fleet information...")
    try:
        fleet = get_fleet_info()
        print_success(f"Found {len(fleet)} device(s) in fleet")
        for device in fleet:
            print_info(f"  - Port: {device['port']}")
            print_info(f"    UID: {device['uid']}")
            print_info(f"    Firmware: {device['firmware']}")
    except Exception as e:
        print_error(f"Fleet info failed: {e}")
        return []
    
    return fleet

def test_serial_connection(device_port: str) -> Optional[serial.Serial]:
    """Test serial connection to a device."""
    print_header("SERIAL CONNECTION TEST")
    
    print_info(f"Testing connection to {device_port}...")
    
    try:
        ser = serial.Serial(device_port, 115200, timeout=1)
        print_success("Serial connection opened successfully")
        return ser
    except serial.SerialException as e:
        print_error(f"Failed to open serial port: {e}")
        return None
    except Exception as e:
        print_error(f"Serial connection error: {e}")
        return None

def test_vendor_info(ser: serial.Serial) -> tuple:
    """Test reading vendor information.
    
    Returns:
        tuple: (success: bool, product_id: int)
    """
    print_header("VENDOR INFORMATION TEST")
    
    try:
        from benchlab_pycore.core import read_device
        
        vendor_info = read_device(ser)
        if vendor_info:
            print_success(f"Vendor info read successfully")
            print_info(f"  Vendor ID: 0x{vendor_info['VendorId']:02X}")
            print_info(f"  Product ID: 0x{vendor_info['ProductId']:02X}")
            print_info(f"  Firmware Version: {vendor_info['FwVersion']}")
            
            product_id = vendor_info['ProductId']
            
            # Check if it's a CFE device
            if product_id == 0x11:
                print_success("Device is a BENCHLAB-CFE (Product ID: 0x11)")
                print_info("CFE-specific sensor names will be used for translation")
            elif product_id == 0x10:
                print_success("Device identification matches original BENCHLAB specifications")
            else:
                print_warning(f"Unknown product ID: 0x{product_id:02X}")
            
            return True, product_id
        else:
            print_error("Failed to read vendor information")
            return False, None
            
    except Exception as e:
        print_error(f"Vendor info test failed: {e}")
        return False, None

def test_uid_reading(ser: serial.Serial) -> bool:
    """Test reading device UID."""
    print_header("UID READING TEST")
    
    try:
        from benchlab_pycore.core import read_uid
        
        uid = read_uid(ser)
        if uid:
            print_success(f"UID read successfully: {uid}")
            
            # Validate UID format (should be 24 hex characters)
            if len(uid) == 24 and all(c in '0123456789ABCDEF' for c in uid):
                print_success("UID format is valid")
                return True
            else:
                print_warning(f"UID format may be invalid: {uid}")
                return True  # Still consider it a success if we can read it
        else:
            print_error("Failed to read UID")
            return False
            
    except Exception as e:
        print_error(f"UID reading test failed: {e}")
        return False

def test_sensor_reading(ser: serial.Serial, product_id: Optional[int] = None) -> bool:
    """Test reading sensor data."""
    print_header("SENSOR READING TEST")
    
    try:
        from benchlab_pycore.core import read_sensors, translate_sensor_struct
        
        print_info(f"Reading raw sensor data (product_id={product_id})...")
        sensors = read_sensors(ser, product_id=product_id)
        
        if sensors:
            print_success("Raw sensor data read successfully")
            
            # Test data translation
            print_info("Translating sensor data...")
            data = translate_sensor_struct(sensors)
            
            if data:
                print_success("Sensor data translation successful")
                
                # Display key metrics
                print_info("\n--- Key Sensor Values ---")
                key_sensors = [
                    'SYS_Power', 'CPU_Power', 'GPU_Power', 'MB_Power',
                    'Chip_Temp', 'Ambient_Temp', 'ATX12V_Voltage'
                ]
                
                for sensor in key_sensors:
                    if sensor in data:
                        print_info(f"  {sensor}: {data[sensor]}")
                        # Log actual readings for verification
                        logger.info("SENSOR_READING: %s = %s", sensor, data[sensor])
                    else:
                        print_warning(f"  {sensor}: Not available")
                
                # Validate reasonable ranges
                print_info("\n--- Data Validation ---")
                validation_passed = True
                
                if 'SYS_Power' in data:
                    power = data['SYS_Power']
                    if power < 0 or power > 5000:  # Unreasonable power range
                        print_warning(f"System power seems unusual: {power}W")
                        validation_passed = False
                    else:
                        print_success(f"System power in reasonable range: {power}W")
                
                if 'Chip_Temp' in data:
                    temp = data['Chip_Temp']
                    if temp < -50 or temp > 150:  # Unreasonable temperature range
                        print_warning(f"Chip temperature seems unusual: {temp} deg C")
                        validation_passed = False
                    else:
                        print_success(f"Chip temperature in reasonable range: {temp} deg C")
                
                if 'ATX12V_Voltage' in data:
                    voltage = data['ATX12V_Voltage']
                    # 12V can be 0 when no load is connected, or in normal range 11.4-12.6V
                    if voltage == 0 or (11.4 <= voltage <= 12.6):
                        print_success(f"ATX12V voltage in reasonable range: {voltage}V")
                    else:
                        print_warning(f"ATX12V voltage seems unusual: {voltage}V")
                        # Don't fail the test for unusual voltage, just warn
                
                # Show all available sensors
                print_info(f"\n--- All Available Sensors ({len(data)} total) ---")
                for key in sorted(data.keys()):
                    print_info(f"  {key}: {data[key]}")
                
                return validation_passed
            else:
                print_error("Failed to translate sensor data")
                return False
        else:
            print_error("Failed to read raw sensor data")
            return False
            
    except Exception as e:
        print_error(f"Sensor reading test failed: {e}")
        return False

def run_comprehensive_test() -> bool:
    """Run all tests in sequence."""
    print_header("BENCHLAB DEVICE COMPREHENSIVE TEST")
    print_info("This script will test your BENCHLAB device connection and functionality.")
    print_info("Please ensure your BENCHLAB device is connected via USB.")
    
    # Test 1: Device Discovery
    fleet = test_device_discovery()
    if not fleet:
        print_error("Device discovery failed. Cannot proceed with tests.")
        return False
    
    # Test 2: Serial Connection (test first device)
    device = fleet[0]
    ser = test_serial_connection(device['port'])
    if not ser:
        print_error("Serial connection failed. Cannot proceed with tests.")
        return False
    
    try:
        # Test 3: Vendor Info (also get product_id for sensor reading)
        vendor_ok, product_id = test_vendor_info(ser)
        
        # Test 4: UID Reading
        uid_ok = test_uid_reading(ser)
        
        # Test 5: Sensor Reading (pass product_id for CFE support)
        sensor_ok = test_sensor_reading(ser, product_id=product_id)
        
        # Summary
        print_header("TEST SUMMARY")
        print_info("Test Results:")
        print_info(f"  Device Discovery: {'SUCCESS' if fleet else 'ERROR'}")
        print_info(f"  Serial Connection: {'SUCCESS' if ser else 'ERROR'}")
        print_info(f"  Vendor Info: {'SUCCESS' if vendor_ok else 'ERROR'}")
        print_info(f"  UID Reading: {'SUCCESS' if uid_ok else 'ERROR'}")
        print_info(f"  Sensor Reading: {'SUCCESS' if sensor_ok else 'ERROR'}")
        
        overall_success = fleet and ser and vendor_ok and uid_ok and sensor_ok
        
        if overall_success:
            print_success("\nALL TESTS PASSED! Your BENCHLAB device is working correctly.")
            print_info("The benchlab-pycore library is ready for use.")
        else:
            print_error("\nSome tests failed. Please check the error messages above.")
            print_info("Common issues:")
            print_info("  - Device not properly connected")
            print_info("  - USB driver issues")
            print_info("  - Device firmware problems")
        
        return overall_success
        
    finally:
        ser.close()
        print_info(f"Serial connection to {device['port']} closed.")

def main():
    """Main entry point."""
    print("BENCHLAB Device Testing Script")
    print("Testing benchlab-pycore library with physical hardware")
    
    try:
        success = run_comprehensive_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()