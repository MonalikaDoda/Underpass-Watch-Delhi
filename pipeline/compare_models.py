"""Which Open-Meteo rain data best matches what newspapers reported?

We can't tell flood from no-flood if the downloaded rain is wrong. So we test
the rain data against an independent number: the rain the articles quoted for each
big storm (24-hour totals at Delhi's main weather station). We pick the rain data
by how well it matches those reports, NOT by how well it predicts floods.

Run:   python pipeline/compare_models.py
Then paste the whole output back to Claude.
Needs internet. Takes about a minute.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

API = "https://archive-api.open-meteo.com/v1/archive"
LAT, LON = 28.585, 77.205  # central Delhi, near the Safdarjung weather station

# (centre date in the sheet, rain the article quoted)
STORMS = [
    ("2024-06-28", "228.1 mm in 24h"),
    ("2023-07-09", "153.0 mm in 24h"),
    ("2022-06-30", "117.0 mm in 24h  <-- date in sheet is under question"),
    ("2021-09-01", "112.1 mm in 24h"),
    ("2024-07-31", "107.6 mm (evening)"),
    ("2020-07-19", "74.8 mm"),
    ("2025-08-14", "58 mm in 24h"),
]
MODELS = [None, "era5", "era5_land", "ecmwf_ifs"]  # None = Open-Meteo's default mix


def get_hourly(centre: str, model: str | None):
    c = pd.Timestamp(centre)
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": (c - pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        "end_date": (c + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata",
    }
    if model:
        params["models"] = model
    for attempt in range(4):
        r = requests.get(API, params=params, timeout=30)
        if r.status_code == 200:
            h = r.json()["hourly"]
            return pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]), dtype="float")
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return None  # e.g. this model is not available for these dates
    return None


def main() -> None:
    for centre, quoted in STORMS:
        print(f"\n=== {centre}   article said: {quoted}")
        for model in MODELS:
            name = model or "default"
            s = get_hourly(centre, model)
            if s is None or s.isna().all():
                print(f"  {name:10s} not available")
                continue
            daily = s.groupby(s.index.day).sum().round(0).astype(int)
            days = "  ".join(f"{d:02d}:{v}" for d, v in daily.items())
            best24 = s.rolling(24, min_periods=24).sum().max()
            print(f"  {name:10s} biggest 24h = {best24:6.1f} mm | rain per day (day:mm)  {days}")
            time.sleep(0.4)
    print("\nWeather data by Open-Meteo.com (CC BY 4.0)")


if __name__ == "__main__":
    main()
