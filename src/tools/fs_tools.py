"""Filesystem related tools."""

import os
import platform
import shutil
import subprocess
from typing import Dict, List, TypedDict
import re
import shlex

from .common import sh

DU_SYNTAX = os.environ.get("DU_SYNTAX", "").lower()  # 'bsd' or 'gnu' (optional override)


class DUEntry(TypedDict):
    path: str
    kb: int


class BigfileItem(TypedDict):
    path: str
    size: str


def _expand_path(path: str) -> str:
    # Expand ~ and env vars, then absolutize
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def _du_cmd(depth: int) -> list[str]:
    # Prefer GNU coreutils 'gdu' if installed (common on macOS via brew)
    if shutil.which("gdu"):
        return ["gdu", "-k", f"--max-depth={depth}"]
    # Optional explicit override
    if DU_SYNTAX == "gnu":
        return ["du", "-k", f"--max-depth={depth}"]
    if DU_SYNTAX == "bsd":
        return ["du", "-k", "-d", str(depth)]
    if platform.system() == "Linux":
        return ["du", "-k", f"--max-depth={depth}"]
    # macOS/BSD
    return ["du", "-k", "-d", str(depth)]


def du(path: str, depth: int = 2) -> List[Dict[str, int]]:
    """
    Cross-platform directory sizes.
    Returns: [{"path": str, "kb": int}, ...]
    """
    target = _expand_path(path)
    cmd = _du_cmd(depth) + [target]
    # Run once; accept non-zero exit codes (permission denied etc.) and parse what we can.
    proc = subprocess.run(cmd, text=True, capture_output=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    # If it's a usage/illegal-option error and no output, try alternate syntax once.
    if proc.returncode != 0 and not stdout and (
        "illegal option" in stderr.lower() or "invalid" in stderr.lower() or "usage" in stderr.lower()
    ):
        if any("--max-depth" in c for c in cmd):
            fallback = ["du", "-k", "-d", str(depth), target]
        else:
            fallback = ["du", "-k", f"--max-depth={depth}", target]
        proc2 = subprocess.run(fallback, text=True, capture_output=True)
        stdout = proc2.stdout or ""

    results: List[Dict[str, int]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # GNU: "<kb>\t<path>", BSD: "<kb> <path>"
        parts = line.split("\t") if "\t" in line else line.split(None, 1)
        if len(parts) != 2:
            continue
        kb_str, p = parts
        try:
            kb = int(kb_str)
        except ValueError:
            continue
        results.append({"path": p, "kb": kb})
    return results


def du_k(path: str, depth: int = 2) -> list[DUEntry]:
    """Return disk usage for ``path`` in kilobytes up to ``depth`` levels."""
    target = _expand_path(path)
    cmd = _du_cmd(depth) + [target]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if proc.returncode != 0 and not stdout and (
        "illegal option" in stderr.lower() or "invalid" in stderr.lower() or "usage" in stderr.lower()
    ):
        if any("--max-depth" in c for c in cmd):
            fallback = ["du", "-k", "-d", str(depth), target]
        else:
            fallback = ["du", "-k", f"--max-depth={depth}", target]
        proc2 = subprocess.run(fallback, text=True, capture_output=True)
        stdout = proc2.stdout or ""
    rows: list[DUEntry] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t") if "\t" in line else line.split(None, 1)
        if len(parts) != 2:
            continue
        kb_str, p = parts
        try:
            rows.append({"path": p, "kb": int(kb_str)})
        except ValueError:
            continue
    return rows


def _sanitize_min_size(min_size: str) -> str:
    """
    Allow find(1) -size patterns like:
    '+200M', '500M', '1G', '+100k', '+0c', '0c', '+512b'
    If invalid, fallback to '+200M'.
    """
    s = str(min_size).strip()
    # Accept optional '+' and optional unit among c (bytes), b (512B blocks), k, M, G
    if re.fullmatch(r"[+]?\d+(?:[cCbBkKmMgG])?", s):
        return s
    return "+200M"


def bigfiles(path: str, min_size: str = "+200M", limit: int = 200) -> list[BigfileItem]:
    """List large files within ``path``."""
    target = _expand_path(path)
    if not os.path.isdir(target):
        return []
    size_arg = _sanitize_min_size(min_size)
    try:
        limit_n = max(1, min(int(limit), 10000))
    except Exception:
        limit_n = 200
    target_q = shlex.quote(target)
    out = sh(
        f"find {target_q} -type f -size {size_arg} -print0 2>/dev/null | "
        f"xargs -0 ls -laSh 2>/dev/null | head -n {limit_n}"
    )
    items: list[BigfileItem] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 9:
            size = parts[4]
            fp = " ".join(parts[8:])
            items.append({"path": fp, "size": size})
    return items
