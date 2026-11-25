import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

URL = "/api/v1/users/me"


def assert_401(response):
    assert response.status_code == 401
    body = response.get_json()
    assert body["code"] == 401
    assert body["status"] == "Unauthorized"
    assert body["message"]
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_token(client):
    assert_401(client.get(URL))


@pytest.mark.parametrize(
    "header",
    ["Bearer", "Bearer not-a-jwt", "Bearer a.b.c", "Basic dXNlcjpwYXNz", "garbage"],
)
def test_malformed_token(client, header):
    assert_401(client.get(URL, headers={"Authorization": header}))


def test_expired_token(client, auth_header):
    assert_401(client.get(URL, headers=auth_header(expires_in=-60)))


def test_wrong_issuer(client, auth_header):
    assert_401(client.get(URL, headers=auth_header(iss="http://evil.example/realms/chat")))


def test_wrong_audience(client, auth_header):
    assert_401(client.get(URL, headers=auth_header(aud="some-other-api")))


def test_signed_with_another_key(client, auth_header):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert_401(client.get(URL, headers=auth_header(key=other)))


def test_unknown_kid(client, auth_header):
    assert_401(client.get(URL, headers=auth_header(headers={"kid": "nope"})))


def test_sub_that_is_not_a_uuid(client, auth_header):
    assert_401(client.get(URL, headers=auth_header(sub="not-a-uuid")))


def test_hs256_token_is_rejected(client, rsa_key):
    token = jwt.encode(
        {"iss": "http://localhost:8081/realms/chat", "aud": "chat-api", "sub": "x", "exp": int(time.time()) + 60},
        "secret-secret-secret-secret-secret",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    assert_401(client.get(URL, headers={"Authorization": f"Bearer {token}"}))
