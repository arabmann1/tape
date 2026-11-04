"""Local web server: the dashboard's API, the live channel, and the built UI.

The live channel is Server-Sent Events: every change to the board (from the
dashboard, the in-app AI, or Claude Code through the MCP server) is pushed to every
open tab.
"""

import asyncio
import functools
import json
import logging

import anyio.from_thread
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, board, cache, data, glossary, lenses
from .ai import agent
from .ai import settings as ai_settings
from .ai.toolset import Toolset
from .config import DIST_DIR

log = logging.getLogger("tape")
app = FastAPI(title="Tape", docs_url="/api/docs", openapi_url="/api/openapi.json")

LOCAL_NAMES = {"127.0.0.1", "localhost", "[::1]"}
MAX_QUESTION_CHARS = 8000


class LocalOnly:
    """Only this computer's own Tape page may use the API.

    Binding to 127.0.0.1 keeps other machines out, but any website open in the
    user's browser can still send requests to localhost, and this API can spend
    their AI credit. The Host check stops DNS rebinding; the Origin check stops
    another site posting here. Plain ASGI so it doesn't buffer streaming responses.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not self._allowed(scope):
            await JSONResponse({"detail": "Tape only answers its own page."}, status_code=403)(scope, receive, send)
            return
        await self.inner(scope, receive, send)

    @staticmethod
    def _allowed(scope) -> bool:
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1")
        name = host if host.endswith("]") else host.rsplit(":", 1)[0]
        if name not in LOCAL_NAMES:
            return False
        origin = headers.get(b"origin", b"").decode("latin-1")
        return not origin or scope["method"] in ("GET", "HEAD") or origin == f"http://{host}"


app.add_middleware(LocalOnly)

_state = board.load()
_lock = asyncio.Lock()
_subscribers: set[asyncio.Queue] = set()


@app.exception_handler(data.DataError)
async def _data_error(_: Request, e: data.DataError):
    return JSONResponse({"detail": str(e)}, status_code=404)


@app.exception_handler(board.CommandError)
async def _command_error(_: Request, e: board.CommandError):
    return JSONResponse({"detail": str(e)}, status_code=400)


@app.exception_handler(ValueError)
async def _value_error(_: Request, e: ValueError):
    return JSONResponse({"detail": str(e)}, status_code=400)


@app.get("/healthz")
def healthz():
    return {"ok": True, "app": "tape", "version": __version__}


# ---------------------------------------------------------------- board + live channel

def _broadcast(state: dict) -> None:
    msg = json.dumps(state)
    for q in list(_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass  # a stalled tab; it resyncs from the next full snapshot


@app.get("/api/state")
def get_state():
    return _state


@app.get("/api/state/summary")
def get_summary():
    return board.summary(_state)


async def apply_command(cmd: dict, source: str) -> dict:
    global _state
    async with _lock:
        new = await run_in_threadpool(board.apply, _state, cmd, source)
        await run_in_threadpool(board.save, new)
        _state = new
    _broadcast(_state)
    return {"ok": True, "version": _state["version"], "symbol": _state["symbol"]}


@app.post("/api/command")
async def command(request: Request):
    cmd = await request.json()
    source = "claude" if cmd.pop("source", None) == "claude" else "you"
    return await apply_command(cmd, source)


@app.get("/api/events")
async def events(request: Request):
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.add(q)

    async def stream():
        try:
            yield f"data: {json.dumps(_state)}\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- analysis

@app.get("/api/chart/{symbol}")
def chart(symbol: str, range: str = "1Y"):
    return lenses.chart_payload(symbol, range)


@app.get("/api/overview/{symbol}")
def overview(symbol: str):
    return lenses.overview(symbol)


@app.get("/api/lens/{symbol}/{lens}")
def lens(symbol: str, lens: str):
    if lens == "investor":
        return lenses.investor_view(symbol)
    if lens == "trader":
        return lenses.trader_view(symbol)
    raise HTTPException(404, "lens must be 'investor' or 'trader'")


@app.get("/api/glossary")
def get_glossary():
    return glossary.GLOSSARY


@app.get("/api/watchlist")
def get_watchlist():
    return cache.kv_get("watchlist", ["SPY", "QQQ", "NVDA", "AAPL", "MSFT"])


@app.put("/api/watchlist")
async def put_watchlist(request: Request):
    symbols = await request.json()
    clean = list(dict.fromkeys(data.normalize(s) for s in symbols))[:50]
    cache.kv_set("watchlist", clean)
    return clean


# ---------------------------------------------------------------- AI

@functools.cache
def _toolset(provider: str) -> Toolset:
    # Tools run in a worker thread; chart changes hop back to the server's event loop.
    def run_command(cmd: dict) -> dict:
        try:
            return anyio.from_thread.run(apply_command, cmd, provider)
        except (ValueError, data.DataError) as e:  # a bad command or an unknown ticker
            return {"error": str(e)}

    return Toolset(run_command, lambda: board.summary(_state))


@app.get("/api/ai/settings")
def get_ai_settings():
    return ai_settings.public()


@app.put("/api/ai/settings")
async def put_ai_settings(request: Request):
    return ai_settings.update(await request.json())


@app.post("/api/ai/test")
async def test_ai():
    return await agent.check()


@app.get("/api/ai/chat")
def get_chat():
    return agent.history()


@app.delete("/api/ai/chat")
def clear_chat():
    if agent.busy():
        raise HTTPException(409, "Wait for the current answer to finish, or stop it first.")
    agent.clear()
    return {"ok": True}


@app.post("/api/ai/chat")
async def post_chat(request: Request):
    body = await request.json()
    message = str(body.get("message") or "").strip()
    if not message:
        raise ValueError("Type a question first.")
    if len(message) > MAX_QUESTION_CHARS:
        raise ValueError(f"That's too long. Keep questions under {MAX_QUESTION_CHARS:,} characters.")
    if agent.busy():
        raise HTTPException(409, "Still working on the last question. Stop it or wait for it to finish.")

    async def stream():
        async for event in agent.turn(message, _toolset, lambda: board.summary(_state)):
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- UI

if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse)
    def no_ui():
        return ("<body style='background:#0b0b0e;color:#ddd;font:15px system-ui;padding:40px'>"
                "<h2>Tape API is running</h2><p>The dashboard isn't built yet. In "
                "<code>frontend</code> run <code>npm install</code> then "
                "<code>npm run build</code>, and restart.</p></body>")
