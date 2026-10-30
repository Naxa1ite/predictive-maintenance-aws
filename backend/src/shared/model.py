"""Pure-Python Random Forest inference from the exported JSON model."""
import json
import os
import struct

from .features import build_features

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "model.json")
_cache = None


def load_model(path=None):
    """Load (and cache) the exported model. Cached across warm Lambda invocations."""
    global _cache
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    if _cache is None:
        with open(_MODEL_PATH, "r", encoding="utf-8") as fh:
            _cache = json.load(fh)
    return _cache


def _tree_proba(tree, x):
    left, right = tree["left"], tree["right"]
    feat, thr, val = tree["feature"], tree["threshold"], tree["p_fail"]
    node = 0
    while left[node] != -1:
        node = left[node] if x[feat[node]] <= thr[node] else right[node]
    return val[node]


def _f32(v):
    """scikit-learn evaluates splits on float32 inputs; mirror that for exact parity."""
    return struct.unpack("f", struct.pack("f", v))[0]


def failure_probability(model, x):
    x = [_f32(v) for v in x]
    trees = model["trees"]
    return sum(_tree_proba(t, x) for t in trees) / len(trees)


def risk_level(model, probability):
    """HIGH iff the model's decision threshold is reached, so the label and the
    probability can never disagree. MEDIUM starts at medium_threshold."""
    if probability >= model["decision_threshold"]:
        return "HIGH"
    if probability >= model["medium_threshold"]:
        return "MEDIUM"
    return "LOW"


def predict(model, reading):
    x = build_features(
        reading["air_temperature"], reading["process_temperature"],
        reading["rotational_speed"], reading["torque"],
        reading["tool_wear"], reading["machine_type"],
    )
    p = failure_probability(model, x)
    risk = risk_level(model, p)
    return {
        "failure_probability": round(p, 4),
        "predicted_class": "FAILURE_PREDICTED" if p >= model["decision_threshold"] else "HEALTHY_PREDICTED",
        "risk_level": risk,
        "model_version": model["model_version"],
    }
