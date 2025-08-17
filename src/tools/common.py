import subprocess


def sh(cmd: str) -> str:
    """Run a shell command using ``bash -lc`` and return its stdout."""
    return subprocess.check_output(["bash", "-lc", cmd], text=True, stderr=subprocess.DEVNULL)
