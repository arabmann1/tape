"""The tools an AI analyst gets: the same data, lenses and chart controls the
dashboard has.

The in-app chat (ai/) and the MCP server (mcp_server.py) both build on these, so
each tool's arguments and description live in one place. Analysis tools run
in-process. Chart tools call `command`, which each caller wires to the running
dashboard, and `chart_state` reads what's on screen the same way.
"""

from typing import Callable, Literal

from . import data, glossary, lenses

Timeframe = Literal["3M", "6M", "1Y", "2Y", "5Y", "10Y"]
Indicator = Literal["volume", "sma20", "sma50", "sma200", "ema20", "bollinger", "levels", "rsi", "macd"]
Tone = Literal["info", "bull", "bear", "warn"]


def _safe(fn, *args):
    try:
        return fn(*args)
    except (data.DataError, ValueError) as e:
        return {"error": str(e)}


def build(command: Callable[[dict], dict], read_state: Callable[[], dict]) -> list[Callable]:
    # ------------------------------------------------------------ analysis

    def overview(symbol: str) -> dict:
        """Snapshot of a US stock or ETF: name, price, 1-day change, 52-week range,
        sector or fund category, size, and the business description."""
        return _safe(lenses.overview, symbol)

    def investor_view(symbol: str) -> dict:
        """LONG-TERM lens (months to years). Stocks: growth, profitability, cash and
        debt, valuation vs the S&P 500, track record, risk, dividends. ETFs: category,
        cost, size, concentration, holdings, track record, risk. Every metric has a
        plain-English reading. Reason about it independently of trader_view."""
        return _safe(lenses.investor_view, symbol)

    def trader_view(symbol: str) -> dict:
        """SHORT-TERM lens (days to weeks): trend vs moving averages, RSI, MACD,
        relative strength, ATR, Bollinger Bands, volume, 52-week range, support and
        resistance levels, and the next earnings date. Reason about it independently
        of investor_view."""
        return _safe(lenses.trader_view, symbol)

    def compare(symbols: list[str]) -> dict:
        """Key metrics from both lenses side by side for up to 6 tickers (e.g. a stock
        and its peers, or competing ETFs)."""
        return _safe(lenses.compare, symbols)

    def price_history(symbol: str, timeframe: Timeframe = "1Y") -> dict:
        """Compact price history: weekly bars (monthly beyond 2Y), the period high and
        low with dates, and the biggest up days, down days and gaps. Use it to find
        dates worth marking on the chart."""
        return _safe(lenses.price_history, symbol, timeframe)

    def explain(term: str) -> dict:
        """Plain-English definition of a metric or concept (e.g. 'RSI', 'P/E',
        'free cash flow', 'golden cross'): what it is, how it's calculated, how to
        read it, and the common trap."""
        entry = glossary.lookup(term)
        if entry:
            return entry
        return {"error": f"No entry for '{term}'.", "available": sorted(glossary.GLOSSARY)}

    # ------------------------------------------------------------ chart control

    def chart_show(symbol: str, timeframe: Timeframe = "1Y", indicators: list[Indicator] | None = None) -> dict:
        """Load a ticker on the user's chart. indicators replaces what's shown; omit
        it to keep the current set. Options: volume, sma20, sma50, sma200, ema20,
        bollinger, levels (auto support/resistance), rsi, macd."""
        cmd = {"type": "show", "symbol": symbol, "range": timeframe}
        if indicators is not None:
            cmd["indicators"] = indicators
        return command(cmd)

    def chart_indicators(indicators: list[Indicator]) -> dict:
        """Replace the indicators shown on the current chart."""
        return command({"type": "indicators", "indicators": indicators})

    def chart_level(price: float, label: str, tone: Tone = "info", symbol: str | None = None) -> dict:
        """Draw a labeled horizontal line at a price (support, resistance, a stop, a
        target). tone: bull (green), bear (red), warn (amber), info (blue)."""
        return command({"type": "level", "price": price, "label": label, "tone": tone, "symbol": symbol})

    def chart_mark(date: str, text: str, position: Literal["above", "below"] = "above",
                   tone: Tone = "info", symbol: str | None = None) -> dict:
        """Put a labeled marker on a date (YYYY-MM-DD): an earnings gap, a breakout, a
        cross. Keep text short (a few words). Non-trading days snap to the prior bar."""
        return command({"type": "mark", "date": date, "text": text, "position": position,
                        "tone": tone, "symbol": symbol})

    def chart_note(text: str) -> dict:
        """Post a short note in the dashboard's activity panel beside the chart: a
        takeaway, a definition, or what to watch next. A few sentences at most."""
        return command({"type": "note", "text": text})

    def chart_clear(symbol: str | None = None, everything: bool = False) -> dict:
        """Remove marks and levels from the current ticker (or one named), or from all
        tickers with everything=True."""
        return command({"type": "clear", "symbol": symbol, "all": everything})

    def chart_state() -> dict:
        """What the user is looking at right now: ticker, timeframe, indicators,
        marks, levels and recent activity. Check this when they say 'this chart'."""
        return read_state()

    return [overview, investor_view, trader_view, compare, price_history, explain,
            chart_show, chart_indicators, chart_level, chart_mark, chart_note, chart_clear, chart_state]
