"""Market data from Yahoo Finance (via yfinance), cached in SQLite.

yfinance is unofficial: Yahoo changes fields and rate-limits without notice.
Every fetch falls back to the cached copy rather than failing, and callers get
the fetch time so stale data is visible instead of silent.
"""

import contextlib
import logging
import math
import re
import sys
import warnings
from datetime import timedelta

import pandas as pd
import yfinance as yf

from . import cache
from .config import HISTORY_PERIOD, PRICE_TTL_HOURS, PROFILE_TTL_HOURS

log = logging.getLogger(__name__)

# yfinance trips pandas 3 deprecation warnings on every call; they're noise here.
warnings.filterwarnings("ignore", module="yfinance")

_TICKER = re.compile(r"^[A-Z][A-Z0-9-]{0,9}$")


class DataError(Exception):
    """Raised when a ticker has no usable data, cached or fresh."""


def normalize(symbol: str) -> str:
    """'brk.b ' -> 'BRK-B' (Yahoo's spelling for share classes)."""
    s = (symbol or "").strip().upper().replace(".", "-").lstrip("$")
    if not _TICKER.match(s):
        raise DataError(f"'{symbol}' doesn't look like a US ticker")
    return s


@contextlib.contextmanager
def _quiet():
    # yfinance occasionally prints; stdout must stay clean for the MCP stdio transport.
    with contextlib.redirect_stdout(sys.stderr):
        yield


def _is_fresh(symbol: str, kind: str, ttl_hours: float) -> bool:
    ts = cache.fetched_at(symbol, kind)
    return ts is not None and cache.now_utc() - ts < timedelta(hours=ttl_hours)


def fetched_at(symbol: str, kind: str = "prices") -> str | None:
    ts = cache.fetched_at(normalize(symbol), kind)
    return ts.isoformat(timespec="minutes") if ts else None


# ---------------------------------------------------------------- prices

def _clean_history(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Adj Close": "adj_close", "Volume": "volume",
    })
    if "adj_close" not in df:
        df["adj_close"] = df["close"]
    df = df[cache.PRICE_COLUMNS].dropna(subset=["close"])
    idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
    df.index = pd.DatetimeIndex(idx).normalize()
    return df[~df.index.duplicated(keep="last")].sort_index()


def get_prices(symbol: str, force: bool = False) -> pd.DataFrame:
    """Daily OHLCV for up to HISTORY_PERIOD. `close` is split-adjusted (what charts
    show); `adj_close` also folds in dividends (what returns are measured on)."""
    symbol = normalize(symbol)
    if not force and _is_fresh(symbol, "prices", PRICE_TTL_HOURS):
        df = cache.load_prices(symbol)
        if df is not None:
            return df
    try:
        with _quiet():
            raw = yf.Ticker(symbol).history(
                period=HISTORY_PERIOD, interval="1d", auto_adjust=False, actions=False
            )
        if raw is not None and len(raw) > 0:
            df = _clean_history(raw)
            cache.save_prices(symbol, df)
            return df
    except Exception as e:  # network, rate limit, Yahoo schema change
        log.warning("price fetch failed for %s: %s", symbol, e)
    df = cache.load_prices(symbol)
    if df is not None:
        log.warning("serving cached prices for %s", symbol)
        return df
    raise DataError(
        f"No price data for {symbol}. Check the ticker; if it's right, Yahoo may be "
        "rate-limiting, so try again in a minute."
    )


# ---------------------------------------------------------------- profile

