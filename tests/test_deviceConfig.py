#!/usr/bin/env python3
"""
BENCHLAB Device Configuration Tool

Interactive numbered-menu tool for reading and writing device configuration.
All write operations require explicit confirmation before sending.

Usage:
    python test_deviceConfig.py [COM_PORT]

    COM_PORT is optional. If omitted, the tool will auto-detect the first
    connected BENCHLAB device.

Example:
    python test_deviceConfig.py
    python test_deviceConfig.py COM4
"""

import sys
import time
import serial

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "─", width: int = 58) -> str:
    return char * width

def _header(title: str) -> None:
    print(f"\n{_hr('═')}")
    print(f"  {title}")
    print(_hr("═"))

def _section(title: str) -> None:
    print(f"\n{_hr()}")
    print(f"  {title}")
    print(_hr())

def _confirm(prompt: str) -> bool:
    """Require the user to type 'yes' to proceed."""
    ans = input(f"\n  ⚠  {prompt}\n  Type 'yes' to confirm: ").strip().lower()
    return ans == "yes"

def _input(prompt: str, default: str = "") -> str:
    val = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return val if val else default

def _input_int(prompt: str, lo: int, hi: int, default: int = None) -> int:
    while True:
        raw = _input(prompt, str(default) if default is not None else "")
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
            print(f"  Enter a value between {lo} and {hi}.")
        except ValueError:
            print("  Enter a valid integer.")

def _menu(title: str, options: list) -> int:
    """Display a numbered menu and return the chosen index (0-based)."""
    _section(title)
    for i, opt in enumerate(options, 1):
        print(f"  {i:2d}.  {opt}")
    print(f"   0.  Back / Cancel")
    while True:
        raw = input("\n  Choice: ").strip()
        try:
            v = int(raw)
            if 0 <= v <= len(options):
                return v - 1   # -1 means "back/cancel"
        except ValueError:
            pass
        print(f"  Enter 0–{len(options)}.")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def connect(port: str = None) -> tuple:
    """Open a serial connection and return (ser, product_id).
    Auto-detects port if not given."""
    from benchlab_pycore.core import get_benchlab_ports, read_device

    if port is None:
        ports = get_benchlab_ports()
        if not ports:
            print("ERROR: No BENCHLAB device found. Check USB connection.")
            sys.exit(1)
        port = ports[0]["port"]
        print(f"  Auto-detected device on {port}")
    else:
        print(f"  Connecting to {port}")

    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {port}: {e}")
        sys.exit(1)

    info = read_device(ser)
    if info is None:
        print("ERROR: Device did not respond to vendor info request.")
        ser.close()
        sys.exit(1)

    from benchlab_pycore.core import BENCHLAB_CFE_PRODUCT_ID, BENCHLAB_ORIGINAL_PRODUCT_ID
    pid = info["ProductId"]
    variant = (
        "BENCHLAB-CFE"      if pid == BENCHLAB_CFE_PRODUCT_ID else
        "BENCHLAB ORIGINAL" if pid == BENCHLAB_ORIGINAL_PRODUCT_ID else
        f"Unknown (0x{pid:02X})"
    )
    print(f"  Connected  │  {variant}  │  FW v{info['FwVersion']}  │  {port}")
    return ser, pid


# ---------------------------------------------------------------------------
# Device info
# ---------------------------------------------------------------------------

def cmd_device_info(ser, product_id) -> None:
    _header("DEVICE INFO")
    from benchlab_pycore.core import read_device, read_uid, ping, read_name
    from benchlab_pycore.core import BENCHLAB_CFE_PRODUCT_ID, BENCHLAB_ORIGINAL_PRODUCT_ID

    ok = ping(ser)
    print(f"  Ping          : {'OK' if ok else 'FAILED'}")

    info = read_device(ser)
    if info:
        variant = (
            "BENCHLAB-CFE"      if info['ProductId'] == BENCHLAB_CFE_PRODUCT_ID else
            "BENCHLAB ORIGINAL" if info['ProductId'] == BENCHLAB_ORIGINAL_PRODUCT_ID else
            f"Unknown (0x{info['ProductId']:02X})"
        )
        print(f"  Variant       : {variant}")
        print(f"  Vendor ID     : 0x{info['VendorId']:02X}")
        print(f"  Product ID    : 0x{info['ProductId']:02X}")
        print(f"  FW Version    : {info['FwVersion']}")

    uid = read_uid(ser)
    print(f"  UID           : {uid or 'N/A'}")

    name = read_name(ser)
    print(f"  Friendly Name : {name!r}")


