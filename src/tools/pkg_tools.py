"""Package cache inspection tools."""

from .common import sh
import os


def pkg_caches() -> dict[str, int]:
    """Return disk usage of common package manager caches."""
    home = os.path.expanduser("~")

    def du1(p: str) -> int:
        if not p:
            return 0
        try:
            out = sh(f'du -sk "{p}" 2>/dev/null')
            return int(out.split()[0])
        except Exception:
            return 0

    brew = (sh("brew --cache || true") or "").strip()
    npm = (sh("npm config get cache 2>/dev/null || true") or "").strip()
    pipc = os.path.join(home, ".cache", "pip")
    return {"brew_kb": du1(brew), "npm_kb": du1(npm), "pip_kb": du1(pipc)}
