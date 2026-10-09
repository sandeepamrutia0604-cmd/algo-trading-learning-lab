"""Where the app finds its own files and where it keeps yours.

Run from the repo (`python -m uvicorn ...`) everything is relative to the repo, as always. Run as the
Windows download (a PyInstaller build, started by desktop/launcher.py with ALGO_DESKTOP=1) the program's
files sit inside the bundle, and your database goes in a per-user folder, so unzipping a new version or
deleting the app never touches your portfolio.

  ALGO_DESKTOP=1   desktop mode (see config.py): no .env, no broker routes, data in the per-user folder
  ALGO_DATA_DIR    overrides the data folder (handy for testing a build without touching real data)
"""

import os
import sys
from pathlib import Path

APP_FOLDER = "AlgoTradingLab"


def is_desktop() -> bool:
    return os.environ.get("ALGO_DESKTOP", "").strip().lower() in {"1", "true", "yes"}


def resource_dir() -> Path:
    """The folder that holds `frontend/`: the PyInstaller bundle when frozen, else the repo root."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Where the database (and the log) live."""
    given = os.environ.get("ALGO_DATA_DIR")
    if given:
        return Path(given)
    if is_desktop():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_FOLDER
    return Path("data")
