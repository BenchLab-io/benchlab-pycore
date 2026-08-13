# Write Validation Testing Guide

This guide explains how to safely test the device configuration write operations added in v0.4.0.

## Overview

The `test_write_validation.py` script provides automated testing for all write operations in benchlab-pycore v0.4.0:

- **Device name** write/read
- **Fan profile** write/read
- **RGB profile** write/read
- **Calibration** write/read
- **Configuration actions** (save/load to flash)

## Safety Features

The script is designed with safety as the top priority:

1. **Always backs up** configuration before any write operation
2. **Verifies every write** by reading back and comparing values
3. **Automatically restores** original configuration after each test
4. **Fails fast** and attempts restoration if any verification fails
5. **Dangerous operations** (calibration) require explicit `--test-calibration` flag
6. **Dry-run mode** available to preview tests without writing
7. **Keyboard interrupt handling** - Ctrl+C will attempt to restore backup

## Prerequisites

Before running the write validation tests, ensure you have the latest version of benchlab-pycore installed:

```bash
# Install in development mode (from the project root)
pip install -e .
```

This ensures you're using the current codebase with all v0.4.0 features.

## Quick Start

### Basic Usage (Safe Default Tests)

```bash
# Run safe default tests (name, fan, RGB, actions)
python tests/test_write_validation.py

# Auto-detects device, or specify port:
python tests/test_write_validation.py COM4
```

### Dry-Run Mode

Preview what would be tested without actually writing:

```bash
python tests/test_write_validation.py --dry-run
```

### Include Calibration Tests

Calibration tests require an explicit flag for safety:

```bash
python tests/test_write_validation.py --test-calibration
```

### Save Backup Before Testing

Save a JSON backup of your device configuration:

```bash
python tests/test_write_validation.py --backup-file my_backup.json
```

## Command-Line Options

### Test Selection

By default, the script runs **safe tests** (name, fan, RGB, actions). Use these flags to customize:

- `--test-name` - Test device name write/read only
- `--test-fan` - Test fan profile write/read only
- `--test-rgb` - Test RGB profile write/read only
- `--test-calibration` - Test calibration write/read (requires explicit flag)
- `--test-actions` - Test config save/load actions only
- `--all` - Enable all tests including calibration

### Other Options

- `--dry-run` - Show what would be tested without writing
- `--backup-file FILE` - Save backup to JSON file before testing
- `--verbose` - Verbose output (currently unused, reserved for future)
- `port` - Specify COM port (optional, auto-detects if omitted)

## Examples

### Test Only Device Name

```bash
python tests/test_write_validation.py --test-name
```

### Test Fan and RGB Profiles

```bash
python tests/test_write_validation.py --test-fan --test-rgb
```

### Run All Tests Including Calibration

```bash
python tests/test_write_validation.py --all
```

### Dry-Run with Backup File

```bash
python tests/test_write_validation.py --dry-run --backup-file backup.json
```

### Specify Device Port

```bash
python tests/test_write_validation.py COM4 --test-fan
```

## What Each Test Does

### Device Name Test

1. Backs up current device name
2. Writes test name: `"TEST_WRITE_VAL"`
3. Reads back and verifies it matches
4. Restores original name
5. Verifies restoration succeeded

**Risk Level:** Low - only affects device name

### Fan Profile Test

1. Backs up fan profile 0, fan channel 0
2. Writes test configuration (FIXED mode, 50% duty)
3. Reads back and verifies all fields match
4. Restores original configuration
5. Verifies restoration succeeded

**Risk Level:** Low - only tests one fan channel, immediately restored

**Note:** The fan will briefly change to 50% fixed duty during the test (< 1 second)

### RGB Profile Test

1. Backs up RGB profile 0
2. Writes test configuration (solid red: RGB=255,0,0)
3. Reads back and verifies all fields match
4. Restores original configuration
5. Verifies restoration succeeded

**Risk Level:** Low - only affects RGB lighting, immediately restored

**Note:** RGB will briefly turn solid red during the test (< 1 second)

### Calibration Test

1. Backs up current calibration from RAM
2. Writes the **same calibration back** (no-op write)
3. Reads back and verifies byte-for-byte match
4. No restoration needed (values unchanged)

**Risk Level:** Very Low - writes same values back, does NOT write to flash

**Important:** This test does NOT modify calibration values or write to flash slots. It only tests the write mechanism by writing the same data back to RAM.

### Configuration Actions Test

1. Gets current device name as a marker
2. Sends `CONFIG_ACTION_SAVE` (saves current config to flash)
3. Sends `CONFIG_ACTION_LOAD` (reloads config from flash)
4. Verifies device name is unchanged after save/load cycle

