"""Return and risk statistics on dividend-adjusted closes. Pure functions, no I/O."""

import numpy as np
import pandas as pd

TRADING_DAYS = 252
PERIODS = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260}


def period_return(adj: pd.Series, days: int) -> float | None:
    if len(adj) <= days:
        return None
    return float(adj.iloc[-1] / adj.iloc[-1 - days] - 1)


def annualize(total: float | None, years: float) -> float | None:
    if total is None or total <= -1:
        return None
    return float((1 + total) ** (1 / years) - 1)


def volatility(adj: pd.Series, days: int = TRADING_DAYS) -> float | None:
    """Annualized standard deviation of daily returns."""
    r = adj.pct_change().dropna().tail(days)
    if len(r) < 20:
        return None
    return float(r.std() * np.sqrt(TRADING_DAYS))


def max_drawdown(adj: pd.Series, days: int | None = None) -> dict | None:
    """Worst peak-to-trough fall, with when it started, bottomed and recovered."""
    s = adj if days is None else adj.tail(days)
    if len(s) < 2:
        return None
    dd = s / s.cummax() - 1
    trough = dd.idxmin()
    peak = s.loc[:trough].idxmax()
    after = s.loc[trough:]
    back = after[after >= s.loc[peak]]
    return {
        "drawdown": float(dd.min()),
        "peak": peak.strftime("%Y-%m-%d"),
        "trough": trough.strftime("%Y-%m-%d"),
        "recovered": back.index[0].strftime("%Y-%m-%d") if len(back) else None,
    }


def beta_and_correlation(adj: pd.Series, bench: pd.Series, days: int = TRADING_DAYS):
    """Beta (how much it moves per 1% market move) and correlation, on daily returns."""
    r = pd.concat([adj.pct_change(), bench.pct_change()], axis=1, join="inner").dropna().tail(days)
    if len(r) < 60:
        return None, None
    cov = r.cov().iloc[0, 1]
    var = r.iloc[:, 1].var()
    return float(cov / var), float(r.corr().iloc[0, 1])
