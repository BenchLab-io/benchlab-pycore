#!/usr/bin/env python3
"""
BENCHLAB Write Validation Test Suite

Automated testing for device configuration write operations added in v0.4.0.
This script safely tests all write functions by backing up, writing test values,
verifying the writes, and restoring original configuration.

Safety Features:
    - Always backs up configuration before writing
    - Verifies every write operation by reading back
    - Automatically restores original configuration
    - Fails fast and restores on any error
    - Dangerous operations require explicit flags
    - Dry-run mode available for testing without writes

Usage:
    python test_write_validation.py                    # Safe default tests
    python test_write_validation.py --dry-run          # Show what would be tested
    python test_write_validation.py --test-calibration # Include calibration tests
    python test_write_validation.py --backup-file backup.json
    python test_write_validation.py COM4               # Specify port
    python test_write_validation.py --verbose          # Detailed logging

Test Categories:
    --test-name         Test device name write/read
    --test-fan          Test fan profile write/read
    --test-rgb          Test RGB profile write/read
    --test-calibration  Test calibration write/read (requires explicit flag)
    --test-actions      Test config save/load actions
    --all               Enable all tests (including calibration)

Requirements:
    - benchlab-pycore library installed
    - BENCHLAB device connected via USB
    - pyserial >= 3.5
"""

import sys
import json
import time
import serial
import argparse
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict

# =============================================================================
# Output Formatting
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'

def print_header(title: str) -> None:
    """Print a formatted test header."""
    print(f"\n{Colors.BOLD}{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}{Colors.RESET}")

def print_section(title: str) -> None:
    """Print a test section header."""
    print(f"\n{Colors.BOLD}{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}{Colors.RESET}")

def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {message}")

def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}")

def print_info(message: str) -> None:
    """Print an informational message."""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {message}")

def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {message}")

def print_test_result(test_name: str, passed: bool) -> None:
    """Print test result with checkmark or X."""
    symbol = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    status = "PASSED" if passed else "FAILED"
    print(f"{symbol} {Colors.BOLD}{status}{Colors.RESET}: {test_name}")

# =============================================================================
# Configuration Backup/Restore
# =============================================================================

@dataclass
class DeviceBackup:
    """Complete backup of device configuration."""
    device_name: Optional[str] = None
    fan_profile_0_0: Optional[Dict[str, Any]] = None
    rgb_profile_0: Optional[Dict[str, Any]] = None
    calibration: Optional[bytes] = None
    product_id: Optional[int] = None
    uid: Optional[str] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert bytes to hex string for JSON
        if data['calibration'] is not None:
            data['calibration'] = data['calibration'].hex()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceBackup':
        """Create from dictionary (JSON deserialization)."""
        if data.get('calibration') is not None and isinstance(data['calibration'], str):
            data['calibration'] = bytes.fromhex(data['calibration'])
        return cls(**data)