# ---------------------------------------------------------------------------
# Friendly name
# ---------------------------------------------------------------------------

def cmd_read_name(ser, product_id) -> None:
    _header("FRIENDLY NAME — READ")
    from benchlab_pycore.core import read_name
    name = read_name(ser)
    print(f"  Current name: {name!r}")


def cmd_write_name(ser, product_id) -> None:
    _header("FRIENDLY NAME — WRITE")
    from benchlab_pycore.core import read_name, write_name, FRIENDLY_NAME_LEN
    current = read_name(ser)
    print(f"  Current name : {current!r}")
    new_name = _input("New name (max 31 chars)")
    if not new_name:
        print("  Cancelled — empty input.")
        return
    if len(new_name.encode()) > 31:
        print(f"  WARNING: name will be truncated to 31 bytes.")
    if not _confirm(f"Write name {new_name!r} to device?"):
        print("  Cancelled.")
        return
    if write_name(ser, new_name):
        print(f"  Written: {new_name!r}")
    else:
        print("  ERROR: Write failed.")


# ---------------------------------------------------------------------------
# Fan profiles
# ---------------------------------------------------------------------------

def _print_fan_config(cfg, profile: int, fan_id: int) -> None:
    from benchlab_pycore.core import FanMode, TempSrc, FanStop
    try:
        mode_name = FanMode(cfg.FanMode).name
    except ValueError:
        mode_name = str(cfg.FanMode)
    try:
        src_name = TempSrc(cfg.TempSource).name
    except ValueError:
        src_name = str(cfg.TempSource)
    try:
        stop_name = FanStop(cfg.FanStop).name
    except ValueError:
        stop_name = str(cfg.FanStop)

    print(f"  Profile {profile}, Fan {fan_id}:")
    print(f"    FanMode    : {cfg.FanMode} ({mode_name})")
    print(f"    TempSource : {cfg.TempSource} ({src_name})")
    print(f"    Temp[0]    : {cfg.Temp[0] / 10:.1f} °C  →  Duty[0]: {cfg.Duty[0]}%")
    print(f"    Temp[1]    : {cfg.Temp[1] / 10:.1f} °C  →  Duty[1]: {cfg.Duty[1]}%")
    print(f"    RampStep   : {cfg.RampStep}")
    print(f"    FixedDuty  : {cfg.FixedDuty}%")
    print(f"    MinDuty    : {cfg.MinDuty}%")
    print(f"    MaxDuty    : {cfg.MaxDuty}%")
    print(f"    FanStop    : {cfg.FanStop} ({stop_name})")


def cmd_read_fan_profile(ser, product_id) -> None:
    _header("FAN PROFILE — READ")
    from benchlab_pycore.core import read_fan_profile, FAN_PROFILE_NUM, FAN_NUM

    choice = _menu("Select scope", [
        "Read all profiles (all fans)",
        "Read one profile (all fans)",
        "Read single fan",
    ])
    if choice < 0:
        return

    entries = []
    if choice == 0:
        entries = [(p, f) for p in range(FAN_PROFILE_NUM) for f in range(FAN_NUM)]
    elif choice == 1:
        p = _input_int("Profile (0–2)", 0, FAN_PROFILE_NUM - 1, 0)
        entries = [(p, f) for f in range(FAN_NUM)]
    else:
        p = _input_int("Profile (0–2)", 0, FAN_PROFILE_NUM - 1, 0)
        f = _input_int(f"Fan ID (0–{FAN_NUM - 1})", 0, FAN_NUM - 1, 0)
        entries = [(p, f)]

    for profile, fan_id in entries:
        cfg = read_fan_profile(ser, fan_profile=profile, fan_id=fan_id)
        if cfg is None:
            print(f"  ERROR: Failed to read profile {profile}, fan {fan_id}")
        else:
            _print_fan_config(cfg, profile, fan_id)
            print()


