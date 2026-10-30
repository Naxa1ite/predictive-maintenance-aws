"""Request validation for POST /predict."""
import re

MACHINE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

# (min, max) ranges, wider than AI4I's observed range but physically plausible.
RANGES = {
    "air_temperature": (273.0, 330.0),       # K
    "process_temperature": (273.0, 345.0),   # K
    "rotational_speed": (0.0, 5000.0),       # rpm
    "torque": (0.0, 150.0),                  # Nm
    "tool_wear": (0.0, 500.0),               # min
}
MACHINE_TYPES = ("L", "M", "H")
SOURCES = ("manual", "simulated")


class ValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_prediction_request(body):
    """Return a cleaned reading dict or raise ValidationError listing every problem."""
    if not isinstance(body, dict):
        raise ValidationError(["Request body must be a JSON object"])
    errors, clean = [], {}

    mid = body.get("machine_id")
    if not isinstance(mid, str) or not MACHINE_ID_RE.match(mid):
        errors.append("machine_id is required: 1-40 characters from A-Z a-z 0-9 _ -")
    else:
        clean["machine_id"] = mid

    for field, (lo, hi) in RANGES.items():
        v = body.get(field)
        if v is None:
            errors.append(f"{field} is required")
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            errors.append(f"{field} must be a number")
        elif v != v or v in (float("inf"), float("-inf")):
            errors.append(f"{field} must be finite")
        elif not lo <= v <= hi:
            errors.append(f"{field} must be between {lo} and {hi}")
        else:
            clean[field] = float(v)

    mt = body.get("machine_type")
    if mt not in MACHINE_TYPES:
        errors.append("machine_type must be one of L, M, H")
    else:
        clean["machine_type"] = mt

    src = body.get("source", "manual")
    if src not in SOURCES:
        errors.append("source must be 'manual' or 'simulated'")
    else:
        clean["source"] = src

    if (not errors and clean["process_temperature"] < clean["air_temperature"]):
        errors.append("process_temperature must not be below air_temperature")

    if errors:
        raise ValidationError(errors)
    return clean