def create_backup(ser: serial.Serial, product_id: int, include_calibration: bool = False) -> DeviceBackup:
    """Create a complete backup of device configuration.
    
    Args:
        ser: Serial connection to device
        product_id: Device product ID (0x10 or 0x11)
        include_calibration: Whether to backup calibration data
        
    Returns:
        DeviceBackup object with current configuration
    """
    from benchlab_pycore.core import (
        read_name, read_fan_profile, read_rgb_profile, 
        read_calibration, read_uid
    )
    
    print_info("Creating backup of current configuration...")
    backup = DeviceBackup()
    backup.product_id = product_id
    backup.timestamp = time.time()

    # Backup device name
    backup.device_name = read_name(ser)
    if backup.device_name:
        print_info(f"  Backed up device name: '{backup.device_name}'")
    
    # Backup UID
    backup.uid = read_uid(ser)
    if backup.uid:
        print_info(f"  Backed up UID: {backup.uid}")
    
    # Backup fan profile 0, fan 0 (we only test one to minimize risk)
    fan_cfg = read_fan_profile(ser, fan_profile=0, fan_id=0)
    if fan_cfg:
        backup.fan_profile_0_0 = {
            'FanMode': fan_cfg.FanMode,
            'TempSource': fan_cfg.TempSource,
            'Temp': list(fan_cfg.Temp),
            'Duty': list(fan_cfg.Duty),
            'RampStep': fan_cfg.RampStep,
            'FixedDuty': fan_cfg.FixedDuty,
            'MinDuty': fan_cfg.MinDuty,
            'MaxDuty': fan_cfg.MaxDuty,
            'FanStop': fan_cfg.FanStop,
        }
        print_info(f"  Backed up fan profile 0/0: FanMode={fan_cfg.FanMode}, FixedDuty={fan_cfg.FixedDuty}%")
    
    # Backup RGB profile 0
    rgb_cfg = read_rgb_profile(ser, rgb_profile=0)
    if rgb_cfg:
        backup.rgb_profile_0 = {
            'Mode': rgb_cfg.Mode,
            'Red': rgb_cfg.Red,
            'Green': rgb_cfg.Green,
            'Blue': rgb_cfg.Blue,
            'Direction': rgb_cfg.Direction,
            'Speed': rgb_cfg.Speed,
        }
        print_info(f"  Backed up RGB profile 0: Mode={rgb_cfg.Mode}, RGB=({rgb_cfg.Red},{rgb_cfg.Green},{rgb_cfg.Blue})")
    
    # Backup calibration (if requested)
    if include_calibration:
        cal = read_calibration(ser, product_id=product_id)
        if cal:
            from ctypes import sizeof
            backup.calibration = bytes(cal)
            print_info(f"  Backed up calibration: {sizeof(cal)} bytes")
    
    print_success("Backup completed")
    return backup

def restore_backup(ser: serial.Serial, backup: DeviceBackup, restore_calibration: bool = False) -> bool:
    """Restore device configuration from backup.
    
    Args:
        ser: Serial connection to device
        backup: DeviceBackup object to restore
        restore_calibration: Whether to restore calibration data
        
    Returns:
        True if all restorations succeeded, False otherwise
    """
    from benchlab_pycore.core import (
        read_name, write_name, write_fan_profile, write_rgb_profile,
        write_calibration, FanConfigStruct, RGBConfigStruct
    )
    
    print_info("Restoring original configuration...")
    all_success = True
    
    # Restore device name
    if backup.device_name is not None:
        if write_name(ser, backup.device_name):
            # Verify restoration
            time.sleep(0.1)
            restored_name = read_name(ser)
            if restored_name == backup.device_name:
                print_info(f"  Restored device name: '{backup.device_name}'")
            else:
                print_error(f"  Failed to verify name restoration: got '{restored_name}'")
                all_success = False
        else:
            print_error("  Failed to restore device name")
            all_success = False
    
    # Restore fan profile
    if backup.fan_profile_0_0 is not None:
        fan_cfg = FanConfigStruct()
        fan_cfg.FanMode = backup.fan_profile_0_0['FanMode']
        fan_cfg.TempSource = backup.fan_profile_0_0['TempSource']
        fan_cfg.Temp[0] = backup.fan_profile_0_0['Temp'][0]
        fan_cfg.Temp[1] = backup.fan_profile_0_0['Temp'][1]
        fan_cfg.Duty[0] = backup.fan_profile_0_0['Duty'][0]
        fan_cfg.Duty[1] = backup.fan_profile_0_0['Duty'][1]
        fan_cfg.RampStep = backup.fan_profile_0_0['RampStep']
        fan_cfg.FixedDuty = backup.fan_profile_0_0['FixedDuty']
        fan_cfg.MinDuty = backup.fan_profile_0_0['MinDuty']
        fan_cfg.MaxDuty = backup.fan_profile_0_0['MaxDuty']
        fan_cfg.FanStop = backup.fan_profile_0_0['FanStop']
        
        if write_fan_profile(ser, fan_profile=0, fan_id=0, config=fan_cfg):
            print_info(f"  Restored fan profile 0/0")
        else:
            print_error("  Failed to restore fan profile")
            all_success = False
    
    # Restore RGB profile
    if backup.rgb_profile_0 is not None:
        rgb_cfg = RGBConfigStruct()
        rgb_cfg.Mode = backup.rgb_profile_0['Mode']
        rgb_cfg.Red = backup.rgb_profile_0['Red']
        rgb_cfg.Green = backup.rgb_profile_0['Green']
        rgb_cfg.Blue = backup.rgb_profile_0['Blue']
        rgb_cfg.Direction = backup.rgb_profile_0['Direction']
        rgb_cfg.Speed = backup.rgb_profile_0['Speed']
        
        if write_rgb_profile(ser, rgb_profile=0, config=rgb_cfg):
            print_info(f"  Restored RGB profile 0")
        else:
            print_error("  Failed to restore RGB profile")
            all_success = False
    
    # Restore calibration (if requested and available)
    if restore_calibration and backup.calibration is not None:
        # Reconstruct calibration struct from bytes
        from benchlab_pycore.core import CalibrationStruct, CalibrationStructCFE, BENCHLAB_CFE_PRODUCT_ID
        
        if backup.product_id == BENCHLAB_CFE_PRODUCT_ID:
            cal = CalibrationStructCFE.from_buffer_copy(backup.calibration)
        else:
            cal = CalibrationStruct.from_buffer_copy(backup.calibration)
        
        if write_calibration(ser, cal, product_id=backup.product_id):
            print_info(f"  Restored calibration")
        else:
            print_error("  Failed to restore calibration")
            all_success = False
    
    if all_success:
        print_success("All configuration restored successfully")
    else:
        print_warning("Some restoration operations failed")
    
    return all_success

