#!/usr/bin/env python3

"""Minimal MCP-ish server exposing read-only tools over a WebSocket route."""

import json
import os
from datetime import datetime, UTC
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from .tools.fs_tools import du_k, bigfiles
from .tools.pkg_tools import pkg_caches
from .tools.docker_tools import docker_df
from .tools.proc_tools import top_procs
from .logging_middleware import setup_logging

app = FastAPI()
setup_logging(app)

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
        try:
            req = json.loads(msg)
            mid = req.get("id")
            method = req.get("method")
            if method == "tools.list":
                result = {"tools": list(TOOLS.keys())}
            elif method == "tools.call":
                name = req["params"]["name"]
                params = req["params"].get("arguments", {}) or {}
                if name not in TOOLS:
                    raise ValueError(f"unknown tool: {name}")
                result = {"name": name, "data": TOOLS[name](params)}
            else:
                raise ValueError("unknown method")
            await ws.send_text(json.dumps({"id": mid, "result": result}))
        except Exception as e:
            await ws.send_text(json.dumps({"id": req.get('id'), "error": {"message": str(e)}}))
