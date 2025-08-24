from src.tools.proc_tools import top_procs


def test_top_procs_basic():
    procs = top_procs(limit=5)
    assert isinstance(procs, list)
    assert len(procs) <= 5
    if procs:
        item = procs[0]
        assert set(['pid', 'name', 'mem_pct', 'cpu_pct', 'cmd']) <= set(item.keys())
