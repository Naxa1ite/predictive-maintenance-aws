import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import sent_alerts
from dashboard.app import handler as dashboard_handler
from health.app import handler as health_handler
from history.app import handler as history_handler
from predict.app import handler as predict_handler
from shared import alerts
from shared.validation import ValidationError, validate_prediction_request

GOOD = {"machine_id": "MACHINE-001", "air_temperature": 298.1, "process_temperature": 308.6,
        "rotational_speed": 1550, "torque": 42.0, "tool_wear": 120, "machine_type": "M"}
HIGH = {**GOOD, "machine_id": "M-HIGH", "air_temperature": 298.5, "process_temperature": 307.5,
        "rotational_speed": 1300, "torque": 62, "tool_wear": 230}


def post(body, raw=None):
    return predict_handler({"body": raw if raw is not None else json.dumps(body)}, None)


def get(handler, route, q=None):
    return handler({"routeKey": route, "queryStringParameters": q}, None)


# ---------- validation ----------
def test_valid_request_passes():
    assert validate_prediction_request(GOOD)["source"] == "manual"


@pytest.mark.parametrize("patch,msg", [
    ({"machine_id": ""}, "machine_id"), ({"machine_id": "bad id!"}, "machine_id"),
    ({"torque": -1}, "torque"), ({"torque": "40"}, "torque"), ({"rotational_speed": 99999}, "rotational_speed"),
    ({"tool_wear": None}, "tool_wear"), ({"machine_type": "Z"}, "machine_type"), ({"source": "x"}, "source"),
    ({"air_temperature": True}, "air_temperature"), ({"process_temperature": 290.0}, "process_temperature"),
])
def test_invalid_fields_rejected(patch, msg):
    with pytest.raises(ValidationError) as e:
        validate_prediction_request({**GOOD, **patch})
    assert any(msg in m for m in e.value.errors)


def test_missing_fields_all_reported():
    with pytest.raises(ValidationError) as e:
        validate_prediction_request({})
    assert len(e.value.errors) >= 6


def test_non_object_body():
    with pytest.raises(ValidationError):
        validate_prediction_request([1, 2])


# ---------- /predict ----------
def test_predict_response_format(aws):
    r = post(GOOD)
    assert r["statusCode"] == 200
    b = json.loads(r["body"])
    for k in ("machine_id", "predicted_class", "failure_probability", "risk_level", "timestamp", "model_version", "disclaimer", "input"):
        assert k in b
    assert b["risk_level"] == "LOW" and b["predicted_class"] == "HEALTHY_PREDICTED"
    assert 0 <= b["failure_probability"] <= 1


def test_predict_bad_json_and_missing_body(aws):
    assert post(None, raw="{not json")["statusCode"] == 400
    assert predict_handler({}, None)["statusCode"] == 400


def test_predict_validation_errors_422(aws):
    r = post({**GOOD, "torque": -5})
    assert r["statusCode"] == 422
    assert "torque" in json.loads(r["body"])["details"][0]


def test_high_risk_stores_event_and_sends_one_alert(aws):
    b = json.loads(post(HIGH)["body"])
    assert b["risk_level"] == "HIGH" and b["alert_triggered"] is True
    assert sent_alerts(aws) == 1


def test_repeated_high_risk_does_not_resend(aws):
    first = json.loads(post(HIGH)["body"])
    second = json.loads(post(HIGH)["body"])
    assert first["alert_triggered"] and not second["alert_triggered"]
    assert sent_alerts(aws) == 1
    events = json.loads(get(history_handler, "GET /events")["body"])["events"]
    assert len(events) == 1


def test_alert_resent_after_recovery(aws):
    post(HIGH)
    post({**GOOD, "machine_id": "M-HIGH"})   # back to low
    again = json.loads(post(HIGH)["body"])
    assert again["alert_triggered"] is True


def test_should_alert_rules():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    recent = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    assert not alerts.should_alert(0.2, 0.5, None, None)
    assert alerts.should_alert(0.6, 0.5, "LOW", None)
    assert not alerts.should_alert(0.6, 0.5, "HIGH", recent, now, 30)
    assert alerts.should_alert(0.6, 0.5, "HIGH", old, now, 30)


def test_alert_threshold_configurable(monkeypatch):
    model = {"decision_threshold": 0.48}
    monkeypatch.setenv("ALERT_THRESHOLD", "")
    assert alerts.alert_threshold(model) == 0.48
    monkeypatch.setenv("ALERT_THRESHOLD", "0.8")
    assert alerts.alert_threshold(model) == 0.8
    monkeypatch.setenv("ALERT_THRESHOLD", "junk")
    assert alerts.alert_threshold(model) == 0.48


def test_sns_failure_does_not_break_prediction(aws, monkeypatch):
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:ap-south-1:123456789012:does-not-exist")
    r = post(HIGH)
    assert r["statusCode"] == 200 and json.loads(r["body"])["alert_triggered"] is False


# ---------- history / dashboard ----------
def test_history_filters(aws):
    post(GOOD)
    post({**GOOD, "machine_id": "OTHER"})
    post(HIGH)
    allp = json.loads(get(history_handler, "GET /predictions")["body"])
    assert allp["count"] == 3
    one = json.loads(get(history_handler, "GET /predictions", {"machine_id": "OTHER"})["body"])
    assert one["count"] == 1 and one["predictions"][0]["machine_id"] == "OTHER"
    hi = json.loads(get(history_handler, "GET /predictions", {"risk_level": "HIGH"})["body"])
    assert hi["count"] == 1
    assert get(history_handler, "GET /predictions", {"risk_level": "BAD"})["statusCode"] == 400
    assert get(history_handler, "GET /predictions", {"machine_id": "bad id!"})["statusCode"] == 400


def test_history_empty(aws):
    assert json.loads(get(history_handler, "GET /predictions")["body"])["count"] == 0


def test_dashboard_summary(aws):
    post(GOOD)
    post({**GOOD, "machine_id": "B"})
    post(HIGH)
    d = json.loads(get(dashboard_handler, "GET /dashboard")["body"])
    s = d["summary"]
    assert s["total_machines"] == 3 and s["high_risk_machines"] == 1 and s["healthy_machines"] == 2
    assert s["total_predictions"] == 3
    assert len(d["recent_events"]) == 1


def test_dashboard_empty(aws):
    s = json.loads(get(dashboard_handler, "GET /dashboard")["body"])["summary"]
    assert s["total_machines"] == 0 and s["total_predictions"] == 0


def test_event_status_update(aws):
    post(HIGH)
    ev = json.loads(get(history_handler, "GET /events")["body"])["events"][0]

    def patch(body):
        return history_handler({"routeKey": "PATCH /events", "body": json.dumps(body)}, None)

    ok = patch({"machine_id": ev["machine_id"], "event_id": ev["event_id"], "maintenance_status": "ACKNOWLEDGED"})
    assert ok["statusCode"] == 200 and json.loads(ok["body"])["event"]["maintenance_status"] == "ACKNOWLEDGED"
    assert patch({"machine_id": ev["machine_id"], "event_id": ev["event_id"], "maintenance_status": "NOPE"})["statusCode"] == 422
    assert patch({"machine_id": ev["machine_id"], "event_id": "missing", "maintenance_status": "RESOLVED"})["statusCode"] == 404


def test_health():
    r = health_handler({}, None)
    b = json.loads(r["body"])
    assert r["statusCode"] == 200 and b["status"] == "ok" and set(b) == {"status", "model_version"}
