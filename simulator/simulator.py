"""Sensor-data simulator for the predictive-maintenance prototype.

READINGS ARE SYNTHETIC (source="simulated"), not real IoT measurements. The
scenarios only describe plausible sensor ranges; the trained model decides risk.

Never runs by default. Examples:
  python simulator/simulator.py --api-url https://xxx.execute-api.ap-south-1.amazonaws.com --scenarios normal high --rounds 10 --interval 3
  python simulator/simulator.py --dry-run --scenarios high --rounds 5      # local model, no AWS
Stop early with Ctrl+C. --rounds is required and capped at 200.
"""
import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "scenarios.json"), encoding="utf-8") as fh:
    SCENARIOS = json.load(fh)


def next_reading(spec, tick, rng=random):
    g = lambda p: rng.gauss(p[0], p[1])  # noqa: E731
    air = g(spec["air_temperature"])
    return {
        "machine_id": spec["machine_id"],
        "machine_type": spec["machine_type"],
        "air_temperature": round(air, 1),
        "process_temperature": round(air + g(spec["temp_delta"]), 1),
        "rotational_speed": max(0, round(g(spec["rotational_speed"]))),
        "torque": round(max(0.0, g(spec["torque"])), 1),
        "tool_wear": round(min(500, spec["tool_wear_start"] + tick * spec["tool_wear_per_tick"])),
        "source": "simulated",
    }


def post(api_url, reading):
    req = urllib.request.Request(api_url.rstrip("/") + "/predict", data=json.dumps(reading).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except urllib.error.URLError as e:
        return {"error": f"cannot reach API: {e.reason}"}


def local_predict(reading):
    sys.path.insert(0, os.path.join(HERE, "..", "backend", "src"))
    from shared import model as mdl
    return {**mdl.predict(mdl.load_model(), reading), "machine_id": reading["machine_id"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-url", default=os.environ.get("API_URL"), help="Base URL of the deployed API (or env API_URL)")
    ap.add_argument("--scenarios", nargs="+", choices=list(SCENARIOS), default=["normal"])
    ap.add_argument("--rounds", type=int, required=True, help="Number of rounds to send (1-200)")
    ap.add_argument("--interval", type=float, default=3.0, help="Seconds between rounds")
    ap.add_argument("--dry-run", action="store_true", help="Use the local model instead of calling AWS")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)
    if not 1 <= a.rounds <= 200:
        ap.error("--rounds must be between 1 and 200")
    if not a.dry_run and not a.api_url:
        ap.error("--api-url (or env API_URL) is required unless --dry-run")
    rng = random.Random(a.seed)
    machines = [m for s in a.scenarios for m in SCENARIOS[s]["machines"]]
    print(f"Simulating {len(machines)} machine(s) for {a.rounds} round(s). SYNTHETIC data. Ctrl+C to stop.")
    try:
        for tick in range(a.rounds):
            for m in machines:
                reading = next_reading(m, tick, rng)
                res = local_predict(reading) if a.dry_run else post(a.api_url, reading)
                if "error" in res:
                    print(f"[{tick:3d}] {m['machine_id']}: ERROR {res['error']}")
                else:
                    flag = " ALERT" if res.get("alert_triggered") else ""
                    print(f"[{tick:3d}] {m['machine_id']}: {res['risk_level']:6s} p={res['failure_probability']:.3f}{flag}")
            if tick < a.rounds - 1:
                time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