def cmd_write_fan_profile(ser, product_id) -> None:
    _header("FAN PROFILE — WRITE")
    from benchlab_pycore.core import (
        read_fan_profile, write_fan_profile,
        FanConfigStruct, FanMode, TempSrc, FanStop,
        FAN_PROFILE_NUM, FAN_NUM, FAN_CURVE_POINTS,
    )

    profile = _input_int("Profile (0–2)", 0, FAN_PROFILE_NUM - 1, 0)
    fan_id  = _input_int(f"Fan ID (0–{FAN_NUM - 1})", 0, FAN_NUM - 1, 0)

    # Read current and display
    current = read_fan_profile(ser, fan_profile=profile, fan_id=fan_id)
    if current is None:
        print("  ERROR: Could not read current profile.")
        return
    print("\n  Current configuration:")
    _print_fan_config(current, profile, fan_id)

    # Build new config field by field, defaulting to current values
    print("\n  Enter new values (press Enter to keep current):")
    cfg = FanConfigStruct()

    print(f"\n  FanMode: 0=TEMP_CONTROL  1=FIXED  2=EXT")
    cfg.FanMode    = _input_int("  FanMode", 0, 2, current.FanMode)

    print(f"\n  TempSource: 0=AUTO  1=TS1  2=TS2  3=TS3  4=TS4  5=TAMB")
    cfg.TempSource = _input_int("  TempSource", 0, 5, current.TempSource)

    for i in range(FAN_CURVE_POINTS):
        t = _input_int(
            f"  Temp[{i}] in tenths of °C (e.g. 300 = 30.0°C)",
            -1000, 1500, current.Temp[i]
        )
        cfg.Temp[i] = t
        cfg.Duty[i] = _input_int(f"  Duty[{i}] % (0–100)", 0, 100, current.Duty[i])

    cfg.RampStep  = _input_int("  RampStep  (0–255)", 0, 255, current.RampStep)
    cfg.FixedDuty = _input_int("  FixedDuty % (0–100)", 0, 100, current.FixedDuty)
    cfg.MinDuty   = _input_int("  MinDuty   % (0–100)", 0, 100, current.MinDuty)
    cfg.MaxDuty   = _input_int("  MaxDuty   % (0–100)", 0, 100, current.MaxDuty)

    print(f"\n  FanStop: 0=OFF  1=ON")
    cfg.FanStop   = _input_int("  FanStop", 0, 1, current.FanStop)

    print("\n  New configuration to write:")
    _print_fan_config(cfg, profile, fan_id)

    if not _confirm(f"Write fan profile {profile}, fan {fan_id} to device?"):
        print("  Cancelled.")
        return

    if write_fan_profile(ser, fan_profile=profile, fan_id=fan_id, config=cfg):
        print("  Written successfully.")
    else:
        print("  ERROR: Write failed.")



def cmd_write_fan_profile_all(ser, product_id) -> None:
    _header("FAN PROFILE — WRITE ALL FANS IN PROFILE")
    from benchlab_pycore.core import (
        read_fan_profile, write_fan_profile,
        FanConfigStruct, FanMode, TempSrc, FanStop,
        FAN_PROFILE_NUM, FAN_NUM, FAN_CURVE_POINTS,
    )

    profile = _input_int("Profile (0–2)", 0, FAN_PROFILE_NUM - 1, 0)

    # Use fan 0 as the reference for current values
    reference = read_fan_profile(ser, fan_profile=profile, fan_id=0)
    if reference is None:
        print("  ERROR: Could not read current profile for fan 0.")
        return
    print(f"\n  Current configuration (fan 0 shown as reference):")
    _print_fan_config(reference, profile, 0)

    # Build new config field by field, defaulting to fan 0's current values
    print("\n  Enter new values (press Enter to keep current):")
    print("  This configuration will be written to ALL fans in this profile.\n")
    cfg = FanConfigStruct()

    print(f"  FanMode: 0=TEMP_CONTROL  1=FIXED  2=EXT")
    cfg.FanMode    = _input_int("  FanMode", 0, 2, reference.FanMode)

    print(f"\n  TempSource: 0=AUTO  1=TS1  2=TS2  3=TS3  4=TS4  5=TAMB")
    cfg.TempSource = _input_int("  TempSource", 0, 5, reference.TempSource)

    for i in range(FAN_CURVE_POINTS):
        t = _input_int(
            f"  Temp[{i}] in tenths of °C (e.g. 300 = 30.0°C)",
            -1000, 1500, reference.Temp[i]
        )
        cfg.Temp[i] = t
        cfg.Duty[i] = _input_int(f"  Duty[{i}] % (0–100)", 0, 100, reference.Duty[i])

    cfg.RampStep  = _input_int("  RampStep  (0–255)", 0, 255, reference.RampStep)
    cfg.FixedDuty = _input_int("  FixedDuty % (0–100)", 0, 100, reference.FixedDuty)
    cfg.MinDuty   = _input_int("  MinDuty   % (0–100)", 0, 100, reference.MinDuty)
    cfg.MaxDuty   = _input_int("  MaxDuty   % (0–100)", 0, 100, reference.MaxDuty)

    print(f"\n  FanStop: 0=OFF  1=ON")
    cfg.FanStop   = _input_int("  FanStop", 0, 1, reference.FanStop)

    print(f"\n  Configuration to write to all {FAN_NUM} fans in profile {profile}:")
    _print_fan_config(cfg, profile, 0)
    print(f"  (fan ID shown as 0; same config will be applied to fans 0–{FAN_NUM - 1})")

    if not _confirm(f"Write this config to ALL {FAN_NUM} fans in profile {profile}?"):
        print("  Cancelled.")
        return

    failed = []
    for fan_id in range(FAN_NUM):
        if write_fan_profile(ser, fan_profile=profile, fan_id=fan_id, config=cfg):
            print(f"  Fan {fan_id}: written")
        else:
            print(f"  Fan {fan_id}: ERROR")
            failed.append(fan_id)

    if failed:
        print(f"\n  WARNING: Failed to write fans: {failed}")
    else:
        print(f"\n  All {FAN_NUM} fans in profile {profile} written successfully.")

