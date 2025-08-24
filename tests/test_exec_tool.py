import pytest
from src.tools.exec_tool import exec_run


def test_exec_run_disabled():
    with pytest.raises(RuntimeError):
        exec_run({})
