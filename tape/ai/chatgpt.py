"""ChatGPT's models, through the official OpenAI SDK and its Responses API.

store=False keeps conversations from being saved on OpenAI's side. Reasoning
then travels with the reply as encrypted content, and is sent back unchanged with
the tool results, as OpenAI requires for reasoning models.
"""

import json
import os
from typing import AsyncIterator

import openai

from .toolset import Toolset

MAX_OUTPUT_TOKENS = 25000  # ceiling per model reply, reasoning included (OpenAI's suggested minimum)
MAX_ROUNDS = 12            # model calls per question, to cap what one question can cost


def _client(key: str) -> openai.AsyncOpenAI:
    # The address is explicit so an OPENAI_BASE_URL set for some other tool can't
    # send this key anywhere but OpenAI. The TAPE_ override is for the test suite.
    return openai.AsyncOpenAI(api_key=key, timeout=openai.Timeout(300.0, connect=15.0),
                              base_url=os.environ.get("TAPE_OPENAI_BASE_URL", "https://api.openai.com/v1"))


def _params(model: dict, system: str, toolset: Toolset) -> dict:
    params = {
        "model": model["id"],
        "instructions": system,
        "tools": [{"type": "function", "name": s["name"], "description": s["description"],
                   "parameters": s["schema"], "strict": False} for s in toolset.specs],
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
        "stream": True,
    }
    if model.get("known"):
        params["reasoning"] = {"effort": "medium"}
        params["include"] = ["reasoning.encrypted_content"]
    return params


def _usage(u) -> dict:
    cached = u.input_tokens_details.cached_tokens if u.input_tokens_details else 0
    return {"type": "usage", "input": (u.input_tokens or 0) - (cached or 0), "output": u.output_tokens or 0,
            "cache_read": cached or 0, "cache_write": 0}


class ResponseFailed(Exception):
    pass


async def run(key: str, model: dict, system: str, prior: list[dict], user_text: str,
              toolset: Toolset) -> AsyncIterator[dict]:
    client = _client(key)
    params = _params(model, system, toolset)
    items = [{"role": m["role"], "content": m["text"]} for m in prior]
    items.append({"role": "user", "content": user_text})

    for _ in range(MAX_ROUNDS):
        response = None
        stream = await client.responses.create(input=items, **params)
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield {"type": "text", "text": event.delta}
            elif event.type == "response.refusal.delta":
                yield {"type": "text", "text": event.delta}
            elif event.type in ("response.completed", "response.incomplete", "response.failed"):
                response = event.response
            elif event.type == "error":
                raise ResponseFailed(event.message)

        if response is None:
            raise ResponseFailed("The connection closed before the answer finished.")
        if response.usage:
            yield _usage(response.usage)
        if response.status == "failed":
            raise ResponseFailed(response.error.message if response.error else "The response failed.")
        if response.status == "incomplete":
            # A tool call cut off here can't be trusted, so never run this turn's tools.
            yield {"type": "notice", "message": "This answer hit the length limit and was cut off. Ask for a shorter version or the rest."}
            return

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            return

        items += response.output
        for call in calls:
            try:
                args = json.loads(call.arguments)
            except ValueError:
                args = call.arguments  # fails validation below, and the model sees why
            yield toolset.started(call.call_id, call.name, args)
            output, ok = await toolset.run(call.name, args)
            yield toolset.finished(call.call_id, ok)
            items.append({"type": "function_call_output", "call_id": call.call_id, "output": output})

    yield {"type": "notice", "message": f"Stopped after {MAX_ROUNDS} steps to protect your API budget. Ask me to continue if you want more."}


async def check(key: str, model: dict) -> None:
    """Confirm the key works and can use this model. Costs nothing."""
    await _client(key).models.retrieve(model["id"])


def _detail(e: openai.APIStatusError) -> str:
    body = e.body if isinstance(e.body, dict) else {}
    return body.get("message") or e.message


def explain(e: Exception, model: dict) -> dict | None:
    """A plain-English message for an API error, or None if this isn't one of ours."""
    billing = "https://platform.openai.com/settings/organization/billing"
    if isinstance(e, ResponseFailed):
        return {"message": f"OpenAI couldn't finish that answer: {e}", "action": None}
    if isinstance(e, openai.AuthenticationError):
        return {"message": "OpenAI rejected this API key. Check that you copied all of it, or create a new one.", "action": "settings"}
    if isinstance(e, openai.PermissionDeniedError):
        return {"message": f"This key isn't allowed to do that: {_detail(e)}", "action": "settings"}
    if isinstance(e, openai.NotFoundError):
        return {"message": f"This key can't use {model['id']}. Choose another model in Settings.", "action": "settings"}
    if isinstance(e, openai.RateLimitError):
        if e.code == "insufficient_quota":
            return {"message": f"Your OpenAI account is out of credit. Add some at {billing}", "action": "settings"}
        return {"message": "OpenAI is limiting this key's requests right now. Wait a minute and try again.", "action": None}
    if isinstance(e, openai.BadRequestError):
        return {"message": f"OpenAI couldn't process that request: {_detail(e)}", "action": None}
    if isinstance(e, openai.APIStatusError):
        return {"message": f"OpenAI is having trouble right now (error {e.status_code}). Try again shortly.", "action": None}
    if isinstance(e, openai.APIConnectionError):
        return {"message": "Couldn't reach OpenAI. Check your internet connection and try again.", "action": None}
    return None
