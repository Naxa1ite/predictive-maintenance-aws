"""High-risk alert logic: threshold + de-duplication + SNS email.

Dedup rule: an alert is sent only when the machine ENTERS the alert state
(previous reading was below the threshold) or when ALERT_COOLDOWN_MINUTES have
passed since the last alert for that machine. Identical consecutive high-risk
readings therefore do not spam the subscriber.
"""
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

from . import store

log = logging.getLogger()


def alert_threshold(model):
    """ALERT_THRESHOLD env var (0-1) overrides the model's decision threshold."""
    raw = os.environ.get("ALERT_THRESHOLD", "").strip()
    try:
        v = float(raw)
        if 0 < v <= 1:
            return v
    except ValueError:
        pass
    return model["decision_threshold"]


def should_alert(probability, threshold, previous_risk, last_alert_at, now=None, cooldown_minutes=None):
    if probability < threshold:
        return False
    if previous_risk != "HIGH" or not last_alert_at:
        return True
    cooldown = cooldown_minutes if cooldown_minutes is not None else int(os.environ.get("ALERT_COOLDOWN_MINUTES", "30"))
    now = now or datetime.now(timezone.utc)
    last = datetime.strptime(last_alert_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return now - last >= timedelta(minutes=cooldown)


def build_message(item):
    return (
        "PREDICTIVE MAINTENANCE ALERT (model prediction, not a confirmed failure)\n\n"
        f"Machine:             {item['machine_id']}\n"
        f"Failure probability: {float(item['failure_probability']):.1%}\n"
        f"Risk level:          {item['risk_level']}\n"
        f"Timestamp (UTC):     {item['timestamp']}\n"
        f"Torque:              {item['torque']} Nm\n"
        f"Rotational speed:    {item['rotational_speed']} rpm\n"
        f"Tool wear:           {item['tool_wear']} min\n"
        f"Data source:         {item['source']}\n\n"
        "Please inspect the machine. This academic prototype is not suitable for safety-critical decisions."
    )


def process(item, previous_risk, last_alert_at, model, sns_client=None):
    """Create an event and publish to SNS when warranted. Returns the event or None."""
    if not should_alert(float(item["failure_probability"]), alert_threshold(model), previous_risk, last_alert_at):
        return None
    event = store.create_event(item)
    topic = os.environ.get("ALERT_TOPIC_ARN")
    if not topic:
        log.warning("ALERT_TOPIC_ARN not set; event stored without notification")
        return event
    try:
        (sns_client or boto3.client("sns")).publish(
            TopicArn=topic,
            Subject=f"[Predictive Maintenance] High risk: {item['machine_id']}"[:100],
            Message=build_message(item))
        store.mark_alert(item, event, store.now_iso())
        event["alert_sent"] = True
        log.info("ALERT_SENT machine=%s probability=%s", item["machine_id"], item["failure_probability"])
    except Exception:  # alert failure must never fail the prediction itself
        log.exception("ALERT_FAILED machine=%s", item["machine_id"])
    return event
