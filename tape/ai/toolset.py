"""Turns Tape's tools into what a model API needs: a JSON Schema for each tool, and
a safe way to run a call the model asked for.

Arguments from a model are untrusted until checked, so every call is validated
against the same type hints the schema was generated from before it runs. A bad
call comes back as an error result the model can read and correct.
"""

import inspect
import json
import logging
from typing import Any, Callable, get_type_hints

from fastapi.concurrency import run_in_threadpool
from pydantic import ConfigDict, ValidationError, create_model

from .. import tools

log = logging.getLogger("tape")


def _args_model(fn: Callable):
    hints = get_type_hints(fn)
    fields = {}
    for p in inspect.signature(fn).parameters.values():
        fields[p.name] = (hints[p.name], ... if p.default is p.empty else p.default)
    return create_model(f"{fn.__name__}_args", __config__=ConfigDict(extra="forbid"), **fields)


def _clean_schema(node: Any) -> Any:
    """Drop pydantic's auto-generated titles: tokens the model gets nothing from."""
    if isinstance(node, dict):
        return {k: _clean_schema(v) for k, v in node.items() if not (k == "title" and isinstance(v, str))}
    if isinstance(node, list):
        return [_clean_schema(v) for v in node]
    return node


LABELS = {
    "overview": "Reading the overview of {symbol}",
    "investor_view": "Reading the investor view of {symbol}",
    "trader_view": "Reading the trader view of {symbol}",
    "compare": "Comparing {symbols}",
    "price_history": "Reading {symbol} price history",
    "explain": "Looking up {term}",
    "chart_show": "Loading {symbol} on the chart",
    "chart_indicators": "Changing chart indicators",
    "chart_level": "Drawing a level at ${price}",
    "chart_mark": "Marking {date} on the chart",
    "chart_note": "Posting a note",
    "chart_clear": "Clearing chart drawings",
    "chart_state": "Checking what's on your chart",
}


class Toolset:
    def __init__(self, command: Callable[[dict], dict], read_state: Callable[[], dict]):
        functions = tools.build(command, read_state)
        self._functions = {fn.__name__: fn for fn in functions}
        self._models = {fn.__name__: _args_model(fn) for fn in functions}
        # Built once and never changed: a stable tool list keeps the prompt cache valid.
        self.specs = [{
            "name": fn.__name__,
            "description": inspect.cleandoc(fn.__doc__),
            "schema": _clean_schema(self._models[fn.__name__].model_json_schema()),
        } for fn in functions]

    def label(self, name: str, args: Any) -> str:
        template = LABELS.get(name, name)
        values = {k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in (args or {}).items()} \
            if isinstance(args, dict) else {}
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            return template.split(" {")[0].split(" $")[0]

    def started(self, call_id: str, name: str, args: Any) -> dict:
        return {"type": "tool_start", "id": call_id, "name": name, "label": self.label(name, args)}

    def finished(self, call_id: str, ok: bool) -> dict:
        return {"type": "tool_end", "id": call_id, "ok": ok}

    async def run(self, name: str, args: Any) -> tuple[str, bool]:
        """Run one tool call. Returns (result text for the model, whether it worked)."""
        fn = self._functions.get(name)
        if fn is None:
            return json.dumps({"error": f"There is no tool named {name}."}), False
        try:
            clean = self._models[name].model_validate(args)
        except ValidationError as e:
            problems = e.errors(include_url=False, include_input=False, include_context=False)
            return json.dumps({"INVALID_ARGUMENTS": problems, "received": args}, default=str), False
        kwargs = {field: getattr(clean, field) for field in self._models[name].model_fields}
        try:
            result = await run_in_threadpool(fn, **kwargs)
        except Exception as e:  # a tool failing must not end the chat; the model can read this
            log.exception("tool %s failed", name)
            return json.dumps({"error": f"{name} failed: {e}"}), False
        ok = not (isinstance(result, dict) and "error" in result)
        return json.dumps(result, separators=(",", ":"), default=str), ok
