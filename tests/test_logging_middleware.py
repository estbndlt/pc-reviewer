from fastapi import FastAPI
from fastapi.testclient import TestClient
import logging
from src.logging_middleware import setup_logging


app = FastAPI()
setup_logging(app)


@app.get('/demo')
def demo():
    return 'ok'


def test_logging_middleware_redacts_authorization():
    """Attach a test handler to 'pc-reviewer' logger to assert headers are redacted."""
    messages: list[str] = []

    class ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                messages.append(self.format(record))
            except Exception:
                messages.append(record.getMessage())

    logger = logging.getLogger("pc-reviewer")
    lh = ListHandler()
    lh.setLevel(logging.INFO)
    lh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(lh)
    try:
        client = TestClient(app)
        client.get('/demo', headers={'Authorization': 'secret'})
    finally:
        logger.removeHandler(lh)

    # middleware logs should contain the redacted header
    assert any('<redacted>' in m for m in messages)