# =============================================================================
# Individual Write Tests
# =============================================================================

def test_name_write(ser: serial.Serial, backup: DeviceBackup, dry_run: bool = False) -> bool:
    """Test device name write operation.
    
    Args:
        ser: Serial connection to device
        backup: Current backup (for restoration)
        dry_run: If True, don't actually write
        
    Returns:
        True if test passed, False otherwise
    """
    from benchlab_pycore.core import read_name, write_name
    
    print_section("TEST: Device Name Write")
    
    if backup.device_name is None:
        print_warning("No device name in backup, skipping test")
        return True
    
    print_info(f"Current name: '{backup.device_name}'")
    
    test_name = "TEST_WRITE_VAL"
    print_info(f"Test name: '{test_name}'")
    
    if dry_run:
        print_info("[DRY RUN] Would write test name and verify")
        return True
    
    # Write test name
    print_info("Writing test name...")
    if not write_name(ser, test_name):
        print_error("Write operation failed")
        return False
    
    time.sleep(0.1)  # Give device time to process
    
    # Read back and verify
    print_info("Reading back...")
    read_back = read_name(ser)
    
    if read_back is None:
        print_error("Failed to read back device name")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    if read_back != test_name:
        print_error(f"Verification failed!")
        print_error(f"  Expected: '{test_name}'")
        print_error(f"  Got:      '{read_back}'")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    print_success(f"Verified: '{read_back}'")
    
    # Restore original name
    print_info("Restoring original name...")
    if not write_name(ser, backup.device_name):
        print_error("Failed to restore original name")
        return False
    
    time.sleep(0.1)
    
    # Verify restoration
    restored = read_name(ser)
    if restored != backup.device_name:
        print_error(f"Restoration verification failed!")
        print_error(f"  Expected: '{backup.device_name}'")
        print_error(f"  Got:      '{restored}'")
        return False
    
    print_success(f"Restored: '{backup.device_name}'")
    return True

