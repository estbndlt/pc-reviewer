#!/usr/bin/env python3

# Minimal, pragmatic MCP-ish server exposing read-only tools over a single WS route.
# It accepts JSON-RPC messages with {"method":"tools.call", "params":{...}} and returns JSON results.
# Good enough for a Custom GPT connector expecting Remote MCP tool calls.

import asyncio, json, os, platform, subprocess, psutil
from datetime import datetime, UTC
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from typing import TypedDict


class DUEntry(TypedDict):
    path: str
    kb: int


class BigfileItem(TypedDict):
    path: str
    size: str


class ProcInfo(TypedDict):
    pid: int
    name: str
    mem_pct: float
    cpu_pct: float
    cmd: str

app = FastAPI()

# ---- helpers ---------------------------------------------------------------
def sh(cmd: str) -> str:
    return subprocess.check_output(["bash","-lc", cmd], text=True, stderr=subprocess.DEVNULL)

def du_k(path: str, depth: int = 2) -> list[DUEntry]:
    # macOS: -d; Linux: --max-depth
    try:
        out = subprocess.check_output(["du","-k","-d",str(depth),path], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        out = subprocess.check_output(["du","-k","--max-depth",str(depth),path], text=True, stderr=subprocess.DEVNULL)
    rows = []
    for line in out.splitlines():
        try:
            kb, p = line.split("\t",1)
            rows.append({"path": p, "kb": int(kb)})
        except ValueError:
            pass
    return rows


def bigfiles(path: str, min_size: str = "+200M", limit: int = 200) -> list[BigfileItem]:
    out = sh(f'find "{path}" -type f -size {min_size} -print0 | xargs -0 ls -laSh 2>/dev/null | head -n {limit}')
    items=[]
    for line in out.splitlines():
        parts=line.split()
        if len(parts)>=9:
            size=parts[4]; fp=" ".join(parts[8:])
            items.append({"path": fp, "size": size})
    return items


def pkg_caches() -> dict[str, int]:
    home = os.path.expanduser("~")
    def du1(p):
        if not os.path.isdir(p): return 0
        try: return int(sh(f'du -sk "{p}"').split()[0])
        except: return 0
    brew = (sh("brew --cache || true") or "").strip()
    npm  = (sh("npm config get cache 2>/dev/null || true") or "").strip()
    pipc = os.path.join(home, ".cache", "pip")
    return {"brew_kb": du1(brew), "npm_kb": du1(npm), "pip_kb": du1(pipc)}


def docker_df() -> dict[str, list[str]]:
    try:
        raw = sh("docker system df --format '{{json .}}' || true").splitlines()
    except Exception:
        raw = []
    return {"raw": raw}


def top_procs(limit: int = 25) -> list[ProcInfo]:
    procs = []
    for p in psutil.process_iter(attrs=["pid","name","memory_percent","cpu_percent","cmdline"]):
        try:
            procs.append({
                "pid": p.info["pid"],
                "name": p.info["name"],
                "mem_pct": round(p.info["memory_percent"] or 0, 2),
                "cpu_pct": round(p.cpu_percent(interval=0.0) or 0, 2),
                "cmd": " ".join(p.info.get("cmdline") or [])[:240]
            })
        except Exception:
            pass
    procs.sort(key=lambda r:(-r["mem_pct"], -r["cpu_pct"]))
    return procs[:limit]


# ---- MCP-ish tool registry -------------------------------------------------
TOOLS = {
    "fs.du": lambda params: du_k(params.get("path") or os.path.expanduser("~"), int(params.get("depth") or 2)),
    "fs.bigfiles": lambda params: bigfiles(params.get("path") or os.path.expanduser("~"),
                                           params.get("min_size") or "+200M",
                                           int(params.get("limit") or 200)),
    "pkg.caches": lambda params: pkg_caches(),
    "docker.df": lambda params: docker_df(),
    "proc.top": lambda params: top_procs(int(params.get("limit") or 25)),
    # "exec.run": DISABLED by default for safety; add when you explicitly opt in.
}

@app.get("/", response_class=PlainTextResponse)
def health() -> str:
    return "mcp:ok " + datetime.now(UTC).isoformat()


@app.websocket("/mcp")
async def mcp_socket(ws: WebSocket) -> None:
    await ws.accept()
    # simple JSON-RPC loop
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
