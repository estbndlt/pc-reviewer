import asyncio
import json
import os
import sys

import websockets


WS_URL = os.environ.get("MCP_WS_URL", "ws://127.0.0.1:8765/mcp")


async def send_and_wait(ws, msg, expect_id, timeout=15):
    await ws.send(json.dumps(msg))
    # Read until we see the matching id (tolerate any log/notify frames)
    while True:
        resp_txt = await asyncio.wait_for(ws.recv(), timeout=timeout)
        print(resp_txt)
        try:
            obj = json.loads(resp_txt)
        except Exception:
            continue
        if obj.get("id") == expect_id:
            return obj


async def main():
    # Increase timeouts for slower du calls; keep ping to maintain connection
    async with websockets.connect(
        WS_URL,
        ping_interval=20,
        ping_timeout=20,
        max_size=8 * 1024 * 1024,
    ) as ws:
        # 1) List tools
        await send_and_wait(ws, {"id": 1, "method": "tools.list", "params": {}}, expect_id=1, timeout=10)

        # 2) Call fs.du on HOME (expand ~ client-side for portability)
        home = os.path.expanduser("~")
        await send_and_wait(
            ws,
            {
                "id": 2,
                "method": "tools.call",
                "params": {"name": "fs.du", "arguments": {"path": home, "depth": 2}},
            },
            expect_id=2,
            timeout=120,  # give du time on large homes
        )

        # Done: close gracefully
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        sys.exit(130)