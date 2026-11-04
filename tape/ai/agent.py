"""One chat turn: send the question to the chosen provider, run the tools it asks
for, stream everything to the dashboard, and save the result.

The history sent back to the model between turns is plain text: the questions and
the final answers, without the tool data behind them. That keeps a follow-up cheap,
since tool results are the bulk of a conversation's tokens and the model can call
a tool again, and it means a chat can move between Claude and ChatGPT mid-way.
"""

import asyncio
import contextlib
import importlib
import logging
from typing import AsyncIterator, Callable

from fastapi.concurrency import run_in_threadpool

from .. import cache
from . import catalog, prompt, settings
from .toolset import Toolset

log = logging.getLogger("tape")

HISTORY_KEY = "chat"
SENT_MESSAGES = 16       # earlier messages sent with each question
KEPT_MESSAGES = 200      # messages kept for the chat panel
_lock = asyncio.Lock()


def provider_module(name: str):
    # Imported on first use: the SDKs are slow to load and most starts don't need both.
    return importlib.import_module(f".{name}", __package__)


def history() -> list[dict]:
    return cache.kv_get(HISTORY_KEY, [])


def clear() -> None:
    cache.kv_set(HISTORY_KEY, [])


def busy() -> bool:
    return _lock.locked()


def _prior(log_: list[dict]) -> list[dict]:
    sent = [{"role": m["role"], "text": m["text"]} for m in log_ if m.get("text")][-SENT_MESSAGES:]
    while sent and sent[0]["role"] != "user":
        sent.pop(0)
    return sent


def _save(log_: list[dict]) -> None:
    cache.kv_set(HISTORY_KEY, log_[-KEPT_MESSAGES:])


async def turn(message: str, toolset_for: Callable[[str], Toolset], read_state: Callable[[], dict]) -> AsyncIterator[dict]:
    """Yields events for the dashboard: start, text, tool_start, tool_end, notice,
    usage, error, done."""
    async with _lock:
        cfg = settings.active()
        provider, model = cfg["provider"], cfg["model"]
        label = catalog.PROVIDERS[provider]["label"]
        if not cfg["key"]:
            yield {"type": "error", "message": f"Add your {label} API key in Settings first.", "action": "settings"}
            yield {"type": "done"}
            return

        log_ = history()
        prior = _prior(log_)
        reply = {"role": "assistant", "text": "", "tools": [], "notices": [], "provider": provider,
                 "provider_label": label, "model": model["id"], "model_label": model["label"], "usage": None}
        log_ += [{"role": "user", "text": message}, reply]
        _save(log_)
        yield {"type": "start", "provider": provider, "provider_label": label, "model": model["id"], "model_label": model["label"]}

        totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        needs_break = False
        module = None
        try:
            module = await run_in_threadpool(provider_module, provider)
            user_text = f"{prompt.context(read_state())}\n\n{message}"
            events = module.run(cfg["key"], model, prompt.SYSTEM, prior, user_text, toolset_for(provider))
            async with contextlib.aclosing(events):
                async for event in events:
                    kind = event["type"]
                    if kind == "usage":
                        for field in totals:
                            totals[field] += event[field]
                        continue
                    if kind == "text":
                        if needs_break and reply["text"]:
                            event = {"type": "text", "text": "\n\n" + event["text"]}
                        needs_break = False
                        reply["text"] += event["text"]
                    elif kind == "tool_start":
                        needs_break = True
                        reply["tools"].append({"id": event["id"], "name": event["name"], "label": event["label"], "ok": None})
                    elif kind == "tool_end":
                        for t in reply["tools"]:
                            if t["id"] == event["id"]:
                                t["ok"] = event["ok"]
                    elif kind == "notice":
                        reply["notices"].append(event["message"])
                    yield event
        except (asyncio.CancelledError, GeneratorExit):
            reply["notices"].append("Stopped.")
            raise
        except Exception as e:
            friendly = module.explain(e, model) if module else None
            if friendly is None:
                log.exception("chat turn failed")
                friendly = {"message": f"Something went wrong: {e}", "action": None}
            reply["error"] = friendly["message"]
            yield {"type": "error", **friendly}
        finally:
            reply["usage"] = {**totals, "cost": catalog.cost(model, totals)}
            _save(log_)

        yield {"type": "usage", **reply["usage"]}
        yield {"type": "done"}


async def check() -> dict:
    """Test the active key and model with a free call."""
    cfg = settings.active()
    label = catalog.PROVIDERS[cfg["provider"]]["label"]
    if not cfg["key"]:
        return {"ok": False, "message": f"Add your {label} API key first."}
    module = None
    try:
        module = await run_in_threadpool(provider_module, cfg["provider"])
        await module.check(cfg["key"], cfg["model"])
    except Exception as e:
        friendly = module.explain(e, cfg["model"]) if module else None
        return {"ok": False, "message": friendly["message"] if friendly else f"Something went wrong: {e}"}
    return {"ok": True, "message": f"Connected to {label}. {cfg['model']['label']} is ready."}
