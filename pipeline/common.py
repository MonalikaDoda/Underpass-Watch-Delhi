"""Shared helpers for the rainfall + threshold pipeline.

Design (kept deliberately simple and explainable, no LLM in the core):
  * For every (hotspot, event date) we look at hourly rain in a 36 h local-time window
    (12:00 the day before the event date to 24:00 on it) and take two numbers:
    the strongest single hour (1h burst) and the strongest 3-hour total (3h accumulation).
  * A hotspot's threshold is the lowest rain it was ever recorded flooding at, per window,
    once it has enough recorded floods. Otherwise a pooled threshold (a low quantile of all
    flooded events) is used and labelled "limited evidence".
  * Risk compares rain to the threshold; a flood is predicted when either window reaches it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

WINDOW_START_OFFSET_H = -12  # hours relative to 00:00 on the event date
WINDOW_END_OFFSET_H = 24
MIN_HOURS_IN_WINDOW = 30  # skip an event if fewer hourly values than this are available

MIN_FLOODS_FOR_OWN_THRESHOLD = 3
POOLED_QUANTILE = 0.25

# ratio of rain to threshold -> tier (checked in order); below the last cut-off is green
TIERS = [(1.0, "red"), (0.8, "orange"), (0.5, "yellow")]


def load_events(data_dir: Path) -> pd.DataFrame:
    ev = pd.read_csv(data_dir / "events.csv", parse_dates=["date"])
    bad = set(ev["outcome"]) - {"flooded", "clear"}
    if bad:
        raise ValueError(f"unexpected outcome values: {bad}")
    return ev


def load_hotspots(data_dir: Path) -> list[dict]:
    return json.loads((data_dir / "hotspots.json").read_text(encoding="utf-8"))["hotspots"]


def load_rain(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "rain" / "hourly.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run pipeline/fetch_rain.py first.")
    rain = pd.read_csv(path, parse_dates=["time"])
    return rain


def compute_features(events: pd.DataFrame, rain: pd.DataFrame) -> pd.DataFrame:
    rows = []
    skipped = []
    for ev in events.itertuples():
        start = ev.date + pd.Timedelta(hours=WINDOW_START_OFFSET_H)
        end = ev.date + pd.Timedelta(hours=WINDOW_END_OFFSET_H)
        s = rain[(rain.hotspot_id == ev.hotspot_id) & (rain.time >= start) & (rain.time < end)]
        s = s.drop_duplicates("time").set_index("time")["precipitation_mm"].sort_index().asfreq("h")
        if s.notna().sum() < MIN_HOURS_IN_WINDOW:
            skipped.append(ev.event_id)
            continue
        r3 = s.rolling(3, min_periods=3).sum()
        rows.append(
            {
                "event_id": ev.event_id,
                "date": ev.date,
                "hotspot_id": ev.hotspot_id,
                "outcome": ev.outcome,
                "time_confidence": ev.time_confidence,
                "rain1h_mm": round(float(s.max()), 2),
                "rain3h_mm": round(float(r3.max()), 2),
                "peak3h_end": r3.idxmax(),
            }
        )
    if skipped:
        print(f"WARNING: no usable rainfall for events {skipped}; they are left out.")
    return pd.DataFrame(rows)


def _finite(x: float):
    return None if (x is None or math.isinf(x) or math.isnan(x)) else x


def fit_thresholds(train: pd.DataFrame) -> dict:
    floods = train[train.outcome == "flooded"]
    pooled = {
        "rain1h_mm": float(floods.rain1h_mm.quantile(POOLED_QUANTILE)) if len(floods) else math.inf,
        "rain3h_mm": float(floods.rain3h_mm.quantile(POOLED_QUANTILE)) if len(floods) else math.inf,
    }
    hotspots = {}
    for hid, g in train.groupby("hotspot_id"):
        f = g[g.outcome == "flooded"]
        c = g[g.outcome == "clear"]
        own = len(f) >= MIN_FLOODS_FOR_OWN_THRESHOLD
        t1 = float(f.rain1h_mm.min()) if own else pooled["rain1h_mm"]
        t3 = float(f.rain3h_mm.min()) if own else pooled["rain3h_mm"]
        hotspots[hid] = {
            "rain1h_mm": t1,
            "rain3h_mm": t3,
            "own_threshold": own,
            "n_floods": int(len(f)),
            "n_clear": int(len(c)),
            "clear_days_at_or_above_threshold": int(((c.rain1h_mm >= t1) | (c.rain3h_mm >= t3)).sum()),
            "evidence": (
                f"based on {len(f)} recorded floods"
                if own
                else f"limited evidence ({len(f)} recorded floods here; pooled threshold used)"
            ),
        }
    return {"pooled": pooled, "hotspots": hotspots}


def thresholds_for(model: dict, hid: str) -> tuple[float, float, bool]:
    h = model["hotspots"].get(hid)
    if h is None:
        return model["pooled"]["rain1h_mm"], model["pooled"]["rain3h_mm"], False
    return h["rain1h_mm"], h["rain3h_mm"], h["own_threshold"]


def risk(model: dict, hid: str, rain1h: float, rain3h: float) -> dict:
    t1, t3, own = thresholds_for(model, hid)
    ratios = []
    for value, t in ((rain1h, t1), (rain3h, t3)):
        if t is not None and not math.isinf(t) and t > 0:
            ratios.append(value / t)
    ratio = max(ratios) if ratios else 0.0
    tier = "green"
    for cut, name in TIERS:
        if ratio >= cut:
            tier = name
            break
    return {"ratio": round(ratio, 3), "tier": tier, "flagged": ratio >= 1.0, "own_threshold": own}


def model_to_jsonable(model: dict) -> dict:
    return {
        "pooled": {k: _finite(v) for k, v in model["pooled"].items()},
        "hotspots": {
            hid: {k: (_finite(v) if isinstance(v, float) else v) for k, v in h.items()}
            for hid, h in model["hotspots"].items()
        },
        "settings": {
            "window_hours": [WINDOW_START_OFFSET_H, WINDOW_END_OFFSET_H],
            "min_floods_for_own_threshold": MIN_FLOODS_FOR_OWN_THRESHOLD,
            "pooled_quantile": POOLED_QUANTILE,
            "tiers": TIERS,
        },
    }
