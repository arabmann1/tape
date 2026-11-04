"""Claude, through the official Anthropic SDK.

History between turns is plain text (see agent.py), and within a turn the replies
are sent back unchanged, so the thinking blocks they carry stay valid: the system
prompt, tools and earlier messages never change once a turn has started.
"""

import os
from typing import AsyncIterator

import anthropic

from .toolset import Toolset

MAX_TOKENS = 16000     # ceiling per model reply, to cap what one runaway answer can cost
MAX_ROUNDS = 12        # model calls per question, for the same reason
MAX_BAD_JSON = 2       # re-asks when a reply's tool input can't be parsed at all
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client(key: str) -> anthropic.AsyncAnthropic:
    # The address is explicit so an ANTHROPIC_BASE_URL set for some other tool can't
    # send this key anywhere but Anthropic. The TAPE_ override is for the test suite.
    return anthropic.AsyncAnthropic(api_key=key, timeout=anthropic.Timeout(300.0, connect=15.0),
                                    base_url=os.environ.get("TAPE_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))


def _params(model: dict, system: str, toolset: Toolset) -> dict:
    params = {
        "model": model["id"],
        "max_tokens": MAX_TOKENS,
        "system": system,
        "tools": [{"name": s["name"], "description": s["description"], "input_schema": s["schema"],
                   "eager_input_streaming": True} for s in toolset.specs],
        "cache_control": {"type": "ephemeral"},
    }
    if model.get("known"):
        params["thinking"] = {"type": "adaptive"}
        params["output_config"] = {"effort": "medium"}
    if model.get("fallback"):
        # If a safety classifier wrongly declines a stock question, Anthropic reruns
        # it on another model instead of ending the answer.
        params["fallbacks"] = "default"
        params["betas"] = [FALLBACK_BETA]
    return params


def _echo(content: list) -> list:
    """The reply as it must be sent back. After a mid-answer fallback, only the text
    from before the switch is sent back, and the switch marker itself is dropped."""
    boundary = max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)
    return [b for i, b in enumerate(content) if i > boundary or b.type == "text"]


def _usage(u) -> dict:
    return {"type": "usage", "input": u.input_tokens or 0, "output": u.output_tokens or 0,
            "cache_read": u.cache_read_input_tokens or 0, "cache_write": u.cache_creation_input_tokens or 0}


async def run(key: str, model: dict, system: str, prior: list[dict], user_text: str,
              toolset: Toolset) -> AsyncIterator[dict]:
    client = _client(key)
    params = _params(model, system, toolset)
    messages = [{"role": m["role"], "content": m["text"]} for m in prior]
    messages.append({"role": "user", "content": user_text})
    bad_json = 0

    for _ in range(MAX_ROUNDS):
        try:
            async with client.beta.messages.stream(messages=messages, **params) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield {"type": "text", "text": event.text}
                response = await stream.get_final_message()
            bad_json = 0
        except ValueError:
            # The SDK couldn't parse a tool input at all, so there's no call to answer.
            bad_json += 1
            if bad_json > MAX_BAD_JSON:
                yield {"type": "notice", "message": "Claude kept sending a garbled tool call, so I stopped. Try asking again."}
                return
            continue

        yield _usage(response.usage)
        content = _echo(response.content)

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": content})
            continue
        if response.stop_reason == "refusal":
            yield {"type": "notice", "message": "Claude declined to answer this one. Try rephrasing the question."}
            return
        if response.stop_reason == "max_tokens":
            # A tool input cut off here can still parse, so never run this turn's tools.
            yield {"type": "notice", "message": "This answer hit the length limit and was cut off. Ask for a shorter version or the rest."}
            return

        calls = [b for b in content if b.type == "tool_use"]
        if not calls:
            return

        results = []
        for call in calls:
            yield toolset.started(call.id, call.name, call.input)
            output, ok = await toolset.run(call.name, call.input)
            yield toolset.finished(call.id, ok)
            result = {"type": "tool_result", "tool_use_id": call.id, "content": output}
            if not ok:
                result["is_error"] = True
            results.append(result)
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": results})

    yield {"type": "notice", "message": f"Stopped after {MAX_ROUNDS} steps to protect your API budget. Ask me to continue if you want more."}


async def check(key: str, model: dict) -> None:
    """Confirm the key works and can use this model. Costs nothing."""
    await _client(key).models.retrieve(model["id"])


def _detail(e: anthropic.APIStatusError) -> str:
    body = e.body if isinstance(e.body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    return error.get("message") or e.message


def explain(e: Exception, model: dict) -> dict | None:
    """A plain-English message for an API error, or None if this isn't one of ours."""
    billing = "https://console.anthropic.com/settings/billing"
    if isinstance(e, anthropic.AuthenticationError):
        return {"message": "Anthropic rejected this API key. Check that you copied all of it, or create a new one.", "action": "settings"}
    if isinstance(e, anthropic.PermissionDeniedError):
        return {"message": f"This key isn't allowed to do that: {_detail(e)}", "action": "settings"}
    if isinstance(e, anthropic.NotFoundError):
        return {"message": f"This key can't use {model['id']}. Choose another model in Settings.", "action": "settings"}
    if isinstance(e, anthropic.RateLimitError):
        return {"message": "Anthropic is limiting this key's requests right now. Wait a minute and try again.", "action": None}
    if isinstance(e, anthropic.BadRequestError):
        detail = _detail(e)
        if "credit balance" in detail.lower():
            return {"message": f"Your Anthropic account is out of credit. Add some at {billing}", "action": "settings"}
        return {"message": f"Anthropic couldn't process that request: {detail}", "action": None}
    if isinstance(e, anthropic.APIStatusError):
        return {"message": f"Anthropic is having trouble right now (error {e.status_code}). Try again shortly.", "action": None}
    if isinstance(e, anthropic.APIConnectionError):
        return {"message": "Couldn't reach Anthropic. Check your internet connection and try again.", "action": None}
    return None
