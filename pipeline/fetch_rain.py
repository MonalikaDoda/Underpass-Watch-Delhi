"""Download hourly rainfall for every (hotspot, event date) from Open-Meteo.

Weather data by Open-Meteo.com (https://open-meteo.com/), licensed CC BY 4.0.
Free, no API key for non-commercial use. Uses each hotspot's own coordinates from
data/hotspots.json. Writes data/rain/hourly.csv (hotspot_id, time, precipitation_mm),
times are local (Asia/Kolkata), each value is the total of the preceding hour.

Usage:  python pipeline/fetch_rain.py [--data-dir data]
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import requests

from common import DEFAULT_DATA_DIR, load_events, load_hotspots

API = "https://archive-api.open-meteo.com/v1/archive"
PAD_DAYS_BEFORE = 2
PAD_DAYS_AFTER = 1


def fetch_one(lat: float, lon: float, start: str, end: str, tries: int = 5) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata",
    }
    for attempt in range(tries):
        r = requests.get(API, params=params, timeout=30)
        if r.status_code == 200:
            h = r.json()["hourly"]
            return pd.DataFrame({"time": pd.to_datetime(h["time"]), "precipitation_mm": h["precipitation"]})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"Open-Meteo returned {r.status_code}: {r.text[:200]}")
    raise RuntimeError("Open-Meteo kept failing after retries")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    events = load_events(args.data_dir)
    coords = {h["id"]: (h["lat"], h["lon"]) for h in load_hotspots(args.data_dir)}
    out_path = args.data_dir / "rain" / "hourly.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    have = pd.read_csv(out_path, parse_dates=["time"]) if out_path.exists() else pd.DataFrame(
        columns=["hotspot_id", "time", "precipitation_mm"]
    )
    frames = [have]
    pairs = events[["hotspot_id", "date"]].drop_duplicates().sort_values(["hotspot_id", "date"])
    for hid, date in pairs.itertuples(index=False):
        if hid not in coords or coords[hid][0] is None:
            raise SystemExit(f"No coordinates for hotspot '{hid}' in hotspots.json")
        start = (date - pd.Timedelta(days=PAD_DAYS_BEFORE)).strftime("%Y-%m-%d")
        end = (date + pd.Timedelta(days=PAD_DAYS_AFTER)).strftime("%Y-%m-%d")
        t0 = pd.Timestamp(start)
        already = have[(have.hotspot_id == hid) & (have.time >= t0)]
        if len(already) >= (PAD_DAYS_BEFORE + 1 + PAD_DAYS_AFTER) * 24 and already.time.min() <= t0:
            continue
        lat, lon = coords[hid]
        df = fetch_one(lat, lon, start, end)
        df.insert(0, "hotspot_id", hid)
        frames.append(df)
        print(f"fetched {hid} {start}..{end}")
        time.sleep(0.4)

    all_rain = pd.concat(frames, ignore_index=True).drop_duplicates(["hotspot_id", "time"]).sort_values(
        ["hotspot_id", "time"]
    )
    all_rain.to_csv(out_path, index=False)
    print(f"wrote {len(all_rain)} hourly rows to {out_path}")
    print("Weather data by Open-Meteo.com (CC BY 4.0)")


if __name__ == "__main__":
    main()