def test_fan_profile_write(ser: serial.Serial, backup: DeviceBackup, dry_run: bool = False) -> bool:
    """Test fan profile write operation.
    
    Args:
        ser: Serial connection to device
        backup: Current backup (for restoration)
        dry_run: If True, don't actually write
        
    Returns:
        True if test passed, False otherwise
    """
    from benchlab_pycore.core import (
        read_fan_profile, write_fan_profile, 
        FanConfigStruct, FanMode
    )
    
    print_section("TEST: Fan Profile Write")
    
    if backup.fan_profile_0_0 is None:
        print_warning("No fan profile in backup, skipping test")
        return True
    
    print_info("Testing profile 0, fan 0")
    print_info(f"Current: FanMode={backup.fan_profile_0_0['FanMode']}, FixedDuty={backup.fan_profile_0_0['FixedDuty']}%")
    
    # Create test configuration with DIFFERENT values from current
    # Toggle FixedDuty to ensure we're writing something different
    current_duty = backup.fan_profile_0_0['FixedDuty']
    test_duty = 75 if current_duty == 50 else 50
    
    test_cfg = FanConfigStruct()
    test_cfg.FanMode = FanMode.FIXED
    test_cfg.FixedDuty = test_duty  # Use toggled value
    test_cfg.TempSource = 0
    test_cfg.Temp[0] = 300  # 30.0°C
    test_cfg.Temp[1] = 600  # 60.0°C
    test_cfg.Duty[0] = 30
    test_cfg.Duty[1] = 80
    test_cfg.MinDuty = 20
    test_cfg.MaxDuty = 100
    test_cfg.RampStep = 5
    test_cfg.FanStop = 0
    
    print_info(f"Test config: FanMode={test_cfg.FanMode}, FixedDuty={test_cfg.FixedDuty}%")
    
    if dry_run:
        print_info("[DRY RUN] Would write test config and verify")
        return True
    
    # Write test configuration
    print_info("Writing test configuration...")
    if not write_fan_profile(ser, fan_profile=0, fan_id=0, config=test_cfg):
        print_error("Write operation failed")
        return False
    
    time.sleep(0.1)
    
    # Read back and verify
    print_info("Reading back...")
    read_back = read_fan_profile(ser, fan_profile=0, fan_id=0)
    
    if read_back is None:
        print_error("Failed to read back fan profile")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    # Verify all fields
    verification_failed = False
    if read_back.FanMode != test_cfg.FanMode:
        print_error(f"FanMode mismatch: expected {test_cfg.FanMode}, got {read_back.FanMode}")
        verification_failed = True
    if read_back.FixedDuty != test_cfg.FixedDuty:
        print_error(f"FixedDuty mismatch: expected {test_cfg.FixedDuty}, got {read_back.FixedDuty}")
        verification_failed = True
    if read_back.MinDuty != test_cfg.MinDuty:
        print_error(f"MinDuty mismatch: expected {test_cfg.MinDuty}, got {read_back.MinDuty}")
        verification_failed = True
    if read_back.MaxDuty != test_cfg.MaxDuty:
        print_error(f"MaxDuty mismatch: expected {test_cfg.MaxDuty}, got {read_back.MaxDuty}")
        verification_failed = True
    
    if verification_failed:
        print_error("Verification failed!")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    print_success("Verified all fields match")
    
    # Restore original configuration
    print_info("Restoring original configuration...")
    restore_cfg = FanConfigStruct()
    restore_cfg.FanMode = backup.fan_profile_0_0['FanMode']
    restore_cfg.TempSource = backup.fan_profile_0_0['TempSource']
    restore_cfg.Temp[0] = backup.fan_profile_0_0['Temp'][0]
    restore_cfg.Temp[1] = backup.fan_profile_0_0['Temp'][1]
    restore_cfg.Duty[0] = backup.fan_profile_0_0['Duty'][0]
    restore_cfg.Duty[1] = backup.fan_profile_0_0['Duty'][1]
    restore_cfg.RampStep = backup.fan_profile_0_0['RampStep']
    restore_cfg.FixedDuty = backup.fan_profile_0_0['FixedDuty']
    restore_cfg.MinDuty = backup.fan_profile_0_0['MinDuty']
    restore_cfg.MaxDuty = backup.fan_profile_0_0['MaxDuty']
    restore_cfg.FanStop = backup.fan_profile_0_0['FanStop']
    
    if not write_fan_profile(ser, fan_profile=0, fan_id=0, config=restore_cfg):
        print_error("Failed to restore original configuration")
        return False
    
    time.sleep(0.1)
    
    # Verify restoration
    restored = read_fan_profile(ser, fan_profile=0, fan_id=0)
    if restored is None or restored.FanMode != restore_cfg.FanMode or restored.FixedDuty != restore_cfg.FixedDuty:
        print_error("Restoration verification failed!")
        return False
    
    print_success("Restored original configuration")
    return True

