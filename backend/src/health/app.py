"""GET /health: liveness check; exposes no configuration or secrets."""
import json
import os
from shared.http import response
from shared import model as mdl


def handler(event, context):
    try:
        version = mdl.load_model()["model_version"]
        ok = True
    except Exception:
        version, ok = None, False
    return response(200 if ok else 503, {"status": "ok" if ok else "degraded", "model_version": version})
