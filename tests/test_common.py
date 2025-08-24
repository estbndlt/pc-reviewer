from src.tools.common import sh


def test_sh_runs_command():
    out = sh('echo hello')
    assert out.strip() == 'hello'
