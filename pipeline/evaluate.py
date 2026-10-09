"""Leave-one-storm-out evaluation.

For each storm day, thresholds are fitted on all OTHER storm days and then used to
predict that day's rows. The unit that matters statistically is the storm day, not
the row: rows on the same day share the same weather.

Also reports a pooled-only baseline (one threshold for every hotspot) for comparison.
Only counts that were actually measured are reported. Lead time is not computed here
(it needs archived forecasts and exact-time records).

Usage:  python pipeline/evaluate.py [--data-dir data]
Writes: data/loso_predictions.csv, data/metrics.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from common import DEFAULT_DATA_DIR, compute_features, fit_thresholds, load_events, load_rain, risk


def confusion(df: pd.DataFrame, col: str) -> dict:
    flooded = df.outcome == "flooded"
    flagged = df[col]
    return {
        "floods_caught": int((flooded & flagged).sum()),
        "floods_missed": int((flooded & ~flagged).sum()),
        "false_alarms": int((~flooded & flagged).sum()),
        "correct_clear": int((~flooded & ~flagged).sum()),
        "n_flooded_rows": int(flooded.sum()),
        "n_clear_rows": int((~flooded).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    events = load_events(args.data_dir)
    rain = load_rain(args.data_dir)
    feats = compute_features(events, rain)

    preds = []
    for day in sorted(feats.date.unique()):
        train = feats[feats.date != day]
        test = feats[feats.date == day]
        model = fit_thresholds(train)
        pooled_only = {"pooled": model["pooled"], "hotspots": {}}
        for r in test.itertuples():
            own = risk(model, r.hotspot_id, r.rain1h_mm, r.rain3h_mm)
            base = risk(pooled_only, r.hotspot_id, r.rain1h_mm, r.rain3h_mm)
            preds.append(
                {
                    "event_id": r.event_id,
                    "date": day,
                    "hotspot_id": r.hotspot_id,
                    "outcome": r.outcome,
                    "time_confidence": r.time_confidence,
                    "rain1h_mm": r.rain1h_mm,
                    "rain3h_mm": r.rain3h_mm,
                    "ratio_to_threshold": own["ratio"],
                    "tier": own["tier"],
                    "flagged": own["flagged"],
                    "used_own_threshold": own["own_threshold"],
                    "flagged_pooled_only": base["flagged"],
                }
            )
    pdf = pd.DataFrame(preds)
    pdf.to_csv(args.data_dir / "loso_predictions.csv", index=False)

    per_day = []
    for day, g in pdf.groupby("date"):
        c = confusion(g, "flagged")
        per_day.append({"date": str(day.date()), **c})

    metrics = {
        "n_rows": int(len(pdf)),
        "n_storm_days": int(pdf.date.nunique()),
        "per_hotspot_thresholds": confusion(pdf, "flagged"),
        "pooled_only_baseline": confusion(pdf, "flagged_pooled_only"),
        "per_storm_day": per_day,
        "notes": [
            "Leave-one-storm-out: thresholds for each day come from the other days only.",
            "Rows on one storm day share the same weather; the effective sample is the number of storm days.",
            "Counts only; with this few clear rows a false-alarm rate would not be reliable.",
            "Rain is a coarse, city-wide signal; differences between hotspots come from flood history.",
        ],
    }
    (args.data_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    for name in ("per_hotspot_thresholds", "pooled_only_baseline"):
        m = metrics[name]
        print(
            f"{name:24s} floods caught {m['floods_caught']}/{m['n_flooded_rows']}, "
            f"missed {m['floods_missed']}, false alarms {m['false_alarms']}/{m['n_clear_rows']} clear rows"
        )
    print(f"{metrics['n_rows']} rows over {metrics['n_storm_days']} storm days")
    for n in metrics["notes"]:
        print("-", n)


if __name__ == "__main__":
    main()
