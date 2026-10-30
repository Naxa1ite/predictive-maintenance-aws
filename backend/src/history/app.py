"""GET /predictions, GET /events, PATCH /events (maintenance status)."""
import logging

from shared import store
from shared.http import error, parse_json_body, response
from shared.validation import MACHINE_ID_RE

log = logging.getLogger()


def _int(q, key, default, lo, hi):
    try:
        return max(lo, min(hi, int(q.get(key, default))))
    except (TypeError, ValueError):
        return default


def handler(event, context):
    route = event.get("routeKey", "")
    q = event.get("queryStringParameters") or {}
    try:
        if route == "GET /predictions":
            mid, risk = q.get("machine_id"), q.get("risk_level")
            if mid and not MACHINE_ID_RE.match(mid):
                return error(400, "Invalid machine_id")
            if risk and risk not in ("LOW", "MEDIUM", "HIGH"):
                return error(400, "risk_level must be LOW, MEDIUM or HIGH")
            items = store.recent_predictions(_int(q, "limit", 50, 1, 200), mid, risk)
            return response(200, {"count": len(items), "predictions": items})
        if route == "GET /events":
            items = store.recent_events(_int(q, "limit", 50, 1, 200))
            return response(200, {"count": len(items), "events": items})
        if route == "PATCH /events":
            try:
                body = parse_json_body(event) or {}
            except ValueError:
                return error(400, "Request body is not valid JSON")
            mid, eid, status = body.get("machine_id"), body.get("event_id"), body.get("maintenance_status")
            if not (isinstance(mid, str) and MACHINE_ID_RE.match(mid) and isinstance(eid, str) and eid):
                return error(422, "machine_id and event_id are required")
            if status not in store.MAINTENANCE_STATUSES:
                return error(422, f"maintenance_status must be one of {list(store.MAINTENANCE_STATUSES)}")
            updated = store.update_event_status(mid, eid, status)
            if updated is None:
                return error(404, "Event not found")
            return response(200, {"event": updated})
        return error(404, "Route not found")
    except Exception:
        log.exception("HISTORY_FAILED route=%s", route)
        return error(500, "Internal error")
