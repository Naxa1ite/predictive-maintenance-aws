"""DynamoDB access layer (single-table design).

Items (pk / sk):
  MACHINE#<id> / PRED#<iso-ts>#<id8>   one prediction
  MACHINE#<id> / LATEST                latest state of a machine (alert dedup state)
  MACHINE#<id> / EVENT#<iso-ts>#<id8>  a high-risk event (maintenance workflow)
  STATS / COUNTER                      atomic total-prediction counter
GSI1 (gsi1pk / gsi1sk) powers every dashboard query without a table scan:
  LATEST items  -> MACHINE / <machine_id>
  PRED items    -> PRED    / <iso-ts>
  EVENT items   -> EVENT   / <iso-ts>
"""
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

MAINTENANCE_STATUSES = ("OPEN", "ACKNOWLEDGED", "UNDER_MAINTENANCE", "RESOLVED")


def _table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _dec(d):
    """Convert floats to Decimal for DynamoDB."""
    return {k: (Decimal(str(v)) if isinstance(v, float) else v) for k, v in d.items()}


def save_prediction(reading, result, timestamp=None):
    ts = timestamp or now_iso()
    pid = uuid.uuid4().hex[:8]
    mid = reading["machine_id"]
    item = _dec({
        "pk": f"MACHINE#{mid}", "sk": f"PRED#{ts}#{pid}",
        "gsi1pk": "PRED", "gsi1sk": ts,
        "prediction_id": f"{ts}#{pid}", "machine_id": mid, "timestamp": ts,
        "air_temperature": reading["air_temperature"],
        "process_temperature": reading["process_temperature"],
        "rotational_speed": reading["rotational_speed"],
        "torque": reading["torque"], "tool_wear": reading["tool_wear"],
        "machine_type": reading["machine_type"], "source": reading["source"],
        "failure_probability": result["failure_probability"],
        "risk_level": result["risk_level"], "predicted_class": result["predicted_class"],
        "model_version": result["model_version"],
    })
    t = _table()
    t.put_item(Item=item)
    t.update_item(Key={"pk": "STATS", "sk": "COUNTER"},
                  UpdateExpression="ADD total_predictions :one", ExpressionAttributeValues={":one": 1})
    return item


def update_latest(item):
    """Upsert the machine's LATEST item and return the PREVIOUS risk level / last alert time."""
    t = _table()
    resp = t.update_item(
        Key={"pk": item["pk"], "sk": "LATEST"},
        UpdateExpression=("SET gsi1pk = :g1, gsi1sk = :mid, machine_id = :mid, #ts = :ts, "
                          "air_temperature = :a, process_temperature = :p, rotational_speed = :r, "
                          "torque = :tq, tool_wear = :w, machine_type = :mt, #src = :src, "
                          "failure_probability = :fp, risk_level = :rl, predicted_class = :pc, "
                          "model_version = :mv"),
        ExpressionAttributeNames={"#ts": "timestamp", "#src": "source"},
        ExpressionAttributeValues={
            ":g1": "MACHINE", ":mid": item["machine_id"], ":ts": item["timestamp"],
            ":a": item["air_temperature"], ":p": item["process_temperature"],
            ":r": item["rotational_speed"], ":tq": item["torque"], ":w": item["tool_wear"],
            ":mt": item["machine_type"], ":src": item["source"],
            ":fp": item["failure_probability"], ":rl": item["risk_level"],
            ":pc": item["predicted_class"], ":mv": item["model_version"],
        },
        ReturnValues="ALL_OLD",
    )
    old = resp.get("Attributes", {})
    return old.get("risk_level"), old.get("last_alert_at")


def create_event(item):
    ts, eid = item["timestamp"], uuid.uuid4().hex[:8]
    ev = _dec({
        "pk": item["pk"], "sk": f"EVENT#{ts}#{eid}",
        "gsi1pk": "EVENT", "gsi1sk": ts,
        "event_id": f"{ts}#{eid}", "machine_id": item["machine_id"], "timestamp": ts,
        "failure_probability": item["failure_probability"], "risk_level": item["risk_level"],
        "torque": item["torque"], "rotational_speed": item["rotational_speed"],
        "tool_wear": item["tool_wear"], "source": item["source"],
        "maintenance_status": "OPEN", "alert_sent": False,
    })
    _table().put_item(Item=ev)
    return ev


def mark_alert(item, event, sent_at):
    t = _table()
    t.update_item(Key={"pk": item["pk"], "sk": "LATEST"},
                  UpdateExpression="SET last_alert_at = :t",
                  ExpressionAttributeValues={":t": sent_at})
    t.update_item(Key={"pk": event["pk"], "sk": event["sk"]},
                  UpdateExpression="SET alert_sent = :s", ExpressionAttributeValues={":s": True})


def update_event_status(machine_id, event_id, status):
    if status not in MAINTENANCE_STATUSES:
        raise ValueError(f"status must be one of {MAINTENANCE_STATUSES}")
    from botocore.exceptions import ClientError
    try:
        r = _table().update_item(
            Key={"pk": f"MACHINE#{machine_id}", "sk": f"EVENT#{event_id}"},
            UpdateExpression="SET maintenance_status = :s, status_updated_at = :t",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeValues={":s": status, ":t": now_iso()},
            ReturnValues="ALL_NEW")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise
    return r["Attributes"]


def _gsi_query(pk, limit, descending=True):
    r = _table().query(IndexName="gsi1", KeyConditionExpression=Key("gsi1pk").eq(pk),
                       ScanIndexForward=not descending, Limit=limit)
    return r["Items"]


def list_machines(limit=200):
    return _gsi_query("MACHINE", limit, descending=False)


def recent_predictions(limit=100, machine_id=None, risk_level=None):
    if machine_id:
        r = _table().query(KeyConditionExpression=Key("pk").eq(f"MACHINE#{machine_id}") &
                           Key("sk").begins_with("PRED#"), ScanIndexForward=False, Limit=limit)
        items = r["Items"]
        if risk_level:
            items = [i for i in items if i["risk_level"] == risk_level]
        return items
    fetch = limit if not risk_level else min(limit * 5, 1000)
    items = _gsi_query("PRED", fetch)
    if risk_level:
        items = [i for i in items if i["risk_level"] == risk_level][:limit]
    return items


def recent_events(limit=50):
    return _gsi_query("EVENT", limit)


def total_predictions():
    r = _table().get_item(Key={"pk": "STATS", "sk": "COUNTER"})
    return int(r.get("Item", {}).get("total_predictions", 0))
