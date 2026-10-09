"""Run the risk service on your own computer (uses the real Open-Meteo forecast).

    python backend/risk/local_run.py            # prints a short table
    python backend/risk/local_run.py --json     # prints the full JSON the website will receive

In October Delhi is mostly dry, so most spots will be green. That is correct, not a bug.
"""
import json
import sys

import handler

resp = handler.get_risk()
if "--json" in sys.argv:
    print(json.dumps(resp, indent=2))
else:
    print(f"Forecast model used: {resp['forecast_model_used']}   (generated {resp['generated_at']})")
    print(f"{'hotspot':36s} {'tier':8s} {'ratio':>6s} {'max 3h mm':>10s} {'limit 3h':>9s}")
    for h in resp["hotspots"]:
        print(f"{h['name']:36s} {h['tier']:8s} {str(h['ratio']):>6s} {str(h['forecast']['max_3h_mm']):>10s} "
              f"{str(h['limit']['rain3h_mm']):>9s}")
    print(resp["credit"])
