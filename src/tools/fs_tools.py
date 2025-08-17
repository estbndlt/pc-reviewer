"""Filesystem related tools."""

from typing import TypedDict
import os
import subprocess

from .common import sh


class DUEntry(TypedDict):
    path: str
    kb: int


class BigfileItem(TypedDict):
    path: str
    size: str


def du_k(path: str, depth: int = 2) -> list[DUEntry]:
    """Return disk usage for ``path`` in kilobytes up to ``depth`` levels."""
    try:
        out = subprocess.check_output(["du", "-k", "-d", str(depth), path], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        out = subprocess.check_output(["du", "-k", "--max-depth", str(depth), path], text=True, stderr=subprocess.DEVNULL)
    rows: list[DUEntry] = []
    for line in out.splitlines():
        try:
            kb, p = line.split("\t", 1)
            rows.append({"path": p, "kb": int(kb)})
        except ValueError:
            pass
    return rows


def bigfiles(path: str, min_size: str = "+200M", limit: int = 200) -> list[BigfileItem]:
    """List large files within ``path``."""
    out = sh(
        f'find "{path}" -type f -size {min_size} -print0 | '
        f"xargs -0 ls -laSh 2>/dev/null | head -n {limit}"
    )
    items: list[BigfileItem] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 9:
            size = parts[4]
            fp = " ".join(parts[8:])
            items.append({"path": fp, "size": size})
    return items