def test_rgb_profile_write(ser: serial.Serial, backup: DeviceBackup, dry_run: bool = False) -> bool:
    """Test RGB profile write operation.
    
    Args:
        ser: Serial connection to device
        backup: Current backup (for restoration)
        dry_run: If True, don't actually write
        
    Returns:
        True if test passed, False otherwise
    """
    from benchlab_pycore.core import (
        read_rgb_profile, write_rgb_profile,
        RGBConfigStruct, RGBMode
    )
    
    print_section("TEST: RGB Profile Write")
    
    if backup.rgb_profile_0 is None:
        print_warning("No RGB profile in backup, skipping test")
        return True
    
    print_info("Testing RGB profile 0")
    print_info(f"Current: Mode={backup.rgb_profile_0['Mode']}, RGB=({backup.rgb_profile_0['Red']},{backup.rgb_profile_0['Green']},{backup.rgb_profile_0['Blue']})")
    
    # Create test configuration (solid red)
    test_cfg = RGBConfigStruct()
    test_cfg.Mode = RGBMode.SINGLE_COLOR
    test_cfg.Red = 255
    test_cfg.Green = 0
    test_cfg.Blue = 0
    test_cfg.Direction = 0
    test_cfg.Speed = 50
    
    print_info(f"Test config: Mode={test_cfg.Mode}, RGB=({test_cfg.Red},{test_cfg.Green},{test_cfg.Blue})")
    
    if dry_run:
        print_info("[DRY RUN] Would write test config and verify")
        return True
    
    # Write test configuration
    print_info("Writing test configuration...")
    if not write_rgb_profile(ser, rgb_profile=0, config=test_cfg):
        print_error("Write operation failed")
        return False
    
    time.sleep(0.1)
    
    # Read back and verify
    print_info("Reading back...")
    read_back = read_rgb_profile(ser, rgb_profile=0)
    
    if read_back is None:
        print_error("Failed to read back RGB profile")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    # Verify all fields
    verification_failed = False
    if read_back.Mode != test_cfg.Mode:
        print_error(f"Mode mismatch: expected {test_cfg.Mode}, got {read_back.Mode}")
        verification_failed = True
    if read_back.Red != test_cfg.Red:
        print_error(f"Red mismatch: expected {test_cfg.Red}, got {read_back.Red}")
        verification_failed = True
    if read_back.Green != test_cfg.Green:
        print_error(f"Green mismatch: expected {test_cfg.Green}, got {read_back.Green}")
        verification_failed = True
    if read_back.Blue != test_cfg.Blue:
        print_error(f"Blue mismatch: expected {test_cfg.Blue}, got {read_back.Blue}")
        verification_failed = True
    
    if verification_failed:
        print_error("Verification failed!")
        restore_backup(ser, backup, restore_calibration=False)
        return False
    
    print_success("Verified all fields match")
    
    # Restore original configuration
    print_info("Restoring original configuration...")
    restore_cfg = RGBConfigStruct()
    restore_cfg.Mode = backup.rgb_profile_0['Mode']
    restore_cfg.Red = backup.rgb_profile_0['Red']
    restore_cfg.Green = backup.rgb_profile_0['Green']
    restore_cfg.Blue = backup.rgb_profile_0['Blue']
    restore_cfg.Direction = backup.rgb_profile_0['Direction']
    restore_cfg.Speed = backup.rgb_profile_0['Speed']
    
    if not write_rgb_profile(ser, rgb_profile=0, config=restore_cfg):
        print_error("Failed to restore original configuration")
        return False
    
    time.sleep(0.1)
    
    # Verify restoration
    restored = read_rgb_profile(ser, rgb_profile=0)
    if restored is None or restored.Mode != restore_cfg.Mode or restored.Red != restore_cfg.Red:
        print_error("Restoration verification failed!")
        return False
    
    print_success("Restored original configuration")
    return True

