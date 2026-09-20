"""Application startup: the schema exists before the first request."""

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app, global_exception_handler


class _Request:
    """Only `url` is read, for the log line."""

    url = "http://testserver/api/students/register"


def test_startup_creates_the_schema(monkeypatch):
    """Without this, a fresh checkout 500s on the first write to the database."""
    calls = []
    monkeypatch.setattr(main, "init_database", lambda: calls.append(True))

    with TestClient(app):
        pass

    assert calls, "lifespan did not create the schema"


@pytest.mark.parametrize(
    "debug,expected",
    [(True, "boom"), (False, None)],
)
async def test_unhandled_error_detail_follows_app_debug(monkeypatch, debug, expected):
    """The flag is app.debug; reading plain "debug" withheld the cause in development."""

    class _Settings:
        @staticmethod
        def get(key, default=None):
            return debug if key == "app.debug" else default

    monkeypatch.setattr(main, "settings", _Settings)

    response = await global_exception_handler(_Request(), RuntimeError("boom"))

    assert response.status_code == 500
    assert (
        (expected in response.body.decode())
        if expected
        else ('"details":null' in response.body.decode())
    )
