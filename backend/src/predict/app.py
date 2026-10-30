"""POST /predict: validate -> model inference -> store in DynamoDB -> alert if needed."""
import json
import logging

from shared import alerts, model as mdl, store
from shared.http import error, parse_json_body, response
from shared.validation import ValidationError, validate_prediction_request

log = logging.getLogger()


def handler(event, context):
    try:
        body = parse_json_body(event)
    except (ValueError, UnicodeDecodeError):
        return error(400, "Request body is not valid JSON")
    if body is None:
        return error(400, "Request body is required")
    try:
        reading = validate_prediction_request(body)
    except ValidationError as exc:
        return error(422, "Validation failed", exc.errors)

    try:
        model = mdl.load_model()
        result = mdl.predict(model, reading)
        item = store.save_prediction(reading, result)
        prev_risk, last_alert = store.update_latest(item)
        ev = alerts.process(item, prev_risk, last_alert, model)
    except Exception:
        log.exception("PREDICT_FAILED machine=%s", reading.get("machine_id"))
        return error(500, "Internal error while processing the prediction")

    log.info("PREDICTION machine=%s risk=%s p=%s source=%s", reading["machine_id"],
             result["risk_level"], result["failure_probability"], reading["source"])
    return response(200, {
        "machine_id": reading["machine_id"],
        "predicted_class": result["predicted_class"],
        "failure_probability": result["failure_probability"],
        "risk_level": result["risk_level"],
        "timestamp": item["timestamp"],
        "model_version": result["model_version"],
        "source": reading["source"],
        "alert_triggered": bool(ev and ev.get("alert_sent")),
        "event_id": ev["event_id"] if ev else None,
        "disclaimer": "Model estimate only; not a confirmed physical machine condition.",
        "input": {k: reading[k] for k in ("air_temperature", "process_temperature",
                                          "rotational_speed", "torque", "tool_wear", "machine_type")},
    })
