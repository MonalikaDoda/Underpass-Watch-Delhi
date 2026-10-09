"""Show how much it rained on each day around a date, for one underpass.

Use it to check a date in your sheet: did it really rain heavily that day?

  python pipeline/check_daily.py                       (checks Zakhira, 28 Jun - 1 Jul 2022)
  python pipeline/check_daily.py minto_bridge 2024-06-26 2024-06-29
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

hotspot = sys.argv[1] if len(sys.argv) > 1 else "zakhira"
start = sys.argv[2] if len(sys.argv) > 2 else "2022-06-28"
end = sys.argv[3] if len(sys.argv) > 3 else "2022-07-01"

path = Path(__file__).resolve().parent.parent / "data" / "rain" / "hourly.csv"
rain = pd.read_csv(path, parse_dates=["time"])
rain = rain[(rain.hotspot_id == hotspot) & (rain.time >= start) & (rain.time < pd.Timestamp(end) + pd.Timedelta(days=1))]
if rain.empty:
    sys.exit(f"No rain data for {hotspot} between {start} and {end}. Run fetch_rain.py first, or pick other dates.")

rain = rain.assign(day=rain.time.dt.date)
table = rain.groupby("day").precipitation_mm.agg(total_mm="sum", heaviest_hour_mm="max").round(1)
print(f"Rain at {hotspot} (Open-Meteo):")
print(table.to_string())
