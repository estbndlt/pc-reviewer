from src.tools.pkg_tools import pkg_caches


def test_pkg_caches_keys_and_types():
    caches = pkg_caches()
    assert set(caches.keys()) == {'brew_kb', 'npm_kb', 'pip_kb'}
    for v in caches.values():
        assert isinstance(v, int)
        assert v >= 0