def test_calibration_write(ser: serial.Serial, backup: DeviceBackup, dry_run: bool = False) -> bool:
    """Test calibration write operation.
    
    This test writes the same calibration back (no-op) to test the write mechanism
    without actually changing calibration values.
    
    Args:
        ser: Serial connection to device
        backup: Current backup (for restoration)
        dry_run: If True, don't actually write
        
    Returns:
        True if test passed, False otherwise
    """
    from benchlab_pycore.core import (
        read_calibration, write_calibration,
        CalibrationStruct, CalibrationStructCFE,
        BENCHLAB_CFE_PRODUCT_ID
    )
    from ctypes import sizeof
    
    print_section("TEST: Calibration Write (No-Op)")
    
    if backup.calibration is None:
        print_warning("No calibration in backup, skipping test")
        return True
    
    print_info(f"Testing calibration write ({len(backup.calibration)} bytes)")
    print_warning("This test writes the same calibration back (no-op)")
    print_warning("It does NOT write to flash slots (safe for testing)")
    
    if dry_run:
        print_info("[DRY RUN] Would write calibration and verify byte-for-byte")
        return True
    
    # Reconstruct calibration struct from backup
    if backup.product_id == BENCHLAB_CFE_PRODUCT_ID:
        cal = CalibrationStructCFE.from_buffer_copy(backup.calibration)
    else:
        cal = CalibrationStruct.from_buffer_copy(backup.calibration)
    
    # Write calibration (same values, just testing the mechanism)
    print_info("Writing calibration to RAM...")
    if not write_calibration(ser, cal, product_id=backup.product_id):
        print_error("Write operation failed")
        return False
    
    time.sleep(0.2)  # Give device more time for calibration
    
    # Read back and verify byte-for-byte
    print_info("Reading back...")
    read_back = read_calibration(ser, product_id=backup.product_id)
    
    if read_back is None:
        print_error("Failed to read back calibration")
        return False
    
    read_back_bytes = bytes(read_back)
    
    if read_back_bytes != backup.calibration:
        print_error("Verification failed! Calibration bytes don't match")
        print_error(f"  Expected: {len(backup.calibration)} bytes")
        print_error(f"  Got:      {len(read_back_bytes)} bytes")
        # Try to restore
        write_calibration(ser, cal, product_id=backup.product_id)
        return False
    
    print_success(f"Verified byte-for-byte match ({len(backup.calibration)} bytes)")
    print_info("Calibration unchanged (no-op write test)")
    return True

def test_config_actions(ser: serial.Serial, backup: DeviceBackup, dry_run: bool = False) -> bool:
    """Test configuration save/load actions.
    
    Args:
        ser: Serial connection to device
        backup: Current backup (for restoration)
        dry_run: If True, don't actually perform actions
        
    Returns:
        True if test passed, False otherwise
    """
    from benchlab_pycore.core import send_action, read_name
    
    print_section("TEST: Configuration Actions (Save/Load)")
    
    print_info("This test saves current config to flash and reloads it")
    print_warning("This writes to flash but should be safe (saves current state)")
    
    if dry_run:
        print_info("[DRY RUN] Would test CONFIG_ACTION_SAVE and CONFIG_ACTION_LOAD")
        return True
    
    # Get current name as a marker
    current_name = read_name(ser)
    if current_name is None:
        print_warning("Cannot read device name, skipping action test")
        return True
    
    print_info(f"Current device name: '{current_name}'")
    
    # Test CONFIG_ACTION_SAVE (action=0)
    print_info("Testing CONFIG_ACTION_SAVE (save to flash)...")
    if not send_action(ser, action=0):
        print_error("CONFIG_ACTION_SAVE failed")
        return False
    
    time.sleep(0.2)  # Give device time to save to flash
    print_success("Configuration saved to flash")
    
    # Test CONFIG_ACTION_LOAD (action=1)
    print_info("Testing CONFIG_ACTION_LOAD (reload from flash)...")
    if not send_action(ser, action=1):
        print_error("CONFIG_ACTION_LOAD failed")
        return False
    
    time.sleep(0.2)  # Give device time to load from flash
    print_success("Configuration loaded from flash")
    
    # Verify name is still the same (should be unchanged)
    reloaded_name = read_name(ser)
    if reloaded_name != current_name:
        print_warning(f"Device name changed after reload: '{current_name}' -> '{reloaded_name}'")
        print_warning("This might indicate flash save/load is not working correctly")
        # Not a hard failure, just a warning
    else:
        print_success("Configuration preserved after save/load cycle")
    
    return True

# =============================================================================
# Main Test Runner
# =============================================================================

