"""Docker related tools."""

from .common import sh


def docker_df() -> dict[str, list[str]]:
    """Return raw output from ``docker system df``."""
    try:
        raw = sh("docker system df --format '{{json .}}' || true").splitlines()
    except Exception:
        raw = []
    return {"raw": raw}
