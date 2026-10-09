"""Copy the three data files the Lambda needs into backend/risk/data/ (run before every deploy).

    python backend/risk/sync_data.py
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
dest = Path(__file__).resolve().parent / "data"
dest.mkdir(exist_ok=True)
for name in ("hotspots.json", "thresholds.json", "features.csv"):
    shutil.copy(root / "data" / name, dest / name)
    print("copied", name)