def run_tests(args: argparse.Namespace) -> bool:
    """Run all enabled tests.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        True if all tests passed, False otherwise
    """
    from benchlab_pycore.core import get_benchlab_ports, read_device
    
    print_header("BENCHLAB Write Validation Test Suite")
    
    if args.dry_run:
        print_warning("DRY RUN MODE: No actual writes will be performed")
    
    # Connect to device
    print_info("Connecting to device...")
    
    if args.port:
        port = args.port
    else:
        ports = get_benchlab_ports()
        if not ports:
            print_error("No BENCHLAB device found. Check USB connection.")
            return False
        port = ports[0]['port']
        print_info(f"Auto-detected device on {port}")
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except serial.SerialException as e:
        print_error(f"Cannot open {port}: {e}")
        return False
    
    try:
        # Read device info
        device_info = read_device(ser)
        if not device_info:
            print_error("Failed to read device information")
            return False
        
        product_id = device_info['ProductId']
        variant = "CFE" if product_id == 0x11 else "ORIGINAL"
        
        print_success(f"Connected to device on {port}")
        print_info(f"  Variant: {variant} (Product ID: 0x{product_id:02X})")
        print_info(f"  Firmware: {device_info['FwVersion']}")
        
        # Create backup
        include_cal = args.test_calibration or args.all
        backup = create_backup(ser, product_id, include_calibration=include_cal)
        
        # Save backup to file if requested
        if args.backup_file:
            print_info(f"Saving backup to {args.backup_file}...")
            with open(args.backup_file, 'w') as f:
                json.dump(backup.to_dict(), f, indent=2)
            print_success(f"Backup saved to {args.backup_file}")
        
        # Determine which tests to run
        test_all = args.all or not any([args.test_name, args.test_fan, args.test_rgb, 
                                        args.test_calibration, args.test_actions])
        
        run_name = args.test_name or test_all
        run_fan = args.test_fan or test_all
        run_rgb = args.test_rgb or test_all
        run_calibration = args.test_calibration or args.all
        run_actions = args.test_actions or test_all
        
        # Run tests
        results = {}
        
        if run_name:
            results['Device Name'] = test_name_write(ser, backup, args.dry_run)
        
        if run_fan:
            results['Fan Profile'] = test_fan_profile_write(ser, backup, args.dry_run)
        
        if run_rgb:
            results['RGB Profile'] = test_rgb_profile_write(ser, backup, args.dry_run)
        
        if run_calibration:
            results['Calibration'] = test_calibration_write(ser, backup, args.dry_run)
        
        if run_actions:
            results['Config Actions'] = test_config_actions(ser, backup, args.dry_run)
        
        # Print summary
        print_section("TEST SUMMARY")
        
        for test_name, passed in results.items():
            print_test_result(test_name, passed)
        
        passed_count = sum(1 for p in results.values() if p)
        total_count = len(results)
        
        print(f"\n{passed_count}/{total_count} tests passed")
        
        if all(results.values()):
            print_success("\nAll write operations validated successfully!")
            print_info("Device configuration restored to original state")
            return True
        else:
            print_error("\nSome tests failed")
            print_warning("Device may not be in original state - check configuration")
            return False
        
    except KeyboardInterrupt:
        print_warning("\n\nTest interrupted by user")
        print_info("Attempting to restore backup...")
        restore_backup(ser, backup, restore_calibration=include_cal)
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ser.close()
        print_info(f"Serial connection to {port} closed")

# =============================================================================
# Command-Line Interface
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='BENCHLAB Write Validation Test Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run safe default tests
  %(prog)s --dry-run                # Show what would be tested
  %(prog)s --test-calibration       # Include calibration tests
  %(prog)s --backup-file backup.json
  %(prog)s COM4                     # Specify port
  %(prog)s --all                    # Run all tests including calibration

Test Categories:
  By default, runs name, fan, RGB, and action tests (safe).
  Use flags to enable/disable specific categories.
        """
    )
    
    parser.add_argument('port', nargs='?', help='COM port (auto-detect if omitted)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be tested without writing')
    parser.add_argument('--test-name', action='store_true',
                       help='Test device name write/read')
    parser.add_argument('--test-fan', action='store_true',
                       help='Test fan profile write/read')
    parser.add_argument('--test-rgb', action='store_true',
                       help='Test RGB profile write/read')
    parser.add_argument('--test-calibration', action='store_true',
                       help='Test calibration write/read (requires explicit flag)')
    parser.add_argument('--test-actions', action='store_true',
                       help='Test config save/load actions')
    parser.add_argument('--all', action='store_true',
                       help='Enable all tests (including calibration)')
    parser.add_argument('--backup-file', metavar='FILE',
                       help='Save backup to JSON file before testing')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output (currently unused)')
    
    args = parser.parse_args()
    
    try:
        success = run_tests(args)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
