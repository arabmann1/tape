"""SQLite cache: daily prices, company/fund profiles, and small key-value state
(the shared chart view and the watchlist)."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

from .config import DATA_DIR, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume INTEGER,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS blobs (
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  json TEXT NOT NULL,
  PRIMARY KEY (symbol, kind)
);
CREATE TABLE IF NOT EXISTS fetches (
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (symbol, kind)
);
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  json TEXT NOT NULL
);
"""

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _mark_fetched(con, symbol: str, kind: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO fetches (symbol, kind, fetched_at) VALUES (?, ?, ?)",
        (symbol, kind, now_utc().isoformat(timespec="seconds")),
    )


def fetched_at(symbol: str, kind: str) -> datetime | None:
    with connect() as con:
        row = con.execute(
            "SELECT fetched_at FROM fetches WHERE symbol = ? AND kind = ?", (symbol, kind)
        ).fetchone()
    return datetime.fromisoformat(row[0]) if row else None


def save_prices(symbol: str, df: pd.DataFrame) -> None:
    rows = [
        (symbol, ts.strftime("%Y-%m-%d"), *(None if pd.isna(v) else float(v) for v in r[:-1]),
         None if pd.isna(r[-1]) else int(r[-1]))
        for ts, r in zip(df.index, df[PRICE_COLUMNS].itertuples(index=False, name=None))
    ]
    with connect() as con:
        con.execute("DELETE FROM prices WHERE symbol = ?", (symbol,))
        con.executemany("INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        _mark_fetched(con, symbol, "prices")


def load_prices(symbol: str) -> pd.DataFrame | None:
    with connect() as con:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, adj_close, volume FROM prices "
            "WHERE symbol = ? ORDER BY date",
            con, params=(symbol,),
        )
    if df.empty:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date")))
    return df


def save_blob(symbol: str, kind: str, payload: dict) -> None:
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO blobs (symbol, kind, json) VALUES (?, ?, ?)",
            (symbol, kind, json.dumps(payload)),
        )
        _mark_fetched(con, symbol, kind)


def load_blob(symbol: str, kind: str) -> dict | None:
    with connect() as con:
        row = con.execute(
            "SELECT json FROM blobs WHERE symbol = ? AND kind = ?", (symbol, kind)
        ).fetchone()
    return json.loads(row[0]) if row else None


def kv_get(key: str, default=None):
    with connect() as con:
        row = con.execute("SELECT json FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def kv_set(key: str, value) -> None:
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO kv (key, json) VALUES (?, ?)", (key, json.dumps(value)))
