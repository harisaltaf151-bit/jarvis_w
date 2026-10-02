"""
JARVIS Core Server
WebSocket + REST bridge — receives AI commands and executes them on the local machine.
Run:  python core/server.py
"""

import asyncio
import json
import logging
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

import websockets
from aiohttp import web

# ── project root on path ──────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.app_controller   import AppController
from tools.file_manager     import FileManager
from tools.browser_agent    import BrowserAgent
from tools.email_agent      import EmailAgent
from tools.system_monitor   import SystemMonitor
from tools.terminal_agent   import TerminalAgent
from tools.screen_capture   import ScreenCapture
from tools.calendar_agent   import CalendarAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("JARVIS")

CONNECTED_CLIENTS: set = set()

# ── tool registry ─────────────────────────────────────────────────────────────
def build_tools():
    return {
        "app":      AppController(),
        "files":    FileManager(),
        "browser":  BrowserAgent(),
        "email":    EmailAgent(),
        "system":   SystemMonitor(),
        "terminal": TerminalAgent(),
        "screen":   ScreenCapture(),
        "calendar": CalendarAgent(),
    }

TOOLS = None   # lazy-init after event loop starts


# ── command router ────────────────────────────────────────────────────────────
async def route_command(payload: dict) -> dict:
    """
    payload = { "tool": "app|files|browser|...", "action": "...", "params": {...} }
    Returns  { "ok": bool, "result": any, "error": str|None }
    """
    tool_name = payload.get("tool", "")
    action    = payload.get("action", "")
    params    = payload.get("params", {})

    tool = TOOLS.get(tool_name)
    if tool is None:
        return {"ok": False, "result": None, "error": f"Unknown tool: {tool_name}"}

    handler = getattr(tool, action, None)
    if handler is None:
        return {"ok": False, "result": None, "error": f"Unknown action '{action}' on tool '{tool_name}'"}

    try:
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**params)
        else:
            result = await asyncio.to_thread(handler, **params)
        return {"ok": True, "result": result, "error": None}
    except Exception as exc:                          # noqa: BLE001
        log.exception("Tool error")
        return {"ok": False, "result": None, "error": str(exc)}


# ── WebSocket handler ─────────────────────────────────────────────────────────
async def ws_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    log.info("Client connected  (total=%d)", len(CONNECTED_CLIENTS))

    # send welcome + system snapshot
    snap = await asyncio.to_thread(TOOLS["system"].snapshot)
    await websocket.send(json.dumps({"type": "welcome", "system": snap}))

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "error": "Invalid JSON"}))
                continue

            msg_type = msg.get("type", "command")

            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "ts": datetime.now().isoformat()}))

            elif msg_type == "command":
                log.info("CMD  tool=%-10s action=%s", msg.get("tool"), msg.get("action"))
                result = await route_command(msg)
                await websocket.send(json.dumps({"type": "result", "id": msg.get("id"), **result}))

            elif msg_type == "system_stats":
                snap = await asyncio.to_thread(TOOLS["system"].snapshot)
                await websocket.send(json.dumps({"type": "system_stats", **snap}))

            else:
                await websocket.send(json.dumps({"type": "error", "error": f"Unknown message type: {msg_type}"}))

    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning("Connection closed with error: %s", e)
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        log.info("Client disconnected (total=%d)", len(CONNECTED_CLIENTS))


# ── REST fallback ─────────────────────────────────────────────────────────────
async def rest_command(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Bad JSON"}, status=400)
    result = await route_command(payload)
    return web.json_response(result)


async def rest_health(_request: web.Request) -> web.Response:
    snap = await asyncio.to_thread(TOOLS["system"].snapshot)
    return web.json_response({"status": "online", "system": snap})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/command", rest_command)
    app.router.add_get("/health",   rest_health)

    # CORS for local UI
    async def cors_middleware(request, handler):
        resp = await handler(request)
        resp.headers["Access-Control-Allow-Origin"]  = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    app.middlewares.append(cors_middleware)
    return app


# ── entry point ───────────────────────────────────────────────────────────────
async def main():
    global TOOLS
    log.info("Initialising tools…")
    TOOLS = build_tools()
    log.info("Tools ready: %s", list(TOOLS.keys()))

    WS_PORT   = int(os.getenv("JARVIS_WS_PORT",   "8765"))
    HTTP_PORT = int(os.getenv("JARVIS_HTTP_PORT", "8766"))

    ws_server   = await websockets.serve(ws_handler, "localhost", WS_PORT)
    runner      = web.AppRunner(make_app())
    await runner.setup()
    http_server = web.TCPSite(runner, "localhost", HTTP_PORT)
    await http_server.start()

    os_name = platform.system()
    print("\n" + "═" * 60)
    print("  J.A.R.V.I.S  Personal AI OS  —  ONLINE")
    print("═" * 60)
    print(f"  WebSocket  →  ws://localhost:{WS_PORT}")
    print(f"  REST API   →  http://localhost:{HTTP_PORT}")
    print(f"  Platform   →  {os_name} {platform.release()}")
    print("═" * 60 + "\n")

    await asyncio.gather(
        ws_server.wait_closed(),
        asyncio.Event().wait(),   # keep HTTP alive
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nJARVIS offline.")
