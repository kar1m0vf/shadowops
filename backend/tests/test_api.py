import sqlite3

import pytest
from fastapi.testclient import TestClient

import main
from main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "events.sqlite3", development=True)) as client:
        yield client


def event(session_id="demo-session", timestamp="2026-10-09T12:00:00Z"):
    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "url": "https://example.com/settings",
        "action": "click",
        "target": {
            "tag": "button",
            "role": "button",
            "label": "Save",
            "selector": "#save",
        },
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "shadowops-backend"}


def test_recording_order_session_isolation_and_persistence(tmp_path):
    database_path = tmp_path / "events.sqlite3"
    with TestClient(create_app(database_path, development=False)) as client:
        first = client.post("/api/events", json=event())
        # An earlier timestamp must not change the order in which events were recorded.
        second = client.post(
            "/api/events", json=event(timestamp="2026-10-09T11:00:00Z")
        )
        other = client.post("/api/events", json=event(session_id="another-session"))
        assert [first.status_code, second.status_code, other.status_code] == [201] * 3
        expected = [first.json(), second.json()]
        assert expected[0]["id"] < expected[1]["id"]
        assert expected[0]["target"] == event()["target"]
        response = client.get("/api/events/demo-session")
        assert response.status_code == 200
        assert response.json() == expected
        assert client.get("/api/events/another-session").json() == [other.json()]
        assert client.get("/api/events/unknown-session").json() == []

    # Reopening the app uses the same SQLite file and retains the events.
    with TestClient(create_app(database_path, development=False)) as restarted:
        assert restarted.get("/api/events/demo-session").json() == expected


@pytest.mark.parametrize("invalid_field", ["session_id", "timestamp"])
def test_invalid_events_are_rejected_without_being_stored(client, invalid_field):
    payload = event()
    payload[invalid_field] = "" if invalid_field == "session_id" else "invalid-date"
    response = client.post("/api/events", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", invalid_field]
    assert client.get("/api/events/demo-session").json() == []


def test_development_cors_only_allows_local_frontend(client):
    for origin, expected_status in [
        ("http://localhost:5173", 200),
        ("https://example.com", 400),
    ]:
        response = client.options(
            "/api/events",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code == expected_status
        assert response.headers.get("access-control-allow-origin") == (
            origin if expected_status == 200 else None
        )


def test_cors_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("SHADOWOPS_ENV", raising=False)
    with TestClient(create_app(tmp_path / "events.sqlite3")) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


def test_storage_failure_returns_a_sensible_error(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(main.sqlite3, "connect", unavailable)
    response = client.post("/api/events", json=event())
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Event storage is temporarily unavailable. Try again."
    }
