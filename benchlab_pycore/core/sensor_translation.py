# benchlab/core/sensor_translation.py

from typing import Dict, Any
from .structures import SENSOR_VIN_NUM, SensorStruct
from .utils import format_chip_temp, format_temp


def translate_sensor_struct(sensor_struct: SensorStruct) -> Dict[str, Any]:
    """Return a flat dict of interpreted sensor values suitable for CSV, graphs, MQTT, etc.
    
    Args:
        sensor_struct (SensorStruct): Raw sensor data from read_sensors().
    
    Returns:
        Dict[str, Any]: Dictionary containing human-readable sensor values with the following keys:
            - Power measurements: 'SYS_Power', 'CPU_Power', 'GPU_Power', 'MB_Power'
            - Voltage measurements: 'EPS1_Voltage', 'EPS2_Voltage', '12V_Voltage', etc.
            - Current measurements: 'EPS1_Current', 'EPS2_Current', '12V_Current', etc.
            - Power measurements: 'EPS1_Power', 'EPS2_Power', '12V_Power', etc.
            - Temperature measurements: 'Chip_Temp', 'Ambient_Temp', 'Temp_Sensor_1', etc.
            - Fan measurements: 'Fan1_Duty', 'Fan1_RPM', 'Fan1_Status', etc.
            - Other: 'Vdd', 'Vref', 'Humidity', 'FanExtDuty'
    
    Note:
        All voltage values are converted from millivolts to volts.
        All power values are converted from milliwatts to watts.
        All current values are converted from milliamps to amps.
        Temperature values are converted from tenths of degrees to degrees Celsius.
    
    Example:
        >>> from benchlab_pycore.core import read_sensors, translate_sensor_struct
        >>> ser = serial.Serial('COM3', 115200)
        >>> sensors = read_sensors(ser)
        >>> if sensors:
        >>>     data = translate_sensor_struct(sensors)
        >>>     print(f"CPU Power: {data['CPU_Power']}W")
        >>>     print(f"Chip Temp: {data['Chip_Temp']}°C")
    """
    data = {}

    # Power
    power = sensor_struct.PowerReadings
    power_cpu = (power[0].Power + power[1].Power) / 1000
    power_gpu = sum([power[i].Power for i in range(6, 11)]) / 1000
    power_mb = sum([power[i].Power for i in range(2, 6)]) / 1000
    power_system = power_cpu + power_gpu + power_mb
    data.update({
        "SYS_Power": power_system,
        "CPU_Power": power_cpu,
        "GPU_Power": power_gpu,
        "MB_Power": power_mb,
    })

    # EPS, ATX, PCIe
    eps_labels = ["EPS1", "EPS2"]
    atx_labels = ["12V", "5V", "5VSB", "3.3V"]
    pcie_labels = ["PCIE8_1", "PCIE8_2", "PCIE8_3", "HPWR1", "HPWR2"]

    for i, label in enumerate(eps_labels):
        data[f"{label}_Voltage"] = power[i].Voltage / 1000
        data[f"{label}_Current"] = power[i].Current / 1000
        data[f"{label}_Power"] = power[i].Power / 1000

    for i, label in enumerate(atx_labels):
        idx = [5, 3, 4, 2][i]
        data[f"{label}_Voltage"] = power[idx].Voltage / 1000
        data[f"{label}_Current"] = power[idx].Current / 1000
        data[f"{label}_Power"] = power[idx].Power / 1000

    for i, label in enumerate(pcie_labels):
        idx = 6 + i
        data[f"{label}_Voltage"] = power[idx].Voltage / 1000
        data[f"{label}_Current"] = power[idx].Current / 1000
        data[f"{label}_Power"] = power[idx].Power / 1000

    # Voltage
    vin_names = [f"VIN_{i}" for i in range(SENSOR_VIN_NUM)]
    for name, value in zip(vin_names, sensor_struct.Vin):
        data[name] = value / 1000
    data["Vdd"] = sensor_struct.Vdd / 1000
    data["Vref"] = sensor_struct.Vref / 1000

    # Temperature
    data["Chip_Temp"] = format_chip_temp(sensor_struct.Tchip)
    data["Ambient_Temp"] = format_temp(sensor_struct.Tamb)
    data["Humidity"] = sensor_struct.Hum / 10
    for i, t in enumerate(sensor_struct.Ts):
        data[f"Temp_Sensor_{i+1}"] = format_temp(t)

    # Fans
    for i, f in enumerate(sensor_struct.Fans):
        data[f"Fan{i+1}_Duty"] = f.Duty
        data[f"Fan{i+1}_RPM"] = f.Tach
        data[f"Fan{i+1}_Status"] = f.Enable
    data["FanExtDuty"] = sensor_struct.FanExtDuty

    return data
