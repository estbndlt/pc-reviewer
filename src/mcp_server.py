#!/usr/bin/env python3

"""Minimal MCP-ish server exposing read-only tools over a WebSocket route."""

import json
import os
import asyncio
import logging
from datetime import datetime, UTC
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse, Response

from .tools.fs_tools import du_k, bigfiles
from .tools.pkg_tools import pkg_caches
from .tools.docker_tools import docker_df
from .tools.proc_tools import top_procs
from .logging_middleware import setup_logging

app = FastAPI()
setup_logging(app)

# logger for RPC diagnostics
logger = logging.getLogger(__name__)

# ---- MCP-ish tool registry -------------------------------------------------
TOOLS = {
    "fs.du": lambda params: du_k(
        params.get("path") or os.path.expanduser("~"),
        int(params.get("depth") or 2),
    ),
    "fs.bigfiles": lambda params: bigfiles(
        params.get("path") or os.path.expanduser("~"),
        params.get("min_size") or "+200M",
        int(params.get("limit") or 200),
    ),
    "pkg.caches": lambda params: pkg_caches(),
    "docker.df": lambda params: docker_df(),
    "proc.top": lambda params: top_procs(int(params.get("limit") or 25)),
    # "exec.run": exec_run,  # disabled by default
}


@app.get("/", response_class=PlainTextResponse)
def health() -> str:
    """Simple health check endpoint."""
    return "mcp:ok " + datetime.now(UTC).isoformat()


@app.websocket("/mcp")
async def mcp_socket(ws: WebSocket) -> None:
    """WebSocket endpoint implementing a minimal MCP-style JSON-RPC API."""
    await ws.accept()
    while True:
        try:
            msg = await ws.receive_text()
        except WebSocketDisconnect:
            break
        # log raw incoming message for diagnostics
        logger.info("WS raw message: %s", msg)
        try:
            req = json.loads(msg)
        except Exception as e:
            logger.error("WS invalid JSON: %s", e)
            await ws.send_text(json.dumps({"id": None, "error": {"message": "invalid json"}}))
            continue

        # Use the shared processor so HTTP/WS/SSE behavior is consistent
        mid = req.get("id")
        method = req.get("method")
        logger.info("WS RPC incoming: method=%s id=%s", method, mid)
        try:
            resp = _process_rpc_req(req)
        except Exception as e:
            # _process_rpc_req should not raise, but be defensive
            logger.exception("WS processing failed")
            resp = {"id": mid, "error": {"message": str(e), "available": list(TOOLS.keys())}}

        # If caller received an unknown-method error, ensure available list is present
        if "error" in resp:
            err = resp["error"]
            if "available" not in err:
                err["available"] = list(TOOLS.keys())

        await ws.send_text(json.dumps(resp))


# --- shared RPC processing helper -----------------------------------------
def _process_rpc_req(req: dict):
    """Process a parsed JSON-RPC-ish request dict and return a mapping with id/result or id/error."""
    mid = req.get("id")
    method = req.get("method")
    logger.debug("Processing RPC request: method=%s id=%s keys=%s", method, mid, list(req.keys()))
    try:
        if method == "initialize":
            # Return a simple capabilities response the extension can accept.
            # Adjust contents if the extension expects more fields.
            return {"id": mid, "result": {"capabilities": {}}}

        if method == "shutdown":
            # Respond positively; extension will call exit afterwards.
            return {"id": mid, "result": None}

        if method == "exit":
            # No response required by some clients, but return ok to be safe.
            return {"id": mid, "result": None}

        if method == "tools.list":
            result = {"tools": list(TOOLS.keys())}
        elif method == "tools.call":
            name = req["params"]["name"]
            params = req["params"].get("arguments", {}) or {}
            if name not in TOOLS:
                # return structured error rather than raising
                return {"id": mid, "error": {"message": f"unknown tool: {name}", "available": list(TOOLS.keys())}}
            result = {"name": name, "data": TOOLS[name](params)}
        else:
            # unknown method -> structured error with available methods
            return {"id": mid, "error": {"message": "unknown method", "available": list(TOOLS.keys())}}
        return {"id": mid, "result": result}
    except Exception as e:
        logger.exception("RPC handler exception")
        return {"id": mid, "error": {"message": str(e), "available": list(TOOLS.keys())}}


# --- HTTP endpoint for direct client->server calls ------------------------
@app.post("/mcp-http")
async def mcp_http(request: Request):
    """
    Accept JSON POST requests with the same JSON-RPC-ish shape used over WebSocket.
    Returns JSON: {"id":..., "result":...} or {"id":..., "error":...}
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"id": None, "error": {"message": "invalid json"}}, status_code=400)
    resp = _process_rpc_req(payload)
    return JSONResponse(resp)


@app.get("/mcp-http")
async def mcp_http_get(request: Request):
    """If client asks for SSE, return streaming event source; otherwise return lightweight JSON."""
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        # reuse the SSE subscribe implementation so GET /mcp-http works as an SSE endpoint
        return await mcp_sse_subscribe(request)
    return JSONResponse({"status": "ok", "tools": list(TOOLS.keys())})


@app.options("/mcp-http")
async def mcp_http_options():
    """
    Respond to preflight / probe OPTIONS requests.
    """
    return Response(status_code=200, headers={"Allow": "POST, GET, OPTIONS"})


# --- lightweight SSE support ----------------------------------------------
# subscribers: a set of asyncio.Queue instances (one per connected client)
_SSE_SUBSCRIBERS = set()


async def _sse_event_generator(q: "asyncio.Queue[str]"):
    try:
        while True:
            data = await q.get()
            # send as SSE `data: ...\n\n`
            yield f"data: {data}\n\n"
    finally:
        # nothing special here; cleanup handled by caller
        return


@app.get("/mcp-sse")
async def mcp_sse_subscribe(request: Request):
    """
    Subscribe to event stream. The server will push events (as JSON strings) to connected subscribers.
    This yields Server-Sent Events with lines starting `data:`.
    """
    q: "asyncio.Queue[str]" = asyncio.Queue()
    _SSE_SUBSCRIBERS.add(q)
    async def event_stream():
        try:
            async for chunk in _sse_event_generator(q):
                # disconnect if client closed
                if await request.is_disconnected():
                    break
                yield chunk
        finally:
            # remove subscriber on disconnect
            _SSE_SUBSCRIBERS.discard(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/mcp-sse")
async def mcp_sse_post(request: Request):
    """
    Accept a JSON-RPC-ish POST and return immediate JSONResponse (same shape as /mcp-http).
    Additionally, publish the response to any SSE subscribers.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"id": None, "error": {"message": "invalid json"}}, status_code=400)

    resp = _process_rpc_req(payload)
    # publish to subscribers asynchronously (non-blocking)
    text = json.dumps(resp)
    for q in list(_SSE_SUBSCRIBERS):
        # best-effort enqueue; ignore failures for dead subscribers
        try:
            q.put_nowait(text)
        except asyncio.QueueFull:
            # if queue full, drop the event for that subscriber
            pass
        except Exception:
            _SSE_SUBSCRIBERS.discard(q)
    return JSONResponse(resp)
