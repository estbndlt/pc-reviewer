#!/usr/bin/env python3
"""Tiny HTTP->WebSocket proxy for the MCP server.

Expose a POST /mcp-http endpoint that forwards JSON-RPC payloads to the
existing WebSocket `/mcp` endpoint and returns the JSON reply. This lets
clients that only support HTTP (or a simple `url` entry in `mcp.json`) use
the MCP tools.

Run with:
  uvicorn src.mcp_http_bridge:app --host 0.0.0.0 --port 8766

The proxy expects the MCP server to be available at ws://127.0.0.1:8765/mcp
by default. Adjust MCP_WS if you run the MCP server on a different port.
"""

from fastapi import FastAPI, Request, Response
import json
import websockets

app = FastAPI()

# WebSocket address of the local MCP server (matches your tasks/launch config)
MCP_WS = "ws://127.0.0.1:8765/mcp"


@app.get("/", response_class=Response)
async def health():
    """Health check for the proxy."""
    return Response(content="mcp-proxy:ok", media_type="text/plain")


@app.post("/mcp-http")
async def proxy(request: Request):
    """Forward the raw JSON body to the MCP websocket and return the response.

    The endpoint expects the client to POST a JSON-RPC request body. The
    proxy opens a short-lived websocket connection to the MCP server, sends
    the request, awaits the single response, and returns it as JSON.
    """
    body = await request.body()
    # ensure we send text over the websocket
    text = body.decode()

    # open a websocket connection to the local MCP and forward the payload
    async with websockets.connect(MCP_WS) as ws:
        await ws.send(text)
        resp = await ws.recv()

    # Return the raw JSON reply from the MCP server
    return Response(content=resp, media_type="application/json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.mcp_http_bridge:app", host="0.0.0.0", port=8766)