def _num(v):
    """Yahoo returns NaN, 'Infinity' and strings in numeric fields; keep real numbers only."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and not math.isfinite(v)) else v
    return None


def _plain(info: dict) -> dict:
    out = {}
    for k, v in info.items():
        if isinstance(v, str):
            out[k] = v
        elif _num(v) is not None:
            out[k] = v
    return out


def _statement_row(df: pd.DataFrame | None, *names: str) -> dict:
    """One line of a financial statement as {fiscal-year-end: value}, oldest first."""
    if df is None or df.empty:
        return {}
    for name in names:
        if name in df.index:
            s = df.loc[name].dropna()
            pairs = sorted((pd.Timestamp(k).strftime("%Y-%m-%d"), float(v)) for k, v in s.items())
            return dict(pairs)
    return {}


def _financials(t: yf.Ticker) -> dict:
    out = {}
    try:
        inc = t.income_stmt
        out["revenue"] = _statement_row(inc, "Total Revenue", "Operating Revenue")
        out["operating_income"] = _statement_row(inc, "Operating Income")
        out["net_income"] = _statement_row(inc, "Net Income", "Net Income Common Stockholders")
    except Exception as e:
        log.warning("income statement unavailable: %s", e)
    try:
        out["free_cash_flow"] = _statement_row(t.cashflow, "Free Cash Flow")
    except Exception as e:
        log.warning("cash flow unavailable: %s", e)
    # Yahoo's summary `freeCashflow` field is a "levered" estimate that can be far
    # off the filings (NVDA: $42B vs $127B), so sum the last four reported quarters.
    try:
        quarters = list(_statement_row(t.quarterly_cashflow, "Free Cash Flow").values())
        if len(quarters) >= 4:
            out["fcf_ttm"] = sum(quarters[-4:])
    except Exception as e:
        log.warning("quarterly cash flow unavailable: %s", e)
    return out


def _next_earnings(t: yf.Ticker) -> list[str]:
    try:
        cal = t.calendar or {}
        dates = cal.get("Earnings Date") or []
        return [d.isoformat() for d in dates if hasattr(d, "isoformat")]
    except Exception as e:
        log.warning("calendar unavailable: %s", e)
        return []


def _dividends_ttm(t: yf.Ticker) -> float | None:
    try:
        d = t.dividends
        if d is None or d.empty:
            return 0.0
        idx = d.index.tz_localize(None) if d.index.tz is not None else d.index
        d = pd.Series(d.to_numpy(), index=idx)
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=365)
        return float(d[d.index > cutoff].sum())
    except Exception as e:
        log.warning("dividends unavailable: %s", e)
        return None


def _fund(t: yf.Ticker) -> dict:
    try:
        fd = t.funds_data
        top = fd.top_holdings
        holdings = [
            {"symbol": str(sym), "name": str(row["Name"]), "weight": float(row["Holding Percent"])}
            for sym, row in top.iterrows()
        ]
        return {"overview": dict(fd.fund_overview or {}), "top_holdings": holdings}
    except Exception as e:
        log.warning("fund data unavailable: %s", e)
        return {}


# Bump when the profile payload's shape changes, so cached copies refetch.
PROFILE_VERSION = 2


def get_profile(symbol: str, force: bool = False) -> dict:
    """Company or fund profile: Yahoo's summary fields plus annual statements,
    upcoming earnings, trailing dividends and (for ETFs) top holdings."""
    symbol = normalize(symbol)
    if not force and _is_fresh(symbol, "profile", PROFILE_TTL_HOURS):
        cached = cache.load_blob(symbol, "profile")
        if cached is not None and cached.get("v") == PROFILE_VERSION:
            return cached
    try:
        with _quiet():
            t = yf.Ticker(symbol)
            info = _plain(t.info or {})
            is_etf = info.get("quoteType") == "ETF"
            payload = {
                "v": PROFILE_VERSION,
                "info": info,
                "financials": {} if is_etf else _financials(t),
                "earnings_dates": [] if is_etf else _next_earnings(t),
                "dividends_ttm": _dividends_ttm(t),
                "fund": _fund(t) if is_etf else {},
            }
        if info:
            cache.save_blob(symbol, "profile", payload)
            return payload
    except Exception as e:
        log.warning("profile fetch failed for %s: %s", symbol, e)
    cached = cache.load_blob(symbol, "profile")
    if cached is not None:
        return cached
    return {"info": {}, "financials": {}, "earnings_dates": [], "dividends_ttm": None, "fund": {}}
