from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Make the src directory importable
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.text.startswith("mcp:ok")


def test_tools_list_via_websocket():
    expected_tools = {"fs.du", "fs.bigfiles", "pkg.caches", "docker.df", "proc.top"}
    with client.websocket_connect("/mcp") as ws:
        ws.send_json({"id": 1, "method": "tools.list"})
        data = ws.receive_json()
        assert data["id"] == 1
        assert set(data["result"]["tools"]) == expected_tools


def test_tools_call_proc_top():
    with client.websocket_connect("/mcp") as ws:
        ws.send_json({"id": 1, "method": "tools.call", "params": {"name": "proc.top", "arguments": {"limit": 1}}})
        data = ws.receive_json()
        assert data["id"] == 1
        assert data["result"]["name"] == "proc.top"
        result = data["result"]["data"]
        assert isinstance(result, list)
        if result:
            item = result[0]
            for key in ("pid", "name", "mem_pct", "cpu_pct", "cmd"):
                assert key in item


def test_tools_call_unknown_tool_error():
    with client.websocket_connect("/mcp") as ws:
        ws.send_json({"id": 2, "method": "tools.call", "params": {"name": "unknown.tool"}})
        data = ws.receive_json()
        assert data["id"] == 2
        assert "error" in data
        assert "unknown tool" in data["error"]["message"]
