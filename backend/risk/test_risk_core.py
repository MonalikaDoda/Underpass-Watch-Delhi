"""Tests for the forecast -> risk logic. Run:  python -m unittest backend/risk/test_risk_core.py -v
(no internet needed; the forecast is made up inside the test)"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk_core import IST, TIERS, assess, forecast_rows, rolling_sum, tier_for  # noqa: E402

MODEL = {
    "pooled": {"rain1h_mm": 2.2, "rain3h_mm": 4.4},
    "hotspots": {
        "minto_bridge": {"rain1h_mm": 3.5, "rain3h_mm": 6.3, "own_threshold": True, "n_floods": 5,
                         "n_clear": 3, "evidence": "based on 5 recorded floods"},
    },
}
MINTO = {"id": "minto_bridge", "name": "Minto Bridge", "lat": 28.636, "lon": 77.226}
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=IST)


def series(hour_values: dict[int, float], hours=48):
    """Hourly forecast from 09:00 today; hour_values maps clock hour -> mm in the hour ending then."""
    t0 = datetime(2026, 10, 9, 9, 0, tzinfo=IST)
    times = [t0 + timedelta(hours=i) for i in range(hours)]
    return times, [hour_values.get(t.hour, 0.0) if t.day == 9 else 0.0 for t in times]


class RiskTests(unittest.TestCase):
    def test_rolling_sum(self):
        self.assertEqual(rolling_sum([1, 2, 3, 4], 3), [None, None, 6, 9])
        self.assertEqual(rolling_sum([1, None, 3, 4], 3), [None, None, None, None])

    def test_red_with_window(self):
        times, p = series({14: 10, 15: 15, 16: 20, 17: 10})
        r = assess(MINTO, MODEL, forecast_rows(times, p, NOW), [6.3, 7.3, 14.1, 137.4, 6.3])
        self.assertEqual(r["tier"], "red")
        self.assertEqual(r["forecast"]["max_3h_mm"], 45.0)
        self.assertEqual(r["forecast"]["max_1h_mm"], 20.0)
        self.assertTrue(r["forecast"]["window_start"].startswith("2026-10-09T14:00"))
        self.assertEqual(r["history"], {"recorded_floods": 5, "floods_with_at_least_this_rain_3h": 1})

    def test_yellow_and_green(self):
        times, p = series({15: 2.0})
        self.assertEqual(assess(MINTO, MODEL, forecast_rows(times, p, NOW), [])["tier"], "yellow")
        times, p = series({})
        r = assess(MINTO, MODEL, forecast_rows(times, p, NOW), [])
        self.assertEqual((r["tier"], r["forecast"]["window_start"]), ("green", None))

    def test_past_rain_is_ignored_but_counts_toward_3h(self):
        times, p = series({10: 50})  # heavy rain this morning, already over
        self.assertEqual(assess(MINTO, MODEL, forecast_rows(times, p, NOW), [])["tier"], "green")
        times, p = series({11: 5, 12: 5, 13: 5})  # 11:00 and 12:00 are past, 13:00 is next hour
        r = assess(MINTO, MODEL, forecast_rows(times, p, NOW), [])
        self.assertEqual(r["forecast"]["max_3h_mm"], 15.0)

    def test_unknown_spot_uses_pooled_limit(self):
        other = {"id": "new_place", "name": "New place", "lat": 28.6, "lon": 77.2}
        times, p = series({14: 3.0})
        r = assess(other, MODEL, forecast_rows(times, p, NOW), [])
        self.assertEqual(r["tier"], "red")  # 3.0 mm in an hour vs pooled limit 2.2 -> ratio 1.36
        self.assertIn("limited evidence", r["evidence"])

    def test_missing_forecast(self):
        r = assess(MINTO, MODEL, [], [])
        self.assertEqual(r["tier"], "unknown")

    def test_tiers_match_pipeline(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "pipeline"))
        try:
            import common
        except ImportError:  # pandas missing on this machine
            self.skipTest("pipeline/common.py needs pandas")
        self.assertEqual(TIERS, common.TIERS)
        m = {"pooled": {"rain1h_mm": 10.0, "rain3h_mm": 10.0}, "hotspots": {}}
        for x in (0, 3, 5, 7.9, 8, 9.9, 10, 25):
            self.assertEqual(tier_for(x / 10), common.risk(m, "x", x, 0)["tier"])


if __name__ == "__main__":
    unittest.main()
