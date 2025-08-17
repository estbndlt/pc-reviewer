"""Process inspection tools."""

from typing import TypedDict
import psutil


class ProcInfo(TypedDict):
    pid: int
    name: str
    mem_pct: float
    cpu_pct: float
    cmd: str


def top_procs(limit: int = 25) -> list[ProcInfo]:
    """Return information about top processes on the host."""
    procs: list[ProcInfo] = []
    for p in psutil.process_iter(attrs=["pid", "name", "memory_percent", "cpu_percent", "cmdline"]):
        try:
            procs.append(
                {
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "mem_pct": round(p.info["memory_percent"] or 0, 2),
                    "cpu_pct": round(p.cpu_percent(interval=0.0) or 0, 2),
                    "cmd": " ".join(p.info.get("cmdline") or [])[:240],
                }
            )
        except Exception:
            pass
    procs.sort(key=lambda r: (-r["mem_pct"], -r["cpu_pct"]))
    return procs[:limit]
