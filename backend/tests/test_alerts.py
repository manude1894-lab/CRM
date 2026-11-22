"""Review 22-11-2026, package 6: unexpected errors are logged with a reference and alerted, without flooding."""
import pytest

from app.config import settings
from app.main import app
from app.services import alert_service


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    alert_service.reset()
    sent = []
    monkeypatch.setattr(alert_service, "_send_in_background", lambda subject, body: sent.append((subject, body)))
    yield sent
    alert_service.reset()


def test_same_error_is_sent_once_in_fifteen_minutes(_clean, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "https://example.invalid/hook")
    for _ in range(5):
        alert_service.report("server", "GET /x", "KeyError", "boom")
    alert_service.report("server", "GET /y", "KeyError", "boom")
    assert len(_clean) == 2 and "KeyError" in _clean[0][0]
    assert len(alert_service.recent) == 6  # every one is still logged


def test_nothing_sent_when_not_configured(_clean, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "")
    monkeypatch.setattr(settings, "ALERT_EMAILS", "")
    alert_service.report("server", "GET /x", "KeyError", "boom")
    assert _clean == [] and len(alert_service.recent) == 1


def test_server_crash_returns_a_reference(_clean, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "https://example.invalid/hook")

    @app.get("/__boom_for_test")
    def boom():
        raise RuntimeError("kaput")

    try:
        r = TestClient(app, raise_server_exceptions=False).get("/__boom_for_test")
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/__boom_for_test"]
    assert r.status_code == 500 and "reference" in r.json()["detail"]
    assert "RuntimeError" in _clean[0][0] and "kaput" not in r.json()["detail"]


def test_browser_errors_are_reported_and_limited(client, _clean, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_URL", "https://example.invalid/hook")
    r = client.post("/api/v1/system/client-errors", json={"where": "Dashboard", "error_type": "ReferenceError",
                                                          "message": "people is not defined"})
    assert r.status_code == 202 and r.json()["reference"]
    assert "browser" in _clean[0][0]
    codes = [client.post("/api/v1/system/client-errors", json={"where": "x"}).status_code for _ in range(25)]
    assert 429 in codes
