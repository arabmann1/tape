"""The AI providers and models Tape offers, with list prices for cost estimates.

Prices are US dollars per million tokens, checked 2026-11-04 against each
provider's pricing page. They only feed the "about $0.03" line under an answer,
so a stale price gives a wrong estimate, never a wrong bill. A model ID that
isn't listed here still works (Settings > Other); it just shows tokens, not cost,
and gets no model-specific request settings.
"""

PROVIDERS = {
    "claude": {
        "label": "Claude",
        "company": "Anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "key_url": "https://console.anthropic.com/settings/keys",
        "billing_url": "https://console.anthropic.com/settings/billing",
        "default_model": "claude-opus-5-5",
        "models": [
            {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "blurb": "Most thorough",
             "input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00, "fallback": True},
            {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "blurb": "Balanced",
             "input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50, "fallback": True},
            {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "blurb": "Fastest, cheapest",
             "input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125, "fallback": False},
        ],
    },
    "chatgpt": {
        "label": "ChatGPT",
        "company": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys",
        "billing_url": "https://platform.openai.com/settings/organization/billing",
        "default_model": "gpt-6.1-sol",
        "models": [
            {"id": "gpt-6-astra", "label": "GPT-6 Astra", "blurb": "Most thorough",
             "input": 10.00, "output": 50.00, "cache_read": 1.00, "cache_write": 10.00},
            {"id": "gpt-6.1-sol", "label": "GPT-6.1 Sol", "blurb": "Balanced",
             "input": 2.00, "output": 10.00, "cache_read": 0.10, "cache_write": 2.00},
            {"id": "gpt-6.1-terra", "label": "GPT-6.1 Terra", "blurb": "Lighter",
             "input": 1.00, "output": 5.00, "cache_read": 0.05, "cache_write": 1.00},
            {"id": "gpt-6-luna", "label": "GPT-6 Luna", "blurb": "Fastest, cheapest",
             "input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.10},
        ],
    },
}


def model_spec(provider: str, model_id: str) -> dict:
    """The catalog entry for a model, or a bare one for an ID typed in by hand."""
    for m in PROVIDERS[provider]["models"]:
        if m["id"] == model_id:
            return {**m, "known": True}
    return {"id": model_id, "label": model_id, "known": False}


def cost(model: dict, usage: dict) -> float | None:
    """Estimated dollars for a usage record, or None for a model we have no price for."""
    if not model.get("known"):
        return None
    return (usage["input"] * model["input"]
            + usage["output"] * model["output"]
            + usage["cache_read"] * model["cache_read"]
            + usage["cache_write"] * model["cache_write"]) / 1_000_000
