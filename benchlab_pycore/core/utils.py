"""
Utility helpers for BENCHLAB

This module provides utility functions for formatting sensor data values
into human-readable formats.
"""

from typing import Optional, Union


# Firmware at which Tchip switched from whole degrees C to 0.1 degC, matching
# every other temperature on the wire. Mirrors the `tchip-whole-degrees`
# advisory (BENCHLAB-FW issue #9); the pairs come from its `affects` block.
# Firmware at or above these reports deci-degrees.
_TCHIP_DECIDEG_FROM = {
    0x10: 3,   # BENCHLAB ORIGINAL
    0x11: 4,   # BENCHLAB 2
}


def format_chip_temp(
    value: Union[int, float],
    product_id: Optional[int] = None,
    fw_version: Optional[int] = None,
) -> Optional[float]:
    """Format the MCU chip temperature from raw sensor data.

    The unit is firmware-dependent. ORIGINAL fw02 and BL2 fw03 report Tchip in
    whole degrees Celsius, while every other temperature on the wire uses
    0.1 degC; ORIGINAL fw03 and BL2 fw04 fixed this to be consistent. Applying
    the wrong scale is out by 10x -- and in this library's case the
    out-of-range guard then discarded the value entirely, so chip temperature
    silently read as None on current firmware.

    Args:
        value:      Raw Tchip value from the sensor struct.
        product_id: ProductId from ``read_device()``. Without it the legacy
                    whole-degree scale is assumed, for backwards compatibility.
        fw_version: FwVersion from ``read_device()``.

    Returns:
        Temperature in degrees Celsius rounded to 1 decimal, or None if the
        reading is the 0x7FFF sentinel or outside -100..100 degC.

    Note:
        Pass *product_id* and *fw_version* whenever you have them: they are
        what makes this correct on current firmware. See the
        ``tchip-whole-degrees`` advisory in the firmware repo.

    Example:
        >>> format_chip_temp(380, 0x11, 4)   # BL2 fw04: deci-degrees
        38.0
        >>> format_chip_temp(38, 0x11, 3)    # BL2 fw03: whole degrees
        38.0
    """
    if value == 0x7FFF:
        return None

    deci_from = _TCHIP_DECIDEG_FROM.get(product_id)
    if (product_id is not None and fw_version is not None
            and deci_from is not None and fw_version >= deci_from):
        temp_c = value / 10
    else:
        temp_c = float(value)

    if temp_c > 100.0 or temp_c < -100.0:
        return None
    return round(temp_c, 1)


def format_temp(value: Union[int, float]) -> Optional[float]:
    """Format temperature value from raw sensor data.
    
    Args:
        value (Union[int, float]): Raw temperature value from sensor.
    
    Returns:
        Optional[float]: Temperature in degrees Celsius, rounded to 1 decimal place,
                        or None if the value is outside valid temperature range.
    
    Note:
        This function converts from tenths of degrees Celsius to degrees Celsius.
        Returns None for values outside the range -1000 to 1000 (representing
        -100.0 deg C to 100.0 deg C).
    
    Example:
        >>> temp = format_temp(255)  # 25.5 deg C
        >>> print(f"Temp: {temp} deg C")
        Temp: 25.5 deg C
        
        >>> temp = format_temp(1500)  # Invalid range
        >>> print(temp)
        None
    """
    if value == 0x7FFF:
        return None
    temp_c = value / 10
    if temp_c > 100.0 or temp_c < -100.0:
        return None
    return round(temp_c, 1)