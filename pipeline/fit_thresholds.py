"""Compute rain features per event and fit per-hotspot thresholds on ALL rows.

This is the model the app uses. Honest accuracy numbers come from evaluate.py
(leave-one-storm-out), not from this fit.

Usage:  python pipeline/fit_thresholds.py [--data-dir data]
Writes: data/features.csv, data/thresholds.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    DEFAULT_DATA_DIR,
    compute_features,
    fit_thresholds,
    load_events,
    load_rain,
    model_to_jsonable,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    events = load_events(args.data_dir)
    rain = load_rain(args.data_dir)
    feats = compute_features(events, rain)
    feats.to_csv(args.data_dir / "features.csv", index=False)

    model = fit_thresholds(feats)
    (args.data_dir / "thresholds.json").write_text(
        json.dumps(model_to_jsonable(model), indent=2), encoding="utf-8"
    )

    print(f"{len(feats)} events with rainfall, {feats.date.nunique()} storm days")
    p = model["pooled"]
    print(f"pooled threshold: {p['rain1h_mm']:.1f} mm/1h, {p['rain3h_mm']:.1f} mm/3h")
    print(f"{'hotspot':20s} {'1h mm':>7s} {'3h mm':>7s}  floods clear clear>=thr  evidence")
    for hid, h in sorted(model["hotspots"].items()):
        print(
            f"{hid:20s} {h['rain1h_mm']:7.1f} {h['rain3h_mm']:7.1f}  {h['n_floods']:6d} {h['n_clear']:5d} "
            f"{h['clear_days_at_or_above_threshold']:9d}  {h['evidence']}"
        )


if __name__ == "__main__":
    main()
