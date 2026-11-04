"""python -m tape serve          -> dashboard + API on http://127.0.0.1:8740
python -m tape serve --open   -> same, opening the browser; if Tape is already
                                 running it just opens that one
python -m tape mcp            -> MCP server on stdio (Claude Code starts this itself)"""

import socket
import sys
import threading
import time
import webbrowser

import httpx

from .config import HOST, PORT


def _is_tape(port: int) -> bool:
    try:
        return httpx.get(f"http://{HOST}:{port}/healthz", timeout=2).json().get("app") == "tape"
    except (httpx.HTTPError, ValueError, AttributeError):
        return False


def _free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    sys.exit(f"Ports {start} to {start + 19} are all in use. Close something and try again.")


def _open_when_ready(port: int) -> None:
    for _ in range(120):
        if _is_tape(port):
            webbrowser.open(f"http://{HOST}:{port}")
            return
        time.sleep(0.5)


def serve(open_browser: bool) -> None:
    import uvicorn

    port = PORT
    if open_browser:
        if _is_tape(port):
            print(f"Tape is already running: http://{HOST}:{port}")
            webbrowser.open(f"http://{HOST}:{port}")
            return
        port = _free_port(port)
        threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()
    print(f"Tape dashboard: http://{HOST}:{port}")
    uvicorn.run("tape.server:app", host=HOST, port=port, log_level="warning",
                timeout_graceful_shutdown=2)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "serve":
        serve("--open" in sys.argv[2:])
    elif cmd == "mcp":
        from .mcp_server import main as mcp_main
        mcp_main()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
