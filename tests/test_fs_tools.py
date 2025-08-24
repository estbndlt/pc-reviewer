from src.tools.fs_tools import du_k, bigfiles
from pathlib import Path
import tempfile


def test_du_k_basic():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'file.txt'
        p.write_text('hello')
        result = du_k(td, depth=0)
        assert isinstance(result, list)
        assert any(r['path'] == td for r in result)


def test_bigfiles_lists_files():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'big.txt'
        p.write_text('x' * 10)
        items = bigfiles(td, min_size='+0c', limit=10)
        assert isinstance(items, list)
        assert any(Path(item['path']).name == 'big.txt' for item in items)
