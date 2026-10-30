"""HTTP helpers: JSON responses, Decimal handling, logging setup."""
import json
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError(f"not serialisable: {type(o)}")


def response(status, body):
    # CORS headers come from the HTTP API's CorsConfiguration (see template.yaml).
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, default=_default),
    }


def error(status, message, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return response(status, body)


def parse_json_body(event):
    raw = event.get("body")
    if raw is None:
        return None
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode("utf-8")
    return json.loads(raw)
