"""GET /dashboard: summary statistics assembled from indexed queries (no scans)."""
import logging

from shared import store
from shared.http import error, response

log = logging.getLogger()


def handler(event, context):
    try:
        machines = store.list_machines()
        recent = store.recent_predictions(limit=200)
        events = store.recent_events(limit=20)
        by_risk = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for m in machines:
            by_risk[m["risk_level"]] = by_risk.get(m["risk_level"], 0) + 1
        distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for p in recent:
            distribution[p["risk_level"]] = distribution.get(p["risk_level"], 0) + 1
        return response(200, {
            "summary": {
                "total_machines": len(machines),
                "healthy_machines": by_risk["LOW"],
                "medium_risk_machines": by_risk["MEDIUM"],
                "high_risk_machines": by_risk["HIGH"],
                "total_predictions": store.total_predictions(),
                "open_events": sum(1 for e in events if e.get("maintenance_status") == "OPEN"),
            },
            "machines": machines,
            "risk_distribution_recent": distribution,
            "recent_predictions": recent,
            "recent_events": events,
            "note": "All values are model estimates; simulated readings are labelled source=simulated.",
        })
    except Exception:
        log.exception("DASHBOARD_FAILED")
        return error(500, "Internal error")
