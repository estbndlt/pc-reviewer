from fastapi import FastAPI
from fastapi.testclient import TestClient
import logging
from logging_middleware import setup_logging


app = FastAPI()
setup_logging(app)


@app.get('/demo')
def demo():
    return 'ok'


def test_logging_middleware_redacts_authorization(caplog):
    caplog.set_level(logging.INFO)
    client = TestClient(app)
    client.get('/demo', headers={'Authorization': 'secret'})
    assert any('<redacted>' in r.message for r in caplog.records if 'request' in r.message)