**Risk Level:** Low - saves current state to flash, then reloads it

**Note:** This writes to flash but saves the current configuration, so it should be safe.

## Expected Output

### Successful Test Run

```
═══════════════════════════════════════════════════════════
  BENCHLAB Write Validation Test Suite
═══════════════════════════════════════════════════════════

[INFO] Connecting to device...
[INFO] Auto-detected device on COM4
[SUCCESS] Connected to device on COM4
[INFO]   Variant: BL2 (Product ID: 0x11)
[INFO]   Firmware: 2
[INFO] Creating backup of current configuration...
[INFO]   Backed up device name: 'My BENCHLAB'
[INFO]   Backed up UID: 123456789ABC
[INFO]   Backed up fan profile 0/0: FanMode=0, FixedDuty=0%
[INFO]   Backed up RGB profile 0: Mode=9, RGB=(255,255,255)
[SUCCESS] Backup completed

────────────────────────────────────────────────────────────
  TEST: Device Name Write
────────────────────────────────────────────────────────────
[INFO] Current name: 'My BENCHLAB'
[INFO] Test name: 'TEST_WRITE_VAL'
[INFO] Writing test name...
[INFO] Reading back...
[SUCCESS] Verified: 'TEST_WRITE_VAL'
[INFO] Restoring original name...
[SUCCESS] Restored: 'My BENCHLAB'

────────────────────────────────────────────────────────────
  TEST: Fan Profile Write
────────────────────────────────────────────────────────────
[INFO] Testing profile 0, fan 0
[INFO] Current: FanMode=0, FixedDuty=0%
[INFO] Test config: FanMode=1, FixedDuty=50%
[INFO] Writing test configuration...
[INFO] Reading back...
[SUCCESS] Verified all fields match
[INFO] Restoring original configuration...
[SUCCESS] Restored original configuration

────────────────────────────────────────────────────────────
  TEST: RGB Profile Write
────────────────────────────────────────────────────────────
[INFO] Testing RGB profile 0
[INFO] Current: Mode=9, RGB=(255,255,255)
[INFO] Test config: Mode=9, RGB=(255,0,0)
[INFO] Writing test configuration...
[INFO] Reading back...
[SUCCESS] Verified all fields match
[INFO] Restoring original configuration...
[SUCCESS] Restored original configuration

────────────────────────────────────────────────────────────
  TEST: Configuration Actions (Save/Load)
────────────────────────────────────────────────────────────
[INFO] This test saves current config to flash and reloads it
[WARNING] This writes to flash but should be safe (saves current state)
[INFO] Current device name: 'My BENCHLAB'
[INFO] Testing CONFIG_ACTION_SAVE (save to flash)...
[SUCCESS] Configuration saved to flash
[INFO] Testing CONFIG_ACTION_LOAD (reload from flash)...
[SUCCESS] Configuration loaded from flash
[SUCCESS] Configuration preserved after save/load cycle

────────────────────────────────────────────────────────────
  TEST SUMMARY
────────────────────────────────────────────────────────────
✓ PASSED: Device Name
✓ PASSED: Fan Profile
✓ PASSED: RGB Profile
✓ PASSED: Config Actions

4/4 tests passed

[SUCCESS] All write operations validated successfully!
[INFO] Device configuration restored to original state
[INFO] Serial connection to COM4 closed
```

### Failed Test Example

```
────────────────────────────────────────────────────────────
  TEST: Device Name Write
────────────────────────────────────────────────────────────
[INFO] Current name: 'My BENCHLAB'
[INFO] Test name: 'TEST_WRITE_VAL'
[INFO] Writing test name...
[INFO] Reading back...
[ERROR] Verification failed!
[ERROR]   Expected: 'TEST_WRITE_VAL'
[ERROR]   Got:      'My BENCHLAB'
[INFO] Restoring original configuration...
[SUCCESS] All configuration restored successfully

────────────────────────────────────────────────────────────
  TEST SUMMARY
────────────────────────────────────────────────────────────
✗ FAILED: Device Name

0/1 tests passed

[ERROR] Some tests failed
[WARNING] Device may not be in original state - check configuration
```

## Troubleshooting

### No Device Found

```
[ERROR] No BENCHLAB device found. Check USB connection.
```

**Solution:** Ensure your BENCHLAB device is connected via USB and drivers are installed.

### Cannot Open Port

```
[ERROR] Cannot open COM4: [Errno 16] could not open port 'COM4': PermissionError
```