# ---------------------------------------------------------------------------
# RGB profiles
# ---------------------------------------------------------------------------

def _print_rgb_config(cfg, profile: int) -> None:
    from benchlab_pycore.core import RGBMode, RGBDirection
    try:
        mode_name = RGBMode(cfg.Mode).name
    except ValueError:
        mode_name = str(cfg.Mode)
    try:
        dir_name = RGBDirection(cfg.Direction).name
    except ValueError:
        dir_name = str(cfg.Direction)

    print(f"  Profile {profile}:")
    print(f"    Mode      : {cfg.Mode} ({mode_name})")
    print(f"    Red       : {cfg.Red}")
    print(f"    Green     : {cfg.Green}")
    print(f"    Blue      : {cfg.Blue}")
    print(f"    Direction : {cfg.Direction} ({dir_name})")
    print(f"    Speed     : {cfg.Speed}")


def cmd_read_rgb_profile(ser, product_id) -> None:
    _header("RGB PROFILE — READ")
    from benchlab_pycore.core import read_rgb_profile, RGB_PROFILE_NUM

    choice = _menu("Select scope", [
        "Read all RGB profiles",
        "Read one RGB profile",
    ])
    if choice < 0:
        return

    profiles = (
        list(range(RGB_PROFILE_NUM)) if choice == 0
        else [_input_int(f"Profile (0–{RGB_PROFILE_NUM - 1})", 0, RGB_PROFILE_NUM - 1, 0)]
    )

    for p in profiles:
        cfg = read_rgb_profile(ser, rgb_profile=p)
        if cfg is None:
            print(f"  Profile {p}: no response from firmware")
        else:
            _print_rgb_config(cfg, p)
            print()


