"""
Utility helpers for BENCHLAB

This module provides utility functions for formatting sensor data values
into human-readable formats.
"""

from typing import Optional, Union


def format_chip_temp(value: Union[int, float]) -> float:
    """Format chip temperature value from raw sensor data.
    
    Args:
        value (Union[int, float]): Raw temperature value from sensor.
    
    Returns:
        float: Temperature in degrees Celsius, rounded to 1 decimal place.
    
    Note:
        This function assumes the raw value is already in the correct scale
        for chip temperature (typically already in degrees Celsius).
    
    Example:
        >>> temp = format_chip_temp(42)
        >>> print(f"Chip temp: {temp}°C")
        Chip temp: 42.0°C
    """
    return round(value / 1, 1)


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
    temp_c = value / 10
    if temp_c > 100.0 or temp_c < -100.0:
        return None
    return round(temp_c, 1)
