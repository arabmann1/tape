"""Which AI to use and the user's API keys.

Keys live in one JSON file in the data folder, never next to the app, so zipping
up or sending the Tape folder can't take them along. On Windows that folder is
private to the user by default; elsewhere the file is set to owner-only. A key
is only ever sent to its own provider, and the API only ever hands back its last
four characters.
"""

import json
import os
import re
import stat
from copy import deepcopy
from pathlib import Path

from ..config import DATA_DIR
from .catalog import PROVIDERS, model_spec

SETTINGS_PATH = DATA_DIR / "ai-settings.json"
DEFAULTS = {"provider": "claude", "keys": {}, "models": {}}


def _read() -> dict:
    try:
        saved = json.loads(Path(SETTINGS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return deepcopy(DEFAULTS)
    return {**deepcopy(DEFAULTS), **saved}


def _write(settings: dict) -> None:
    path = Path(SETTINGS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Create it owner-only from the start so the key is never briefly world-readable.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, path)


def _check_key(provider: str, key: str) -> str:
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-.]{20,}", key):
        raise ValueError("That doesn't look like an API key. Copy the whole key, with no spaces.")
    if provider == "chatgpt" and key.startswith("sk-ant-"):
        raise ValueError("That's a Claude key (it starts with sk-ant-). Choose Claude, or paste an OpenAI key.")
    if provider == "claude" and key.startswith("sk-") and not key.startswith("sk-ant-"):
        raise ValueError("That looks like an OpenAI key. Choose ChatGPT, or paste a Claude key (sk-ant-...).")
    return key


def _key(settings: dict, provider: str) -> tuple[str | None, str | None]:
    saved = settings["keys"].get(provider)
    if saved:
        return saved, "saved"
    from_env = os.environ.get(PROVIDERS[provider]["key_env"])
    return (from_env, "environment") if from_env else (None, None)


def _model_id(settings: dict, provider: str) -> str:
    return settings["models"].get(provider) or PROVIDERS[provider]["default_model"]


def active(provider: str | None = None) -> dict:
    """What a chat should use: provider name, key (or None) and model entry."""
    settings = _read()
    provider = provider or settings["provider"]
    key, _ = _key(settings, provider)
    return {"provider": provider, "key": key, "model": model_spec(provider, _model_id(settings, provider))}


def public() -> dict:
    """Everything the settings screen needs, with the keys reduced to a hint."""
    settings = _read()
    providers = {}
    for name, p in PROVIDERS.items():
        key, source = _key(settings, name)
        providers[name] = {
            "label": p["label"],
            "company": p["company"],
            "key_url": p["key_url"],
            "billing_url": p["billing_url"],
            "has_key": bool(key),
            "key_hint": key[-4:] if key else None,
            "key_source": source,
            "model": _model_id(settings, name),
            "default_model": p["default_model"],
            "models": [{k: m[k] for k in ("id", "label", "blurb", "input", "output")} for m in p["models"]],
        }
    return {"provider": settings["provider"], "providers": providers}


def update(change: dict) -> dict:
    """Apply a change from the settings screen: provider, and per-provider key or model."""
    settings = _read()
    provider = change.get("provider", settings["provider"])
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {list(PROVIDERS)}")
    settings["provider"] = provider

    if change.get("key"):
        settings["keys"][provider] = _check_key(provider, change["key"])
    if change.get("remove_key"):
        settings["keys"].pop(provider, None)
    if "model" in change:
        model = str(change["model"]).strip()
        if not re.fullmatch(r"[A-Za-z0-9_\-.:]{1,80}", model):
            raise ValueError("That model ID has characters a model ID can't have.")
        settings["models"][provider] = model

    _write(settings)
    return public()