def cmd_write_rgb_profile(ser, product_id) -> None:
    _header("RGB PROFILE — WRITE")
    from benchlab_pycore.core import (
        read_rgb_profile, write_rgb_profile,
        RGBConfigStruct, RGBMode, RGBDirection, RGB_PROFILE_NUM,
    )

    profile = _input_int(f"Profile (0–{RGB_PROFILE_NUM - 1})", 0, RGB_PROFILE_NUM - 1, 0)

    current = read_rgb_profile(ser, rgb_profile=profile)
    if current is None:
        print("  WARNING: Could not read current profile. Using zeros as defaults.")
        current = RGBConfigStruct()
    else:
        print("\n  Current configuration:")
        _print_rgb_config(current, profile)

    print("\n  Enter new values (press Enter to keep current):")
    cfg = RGBConfigStruct()

    modes = "  ".join(f"{m.value}={m.name}" for m in RGBMode)
    print(f"\n  RGB Modes: {modes}")
    cfg.Mode      = _input_int("  Mode", 0, 9, current.Mode)
    cfg.Red       = _input_int("  Red       (0–255)", 0, 255, current.Red)
    cfg.Green     = _input_int("  Green     (0–255)", 0, 255, current.Green)
    cfg.Blue      = _input_int("  Blue      (0–255)", 0, 255, current.Blue)
    print(f"\n  Direction: 0=CLOCKWISE  1=COUNTER_CLOCKWISE")
    cfg.Direction = _input_int("  Direction (0–1)", 0, 1, current.Direction)
    cfg.Speed     = _input_int("  Speed     (0–255)", 0, 255, current.Speed)

    print("\n  New configuration to write:")
    _print_rgb_config(cfg, profile)

    if not _confirm(f"Write RGB profile {profile} to device?"):
        print("  Cancelled.")
        return

    if write_rgb_profile(ser, rgb_profile=profile, config=cfg):
        print("  Written successfully.")
    else:
        print("  ERROR: Write failed.")


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _print_calibration(cal) -> None:
    from ctypes import sizeof
    print(f"  CRC   : 0x{cal.Crc:04X}  ({sizeof(cal)} bytes)")
    print(f"  Vdd   : Offset={cal.Vdd.Offset:6d}  GainOffset={cal.Vdd.GainOffset:6d}")
    print(f"  Vref  : Offset={cal.Vref.Offset:6d}  GainOffset={cal.Vref.GainOffset:6d}")
    print(f"  Tamb  : Offset={cal.Tamb.Offset:6d}  GainOffset={cal.Tamb.GainOffset:6d}")
    print(f"  Hum   : Offset={cal.Hum.Offset:6d}  GainOffset={cal.Hum.GainOffset:6d}")
    for i, v in enumerate(cal.Vin):
        print(f"  Vin[{i:2d}]: Offset={v.Offset:6d}  GainOffset={v.GainOffset:6d}")
    for i, v in enumerate(cal.Ts):
        print(f"  Ts[{i}]  : Offset={v.Offset:6d}  GainOffset={v.GainOffset:6d}  TsB={cal.TsB[i]}")
    for i, v in enumerate(cal.PowerReadingVoltage):
        print(f"  PwrV[{i:2d}]: Offset={v.Offset:6d}  GainOffset={v.GainOffset:6d}")
    for i, v in enumerate(cal.PowerReadingCurrent):
        print(f"  PwrI[{i:2d}]: Offset={v.Offset:6d}  GainOffset={v.GainOffset:6d}")


def cmd_read_calibration(ser, product_id) -> None:
    _header("CALIBRATION — READ (RAM)")
    from benchlab_pycore.core import read_calibration
    cal = read_calibration(ser, product_id=product_id)
    if cal is None:
        print("  ERROR: Failed to read calibration.")
        return
    _print_calibration(cal)


def cmd_load_calibration(ser, product_id) -> None:
    _header("CALIBRATION — LOAD FROM FLASH INTO RAM")
    from benchlab_pycore.core import load_calibration, CAL_FACTORY, CAL_USER

    choice = _menu("Load from which flash slot?", [
        f"Factory slot (CAL_FACTORY = {CAL_FACTORY})  — recommended for recovery",
        f"User slot    (CAL_USER    = {CAL_USER})  — last saved user calibration",
    ])
    if choice < 0:
        return

    cal_id = CAL_FACTORY if choice == 0 else CAL_USER
    slot   = "factory" if cal_id == CAL_FACTORY else "user"

    if not _confirm(f"Load {slot} calibration from flash into RAM?"):
        print("  Cancelled.")
        return

    if load_calibration(ser, cal_id):
        print(f"  Loaded {slot} calibration into RAM.")
        print("  Note: this does NOT persist — use 'Store to flash' to save.")
    else:
        print("  ERROR: Load failed.")


def cmd_store_calibration(ser, product_id) -> None:
    _header("CALIBRATION — STORE RAM TO FLASH")
    from benchlab_pycore.core import store_calibration, CAL_FACTORY, CAL_USER

    choice = _menu("Store to which flash slot?", [
        f"User slot    (CAL_USER    = {CAL_USER})  — overwrites saved user calibration",
        f"Factory slot (CAL_FACTORY = {CAL_FACTORY})  — overwrites factory calibration ⚠",
    ])
    if choice < 0:
        return

    cal_id = CAL_USER if choice == 0 else CAL_FACTORY
    slot   = "user" if cal_id == CAL_USER else "FACTORY"

    if not _confirm(f"Store current RAM calibration to {slot} flash slot?"):
        print("  Cancelled.")
        return

    if cal_id == CAL_FACTORY:
        if not _confirm("This will OVERWRITE the factory calibration. Are you absolutely sure?"):
            print("  Cancelled.")
            return

    if store_calibration(ser, cal_id):
        print(f"  Stored to {slot} slot.")
    else:
        print("  ERROR: Store failed.")


