"""The shared chart view ("board"): which ticker is on screen, which indicators
are showing, and the marks, levels and notes placed on it.

Both the dashboard and Claude change it through the same commands, so whoever
acts last wins and both always see the same thing. It's persisted so a
restart or page reload picks up where you left off.
"""

import itertools
import time
from copy import deepcopy

from . import cache, data
from .lenses import RANGES

INDICATORS = ["volume", "sma20", "sma50", "sma200", "ema20", "bollinger", "levels", "rsi", "macd"]
TONES = ["info", "bull", "bear", "warn"]
DEFAULT = {
    "symbol": "SPY",
    "range": "1Y",
    "indicators": ["volume", "sma50", "sma200", "rsi"],
    "marks": [],      # {id, symbol, date, text, position, tone, source}
    "levels": [],     # {id, symbol, price, label, tone, source}
    "activity": [],   # newest first: {id, ts, source, kind, symbol, text}
    "version": 0,
}
MAX_ACTIVITY = 60
_ids = itertools.count(int(time.time() * 1000))


class CommandError(ValueError):
    pass


def load() -> dict:
    state = cache.kv_get("board")
    return {**deepcopy(DEFAULT), **state} if state else deepcopy(DEFAULT)


def save(state: dict) -> None:
    cache.kv_set("board", state)


def _log(state, source, kind, text, symbol=None):
    state["activity"].insert(0, {
        "id": next(_ids), "ts": int(time.time()), "source": source,
        "kind": kind, "symbol": symbol or state["symbol"], "text": text,
    })
    del state["activity"][MAX_ACTIVITY:]


def _indicators(values) -> list[str]:
    bad = [v for v in values if v not in INDICATORS]
    if bad:
        raise CommandError(f"unknown indicator(s) {bad}; choose from {INDICATORS}")
    return [i for i in INDICATORS if i in values]


def _tone(t) -> str:
    t = t or "info"
    if t not in TONES:
        raise CommandError(f"tone must be one of {TONES}")
    return t


def apply(state: dict, cmd: dict, source: str = "you") -> dict:
    """Apply one command to a copy of the state and return the new state.
    Raises CommandError (bad input) or data.DataError (unknown ticker)."""
    s = deepcopy(state)
    kind = cmd.get("type")
    symbol = data.normalize(cmd["symbol"]) if cmd.get("symbol") else s["symbol"]

    if kind == "show":
        data.get_prices(symbol)  # validates the ticker and warms the cache
        s["symbol"] = symbol
        rng = cmd.get("range") or s["range"]
        if rng not in RANGES:
            raise CommandError(f"range must be one of {list(RANGES)}")
        s["range"] = rng
        if cmd.get("indicators") is not None:
            s["indicators"] = _indicators(cmd["indicators"])
        _log(s, source, "show", f"Loaded {symbol} · {rng}", symbol)

    elif kind == "range":
        if cmd.get("range") not in RANGES:
            raise CommandError(f"range must be one of {list(RANGES)}")
        s["range"] = cmd["range"]

    elif kind == "indicators":
        s["indicators"] = _indicators(cmd.get("indicators") or [])
        if source != "you":
            _log(s, source, "indicators", "Showing " + (", ".join(s["indicators"]) or "price only"))

    elif kind == "mark":
        text = (cmd.get("text") or "").strip()
        if not cmd.get("date") or not text:
            raise CommandError("mark needs a date (YYYY-MM-DD) and text")
        pos = cmd.get("position") or "above"
        if pos not in ("above", "below"):
            raise CommandError("position must be 'above' or 'below'")
        s["marks"].append({"id": next(_ids), "symbol": symbol, "date": cmd["date"][:10], "text": text[:80],
                           "position": pos, "tone": _tone(cmd.get("tone")), "source": source})
        _log(s, source, "mark", f"Marked {cmd['date'][:10]}: {text}", symbol)

    elif kind == "level":
        try:
            price = float(cmd["price"])
        except (KeyError, TypeError, ValueError):
            raise CommandError("level needs a numeric price")
        label = (cmd.get("label") or "").strip()[:40]
        s["levels"].append({"id": next(_ids), "symbol": symbol, "price": price, "label": label,
                            "tone": _tone(cmd.get("tone")), "source": source})
        _log(s, source, "level", f"Level ${price:,.2f}" + (f": {label}" if label else ""), symbol)

    elif kind == "note":
        text = (cmd.get("text") or "").strip()
        if not text:
            raise CommandError("note needs text")
        _log(s, source, "note", text[:2000], symbol)

    elif kind == "remove":
        target = cmd.get("id")
        s["marks"] = [m for m in s["marks"] if m["id"] != target]
        s["levels"] = [lv for lv in s["levels"] if lv["id"] != target]

    elif kind == "clear":
        everything = cmd.get("all", False)
        s["marks"] = [] if everything else [m for m in s["marks"] if m["symbol"] != symbol]
        s["levels"] = [] if everything else [lv for lv in s["levels"] if lv["symbol"] != symbol]
        _log(s, source, "clear", "Cleared all drawings" if everything else f"Cleared drawings on {symbol}", symbol)

    else:
        raise CommandError(f"unknown command type '{kind}'")

    s["version"] = state.get("version", 0) + 1
    return s


def summary(state: dict) -> dict:
    """What's on screen right now, trimmed for Claude to read."""
    sym = state["symbol"]
    return {
        "symbol": sym,
        "range": state["range"],
        "indicators": state["indicators"],
        "marks": [m for m in state["marks"] if m["symbol"] == sym],
        "levels": [lv for lv in state["levels"] if lv["symbol"] == sym],
        "recent_activity": state["activity"][:10],
    }
