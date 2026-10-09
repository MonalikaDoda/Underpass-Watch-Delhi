"""AWS Lambda: GET /risk -> risk colour for every hotspot, from the live Open-Meteo forecast.

Weather data by Open-Meteo.com (CC BY 4.0).

Needs these three files in a folder called `data` next to this file (run sync_data.py to copy
them from the repo's /data folder before deploying):
    hotspots.json   thresholds.json   features.csv

Environment variable (optional):
    FORECAST_MODEL   default "ecmwf_ifs". If Open-Meteo rejects it, we retry with its default
                     and say which one was used in the response ("forecast_model_used").
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from risk_core import DISCLAIMER, IST, assess, forecast_rows

HERE = Path(__file__).resolve().parent
API = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 600
_cache: dict = {}


def _data_dir() -> Path:
    for p in (HERE / "data", HERE.parent.parent / "data"):
        if (p / "thresholds.json").exists():
            return p
    raise FileNotFoundError("data folder not found; run sync_data.py")


def load_data():
    d = _data_dir()
    hotspots = json.loads((d / "hotspots.json").read_text(encoding="utf-8"))["hotspots"]
    model = json.loads((d / "thresholds.json").read_text(encoding="utf-8"))
    floods: dict[str, list[float]] = {}
    with open(d / "features.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["outcome"] == "flooded":
                floods.setdefault(r["hotspot_id"], []).append(float(r["rain3h_mm"]))
    return hotspots, model, floods


def _get(params: dict) -> list[dict]:
    url = API + "?" + urllib.parse.urlencode(params, safe=",")
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, list) else [data]


def fetch_forecast(hotspots: list[dict]) -> tuple[list[dict], str]:
    """One call for all hotspots. Returns (one result per hotspot, model name used)."""
    params = {
        "latitude": ",".join(str(h["lat"]) for h in hotspots),
        "longitude": ",".join(str(h["lon"]) for h in hotspots),
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata",
        "past_days": 1,
        "forecast_days": 2,
    }
    wanted = os.environ.get("FORECAST_MODEL", "ecmwf_ifs")
    try:
        return _get({**params, "models": wanted}), wanted
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
    return _get(params), "open-meteo default"


def build_response(hotspots, model, floods, results, model_used, now: datetime | None = None) -> dict:
    now = now or datetime.now(IST)
    out = []
    for h, res in zip(hotspots, results):
        times = [datetime.fromisoformat(t).replace(tzinfo=IST) for t in res["hourly"]["time"]]
        rows = forecast_rows(times, res["hourly"]["precipitation"], now)
        out.append(assess(h, model, rows, floods.get(h["id"], [])))
    return {
        "generated_at": now.isoformat(),
        "forecast_model_used": model_used,
        "lookahead_hours": 24,
        "disclaimer": DISCLAIMER,
        "credit": "Weather data by Open-Meteo.com",
        "hotspots": out,
    }


def get_risk() -> dict:
    hotspots, model, floods = load_data()
    cached = _cache.get("forecast")
    if cached and time.time() - cached["at"] < CACHE_SECONDS:
        results, model_used = cached["results"], cached["model_used"]
    else:
        results, model_used = fetch_forecast(hotspots)
        _cache["forecast"] = {"at": time.time(), "results": results, "model_used": model_used}
    return build_response(hotspots, model, floods, results, model_used)


def lambda_handler(event, context):
    headers = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
               "Cache-Control": "max-age=300"}
    try:
        return {"statusCode": 200, "headers": headers, "body": json.dumps(get_risk())}
    except Exception as e:  # never invent a forecast: say it is unavailable
        print("risk lambda error:", repr(e))  # shows up in CloudWatch Logs
        return {"statusCode": 503, "headers": headers,
                "body": json.dumps({"error": "forecast_unavailable", "disclaimer": DISCLAIMER})}
