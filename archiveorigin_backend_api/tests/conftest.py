import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

paths = [str(APP_DIR), str(ROOT)]
for p in paths:
    if p not in sys.path:
        sys.path.insert(0, p)