# ---------------------------------------------------------------------------
# Config save / load / reset
# ---------------------------------------------------------------------------

def cmd_save_config(ser, product_id) -> None:
    _header("CONFIG — SAVE TO FLASH")
    from benchlab_pycore.core import send_action
    if not _confirm("Save current device configuration (name, fan profiles, RGB) to flash?"):
        print("  Cancelled.")
        return
    if send_action(ser, action=0):   # CONFIG_ACTION_SAVE = 0
        print("  Config saved.")
    else:
        print("  ERROR: Save failed.")


def cmd_load_config(ser, product_id) -> None:
    _header("CONFIG — RELOAD FROM FLASH")
    from benchlab_pycore.core import send_action
    if not _confirm("Reload configuration from flash? Unsaved RAM changes will be lost."):
        print("  Cancelled.")
        return
    if send_action(ser, action=1):   # CONFIG_ACTION_LOAD = 1
        print("  Config reloaded from flash.")
    else:
        print("  ERROR: Reload failed.")


def cmd_reset_config(ser, product_id) -> None:
    _header("CONFIG — RESET TO DEFAULTS")
    from benchlab_pycore.core import send_action
    print("  WARNING: This resets name, fan profiles, and RGB to firmware defaults.")
    print("           It does NOT reset calibration.")
    if not _confirm("Reset configuration to firmware defaults?"):
        print("  Cancelled.")
        return
    if not _confirm("Are you sure? This cannot be undone without reflashing."):
        print("  Cancelled.")
        return
    if send_action(ser, action=2):   # CONFIG_ACTION_RESET = 2
        print("  Config reset to defaults.")
        print("  Use 'Save config to flash' to persist the reset.")
    else:
        print("  ERROR: Reset failed.")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

MENU_OPTIONS = [
    ("Device info",                 cmd_device_info),
    # ── Name ──────────────────────────────────────────────────────────────
    ("Read friendly name",          cmd_read_name),
    ("Write friendly name",         cmd_write_name),
    # ── Fan ───────────────────────────────────────────────────────────────
    ("Read fan profile(s)",         cmd_read_fan_profile),
    ("Write fan profile",           cmd_write_fan_profile),
    ("Write all fans in profile",   cmd_write_fan_profile_all),
    # ── RGB ───────────────────────────────────────────────────────────────
    ("Read RGB profile(s)",         cmd_read_rgb_profile),
    ("Write RGB profile",           cmd_write_rgb_profile),
    # ── Calibration ───────────────────────────────────────────────────────
    ("Read calibration (RAM)",      cmd_read_calibration),
    ("Load calibration from flash", cmd_load_calibration),
    ("Store calibration to flash",  cmd_store_calibration),
    # ── Config ────────────────────────────────────────────────────────────
    ("Save config to flash",        cmd_save_config),
    ("Reload config from flash",    cmd_load_config),
    ("Reset config to defaults",    cmd_reset_config),
]


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else None

    _header("BENCHLAB DEVICE CONFIGURATION TOOL")
    ser, product_id = connect(port)

    try:
        while True:
            _section("MAIN MENU")
            for i, (label, _) in enumerate(MENU_OPTIONS, 1):
                print(f"  {i:2d}.  {label}")
            print(f"\n   0.  Exit")

            raw = input("\n  Choice: ").strip()
            try:
                choice = int(raw)
            except ValueError:
                continue

            if choice == 0:
                print("\n  Goodbye.")
                break
            if 1 <= choice <= len(MENU_OPTIONS):
                label, fn = MENU_OPTIONS[choice - 1]
                try:
                    fn(ser, product_id)
                except Exception as e:
                    print(f"\n  ERROR: {e}")
                input("\n  Press Enter to continue...")
    finally:
        ser.close()
        print(f"  Connection to {ser.port} closed.")


if __name__ == "__main__":
    main()