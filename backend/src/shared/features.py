"""Feature engineering shared by training (ml/) and inference (Lambda).

Pure Python on purpose: the Lambda package then needs no numpy/scikit-learn,
and training and inference are guaranteed to build identical feature vectors.
"""
import math

MACHINE_TYPES = ("L", "M", "H")

FEATURE_NAMES = [
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear",
    "temp_diff",       # process - air temperature (K)
    "power_w",         # torque * angular velocity (W)
    "wear_torque",     # tool wear * torque (overstrain proxy)
    "type_L",
    "type_M",
    "type_H",
]


def build_features(air_temperature, process_temperature, rotational_speed,
                   torque, tool_wear, machine_type):
    """Return the feature vector (list of floats) in FEATURE_NAMES order."""
    power_w = torque * rotational_speed * 2.0 * math.pi / 60.0
    return [
        float(air_temperature),
        float(process_temperature),
        float(rotational_speed),
        float(torque),
        float(tool_wear),
        float(process_temperature - air_temperature),
        float(power_w),
        float(tool_wear * torque),
        1.0 if machine_type == "L" else 0.0,
        1.0 if machine_type == "M" else 0.0,
        1.0 if machine_type == "H" else 0.0,
    ]
