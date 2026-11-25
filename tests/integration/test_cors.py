import pytest

ALLOWED = "https://app.example.test"
OTHER = "https://evil.example.test"
PATH = "/api/v1/users/me"


@pytest.fixture
def make_client(app, monkeypatch):
    """make_client(origins) -> test client for a fresh app with CORS_ALLOWED_ORIGINS set (or unset)."""

    def _make(origins=None):
        # `app` is requested so the hermetic test environment variables are already set.
        if origins is None:
            monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        else:
            monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
        from app import create_app

        return create_app().test_client()

    return _make


def _preflight(client, origin=ALLOWED):
    return client.options(
        PATH,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_preflight_from_allowed_origin_needs_no_token(make_client):
    response = _preflight(make_client(ALLOWED))

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED
    allowed_headers = response.headers["Access-Control-Allow-Headers"].lower()
    assert "authorization" in allowed_headers and "content-type" in allowed_headers
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_preflight_from_other_origin_gets_no_cors_headers(make_client):
    response = _preflight(make_client(ALLOWED), origin=OTHER)

    assert "Access-Control-Allow-Origin" not in response.headers


def test_several_origins_are_allowed(make_client):
    client = make_client(f"{ALLOWED}, https://other.example.test")

    assert _preflight(client, "https://other.example.test").headers["Access-Control-Allow-Origin"] == (
        "https://other.example.test"
    )


def test_no_cors_headers_when_not_configured(make_client):
    response = _preflight(make_client(None))

    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_does_not_weaken_authentication(make_client):
    response = make_client(ALLOWED).get(PATH, headers={"Origin": ALLOWED})

    assert response.status_code == 401
    assert response.headers["Access-Control-Allow-Origin"] == ALLOWED


def test_health_endpoints_have_no_cors_headers(make_client):
    response = make_client(ALLOWED).get("/healthz", headers={"Origin": ALLOWED})

    assert "Access-Control-Allow-Origin" not in response.headers