**Solution:** Close any other applications using the device (e.g., monitoring software, other test scripts).

### Write Verification Failed

If a write verification fails, the script will:
1. Report the mismatch
2. Attempt to restore the original configuration
3. Verify the restoration succeeded
4. Exit with error status

**Solution:** This indicates a potential firmware issue. Check:
- Firmware version is compatible
- Device is not in a special mode
- USB connection is stable

### Test Interrupted (Ctrl+C)

```
[WARNING] Test interrupted by user
[INFO] Attempting to restore backup...
```

The script will attempt to restore your original configuration. If restoration fails, you can:
1. Manually restore using the interactive tool: `python tests/test_deviceConfig.py`
2. Use a saved backup file if you used `--backup-file`

## Integration with CI/CD

The script returns appropriate exit codes:
- `0` - All tests passed
- `1` - One or more tests failed or error occurred

Example GitHub Actions workflow:

```yaml
- name: Run write validation tests
  run: |
    python tests/test_write_validation.py --dry-run
    # Only run actual tests if device is available
    if [ -n "$DEVICE_PORT" ]; then
      python tests/test_write_validation.py $DEVICE_PORT
    fi
```

## Backup File Format

When using `--backup-file`, the script saves a JSON file with this structure:

```json
{
  "device_name": "My BENCHLAB",
  "fan_profile_0_0": {
    "FanMode": 0,
    "TempSource": 0,
    "Temp": [300, 600],
    "Duty": [30, 80],
    "RampStep": 5,
    "FixedDuty": 0,
    "MinDuty": 20,
    "MaxDuty": 100,
    "FanStop": 0
  },
  "rgb_profile_0": {
    "Mode": 9,
    "Red": 255,
    "Green": 255,
    "Blue": 255,
    "Direction": 0,
    "Speed": 50
  },
  "calibration": "0100020003000400...",
  "product_id": 17,
  "uid": "123456789ABC",
  "timestamp": 1779960873.123
}
```

## Comparison with Other Test Scripts

### vs. `test_device.py`

- `test_device.py` - Read-only tests (device discovery, sensor reading)
- `test_write_validation.py` - Write operation tests with backup/restore

### vs. `test_deviceConfig.py`

- `test_deviceConfig.py` - Interactive manual configuration tool
- `test_write_validation.py` - Automated validation with verification

### vs. `test_config.py`

- `test_config.py` - Unit tests with mocked serial (no hardware)
- `test_write_validation.py` - Integration tests with real hardware

## Best Practices

1. **Always run dry-run first** on a new device to see what will be tested
2. **Save a backup** before running tests: `--backup-file backup.json`
3. **Start with safe tests** before enabling calibration tests
4. **Run tests one at a time** initially: `--test-name`, `--test-fan`, etc.
5. **Monitor the device** during tests to observe behavior
6. **Keep firmware updated** to ensure compatibility

## Safety Checklist

Before running write tests:

- [ ] Device is not performing critical operations
- [ ] You have a backup of important configurations (optional but recommended)
- [ ] You understand what each test does (see "What Each Test Does" section)
- [ ] You've run `--dry-run` to preview the tests
- [ ] No other applications are using the device
- [ ] Device firmware is compatible with benchlab-pycore v0.4.0+

## Support

If you encounter issues:

1. Check this documentation
2. Run with `--dry-run` to diagnose
3. Try individual tests: `--test-name`, `--test-fan`, etc.
4. Check device firmware version
5. Review the [main README](../README.md) for device compatibility
6. Report issues on GitHub with test output

## Technical Details

### Test Timing

- Each write operation waits 100ms before reading back
- Calibration writes wait 200ms (larger data transfer)
- Configuration actions wait 200ms (flash operations)

### What Gets Tested

- **Device Name:** Only the friendly name (31 chars max)
- **Fan Profile:** Only profile 0, fan channel 0 (out of 3 profiles × 9 channels)
- **RGB Profile:** Only profile 0 (out of 2 profiles)
- **Calibration:** Full calibration struct (178 bytes ORIGINAL, 294 bytes BL2)
- **Actions:** Save and load operations (not reset)

### What Does NOT Get Tested

- **Firmware flashing** - This library does not support firmware updates
- **Factory calibration slot** - Only RAM calibration is tested
- **All fan channels** - Only one channel to minimize risk
- **CONFIG_ACTION_RESET** - Too destructive for automated tests

## Conclusion

The write validation script provides a safe, automated way to verify that all write operations in benchlab-pycore v0.4.0 work correctly with your devices. By following the safety features and best practices, you can confidently test write functionality without risk to your device configuration.
