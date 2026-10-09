"""Turn a rain forecast into a risk colour for one underpass.

Pure functions only: no internet, no AWS. That makes them easy to test.

How it works (same idea as the pipeline):
  1. From the hourly forecast take the heaviest single hour (1h) and the heaviest
     3-hour total (3h) over the next 24 hours.
  2. Compare each with this underpass's rain limit (learned from its recorded floods).
  3. ratio = the larger of (forecast 1h / limit 1h) and (forecast 3h / limit 3h).
  4. Colour: ratio >= 1.0 red, >= 0.8 orange, >= 0.5 yellow, otherwise green.

Open-Meteo labels each hourly value with the END of the hour it covers
(the value at 14:00 is the rain between 13:00 and 14:00).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
# keep identical to TIERS in pipeline/common.py (test_risk_core.py checks this)
TIERS = [(1.0, "red"), (0.8, "orange"), (0.5, "yellow")]
DISCLAIMER = "Prototype. Estimated risk, not an official warning."
LOOKAHEAD_HOURS = 24


def tier_for(ratio: float) -> str:
    for cut, name in TIERS:
        if ratio >= cut:
            return name
    return "green"


def _ok(x) -> bool:
    """A usable limit: a positive, finite number."""
    return x is not None and isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x) and x > 0


def rolling_sum(values: list, n: int) -> list:
    out = []
    for i in range(len(values)):
        if i + 1 < n:
            out.append(None)
            continue
        window = values[i + 1 - n : i + 1]
        out.append(None if any(v is None for v in window) else sum(window))
    return out


def forecast_rows(times: list[datetime], precip: list, now: datetime, lookahead: int = LOOKAHEAD_HOURS):
    """(time, rain in that hour, rain in the 3 hours up to it) for hours from now to now+lookahead."""
    r1 = [None if v is None else float(v) for v in precip]
    r3 = rolling_sum(r1, 3)
    end = now + timedelta(hours=lookahead)
    return [(t, a, b) for t, a, b in zip(times, r1, r3) if now < t <= end]


def limits_for(hotspot_id: str, model: dict) -> dict:
    h = model.get("hotspots", {}).get(hotspot_id)
    if h:
        return {
            "rain1h_mm": h.get("rain1h_mm"),
            "rain3h_mm": h.get("rain3h_mm"),
            "own_threshold": bool(h.get("own_threshold")),
            "evidence": h.get("evidence", ""),
            "n_floods": int(h.get("n_floods", 0)),
            "n_clear": int(h.get("n_clear", 0)),
        }
    p = model["pooled"]
    return {
        "rain1h_mm": p.get("rain1h_mm"),
        "rain3h_mm": p.get("rain3h_mm"),
        "own_threshold": False,
        "evidence": "limited evidence (no recorded floods here; pooled limit used)",
        "n_floods": 0,
        "n_clear": 0,
    }


def _r(x):
    return None if x is None else round(float(x), 1)


def assess(hotspot: dict, model: dict, rows: list, flood_rain3h: list[float]) -> dict:
    """Risk for one hotspot. `rows` come from forecast_rows(); `flood_rain3h` are the 3h rain
    values of this hotspot's recorded floods (from data/features.csv)."""
    lim = limits_for(hotspot["id"], model)
    l1, l3 = lim["rain1h_mm"], lim["rain3h_mm"]
    base = {
        "id": hotspot["id"],
        "name": hotspot["name"],
        "lat": hotspot["lat"],
        "lon": hotspot["lon"],
        "limit": {"rain1h_mm": _r(l1) if _ok(l1) else None, "rain3h_mm": _r(l3) if _ok(l3) else None},
        "limit_is_own": lim["own_threshold"],
        "evidence": lim["evidence"],
        "note": DISCLAIMER,
    }

    v1 = [a for _, a, _ in rows if a is not None]
    v3 = [b for _, _, b in rows if b is not None]
    if not v1:
        return {**base, "tier": "unknown", "ratio": None,
                "forecast": {"max_1h_mm": None, "max_3h_mm": None, "window_start": None, "window_end": None},
                "history": None, "why": "Forecast is not available for this spot right now."}

    max1, max3 = max(v1), (max(v3) if v3 else max(v1))
    ratios = []
    if _ok(l1):
        ratios.append(max1 / l1)
    if _ok(l3):
        ratios.append(max3 / l3)
    ratio = max(ratios) if ratios else 0.0
    tier = tier_for(ratio)

    flagged = [
        t for t, a, b in rows
        if (_ok(l1) and a is not None and a >= l1) or (_ok(l3) and b is not None and b >= l3)
    ]
    window_start = flagged[0].isoformat() if flagged else None
    window_end = flagged[-1].isoformat() if flagged else None

    limit_text = f"about {_r(l3)} mm in 3 h" if _ok(l3) else "not known"
    fc_text = f"up to {_r(max3)} mm in 3 h, heaviest hour {_r(max1)} mm"
    history = None
    if tier == "green":
        why = f"Forecast rain for the next 24 h ({fc_text}) is well below this spot's limit ({limit_text})."
    else:
        close = {"yellow": "getting closer to", "orange": "close to", "red": "at or above"}[tier]
        why = f"Forecast rain {fc_text} is {close} this spot's limit ({limit_text})."
        if flood_rain3h:
            k = sum(1 for x in flood_rain3h if x >= max3)
            history = {"recorded_floods": len(flood_rain3h), "floods_with_at_least_this_rain_3h": k}
            why += f" {k} of {len(flood_rain3h)} recorded floods here had at least this much rain in 3 h."
        if window_start:
            why += " Estimated risk window is based on when forecast rain reaches the limit."
    why += f" Evidence: {lim['evidence']}."

    return {**base, "tier": tier, "ratio": round(ratio, 2),
            "forecast": {"max_1h_mm": _r(max1), "max_3h_mm": _r(max3),
                         "window_start": window_start, "window_end": window_end},
            "history": history, "why": why}
