from types import SimpleNamespace

from sqlalchemy.exc import OperationalError


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readyz_ok(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def broken_db(monkeypatch):
    def execute(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    monkeypatch.setattr("app.blueprints.health.db", SimpleNamespace(session=SimpleNamespace(execute=execute)))


def test_readyz_503_when_database_down(client, monkeypatch):
    broken_db(monkeypatch)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.get_json()["status"] == "Service Unavailable"


def test_healthz_stays_up_when_database_down(client, monkeypatch):
    broken_db(monkeypatch)
    assert client.get("/healthz").status_code == 200


def test_swagger_ui_is_served_at_docs(client):
    assert client.get("/docs").status_code == 200
