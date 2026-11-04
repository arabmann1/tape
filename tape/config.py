"""Paths, ports and tunables. Each can be overridden with an environment variable."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "frontend" / "dist"


def _user_data_home() -> Path:
    if os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


# The cache lives outside OneDrive on purpose: a live SQLite file inside a
# synced folder gets locked and conflict-copied by the sync client.
DATA_DIR = Path(os.environ.get("TAPE_DATA_DIR", _user_data_home() / "tape"))
DB_PATH = DATA_DIR / "tape.db"

HOST = "127.0.0.1"
PORT = int(os.environ.get("TAPE_PORT", "8740"))
API_BASE = f"http://{HOST}:{PORT}"

BENCHMARK = "SPY"          # the S&P 500 stand-in every return is compared against
HISTORY_PERIOD = "10y"     # how much daily history to keep per ticker
PRICE_TTL_HOURS = 4        # refetch prices after this long
PROFILE_TTL_HOURS = 24     # refetch fundamentals / fund data after this long
