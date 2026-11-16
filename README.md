# user-service

Flask service that owns user profiles (see `../design.md`). First slice: health endpoints,
JWT validation, and `GET /api/v1/users/me` with lazy provisioning.

Layers: Blueprint (`app/blueprints`) → service (`app/services`, owns the commit) → repository
(`app/repositories`, queries only).

## Run with Docker (from `vilu-chat/`)

```bash
cp .env.example .env                      # once; set passwords (URL-safe)
docker compose up -d --build --wait user-service auth-stub
```

This starts Postgres, the auth stub (port 8081) and this service (port 8001). The container runs
`flask --app app db upgrade` before gunicorn.

```bash
TOKEN=$(curl -s -X POST localhost:8081/realms/chat/protocol/openid-connect/token -d username=anna \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s -H "Authorization: Bearer $TOKEN" localhost:8001/api/v1/users/me
```

Swagger UI: <http://localhost:8001/docs> (assets load from a CDN; use "Authorize" with a token).
Health: `/healthz` (liveness), `/readyz` (runs `SELECT 1`).

## Endpoints (`/api/v1/users`, bearer token required)

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/me` | Own profile; creates the row on the first call |
| PATCH | `/me` | `display_name` (trimmed, not blank), `bio`, `status_text`, `locale`, `timezone`; only sent fields change |
| DELETE | `/me` | Soft delete (204). Idempotent |
| GET | `/{user_id}` | Public profile; 404 if missing or deleted |
| POST | `/lookup` | `{ids}` (1 to 100); returns the public profiles found, omitting unknown and deleted ids |

A deleted account gets `403` with `"error_code": "account_deleted"` on `GET`/`PATCH /me`, and lazy provisioning never
recreates or revives it. Errors use the flask-smorest format (`code`, `status`, `message`); a few also carry a stable
`error_code`.

Outbox rows (same transaction as the change, `aggregate_id` = the user id): `user.updated` with
`{user_id, display_name}` when the display name actually changes, and `user.deleted` with `{user_id}`.

## Run outside Docker (Python 3.12)

```bash
docker compose up -d --wait postgres auth-stub     # from vilu-chat/
cd user-service
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                               # database on localhost:5432
flask --app app db upgrade
flask --app app run --port 8001
```

## Tests

Needs the Postgres container and the `user_service_test` database (created by the parent init script).
`TEST_DATABASE_URL` comes from `.env`; it must point at a database whose name ends in `_test`, because
data is truncated between tests. Migrations are run (downgrade to base, then upgrade) at session start.
The auth stub is not needed: tests sign tokens with a generated RSA key and the JWKS lookup returns its public key.

```bash
pytest
```

## Configuration (environment variables)

| Variable | Purpose |
| --- | --- |
| `SQLALCHEMY_DATABASE_URI` | Database URL (role `user_svc`, database `user_service`) |
| `KEYCLOAK_ISSUER` | Compared as a string with the token's `iss` |
| `KEYCLOAK_JWKS_URL` | Where the signing keys are fetched |
| `KEYCLOAK_AUDIENCE` | Expected `aud` |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Optional, per worker; default 3 and 2 |
| `TEST_DATABASE_URL` | Tests only |

## Migrations

`flask --app app db migrate -m "..."` drafts a migration; review it by hand, then `flask --app app db upgrade`.
