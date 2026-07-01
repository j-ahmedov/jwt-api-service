# JWT API Service (SEC25)

A RESTful service secured with **JWT authentication** and **role-based access
control (RBAC)**, built with FastAPI + async SQLAlchemy + PostgreSQL.

This project implements the SEC25 brief: *"JWT (JSON Web Token) API on RESTful
service"* — generating and validating JWTs, securing endpoints, enforcing
role-based access control, integrating into a REST service, and evaluating the
result for performance, security, and scalability.

---

## 1. Setup & run

```bash
# 1. Dependencies
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # runtime
pip install -r requirements-dev.txt      # + test tooling

# 2. Configuration
cp .env.example .env                     # then edit values
#   - DATABASE_URL : postgresql+asyncpg://<user>[:<pw>]@localhost:5432/jwt_api_db
#   - SECRET_KEY   : python3 -c "import secrets; print(secrets.token_hex(32))"
#   - ADMIN_*      : bootstrap admin, seeded on first start if no admin exists

# 3. Create the database, then run
createdb jwt_api_db
uvicorn main:app --reload
```

Interactive API docs (Swagger): http://127.0.0.1:8000/docs

---

## 2. Architecture

```
main.py            FastAPI app, CORS, router mounting, lifespan -> init_db()
config.py          Typed settings loaded from .env
database.py        Async engine + ORM models + table creation + admin seed
auth/
  jwt_handler.py   create / decode access & refresh tokens
  password.py      bcrypt hash / verify
  dependencies.py  get_current_user / require_admin (the auth gate)
models/            Pydantic request/response schemas + Role enum
routes/
  auth.py          register, login, refresh (rotation), logout (revocation)
  users.py         /users/me, /users/ (admin), PATCH /users/{id}/role (admin)
  items.py         item CRUD; delete is admin-only
tests/             pytest suite (auth, RBAC, items)
scripts/benchmark.py   load/latency benchmark
```

**Token model.** Two HS256-signed token types carrying
`sub` (user id, string per RFC 7519), `role`, `jti` (unique id for revocation),
`iat`, `exp`, and `type` (`access` | `refresh`). Access tokens (30 min) authorize
endpoints; refresh tokens (7 days) mint new access tokens and are **single-use**
(rotated on every refresh). Revoked `jti`s are stored in `revoked_tokens`.

---

## 3. Requirement coverage (SEC25 objectives a–e)

| # | Objective | Where |
|---|-----------|-------|
| a | Generate & validate JWTs | `auth/jwt_handler.py`, `auth/dependencies.py` |
| b | Secure token-based auth for endpoints | `HTTPBearer` + `get_current_user` on protected routes |
| c | Access control from token attributes & roles | `require_admin`, `Role` enum, admin-only routes |
| d | Integrate into the REST service | `/auth`, `/users`, `/items` routers + DI, PostgreSQL persistence |
| e | Evaluate performance, security, scalability | §4–§6 below + `tests/` + `scripts/benchmark.py` |

---

## 4. Security evaluation

**Implemented controls**

| Threat | Mitigation |
|--------|------------|
| Password disclosure (DB dump) | bcrypt hashing, cost 12, per-password salt; hashes never returned in any response |
| Token forgery / tampering | HS256 signature verified on every request; payload shape validated |
| Token reuse after logout | `jti` revocation blacklist checked on every protected request |
| Refresh-token replay / theft | Single-use refresh rotation — old `jti` revoked when refreshed |
| Token-type confusion | Explicit `type` check (an access token can't refresh; a refresh token can't access) |
| Privilege escalation at registration | Public `/auth/register` always creates `role=user`; role can't be self-assigned |
| Privilege escalation via API | Role changes only via admin-only `PATCH /users/{id}/role`; admin can't self-demote |
| Disabled accounts | `is_active` re-checked on every request, not just at login |
| Secret leakage | `SECRET_KEY`, DB URL, admin creds in `.env` (gitignored); none hardcoded |
| Input abuse | Pydantic validation (username alphanumeric ≥3, password ≥8) |

**Known limitations / hardening backlog**

- **No rate limiting / lockout** on `/auth/login` → brute-force possible. Add a
  reverse-proxy or slowapi-style limiter.
- **CORS is wide open** (`allow_origins=["*"]`) — fine for dev, must be
  restricted in production.
- **HS256 shared secret** — anyone able to verify can also sign. For multi-service
  verification, move to **RS256** (private key signs, public key verifies).
- **Revocation table grows unbounded** — see §6.
- No refresh-token reuse *detection* (rotation revokes the old token, but a
  detected reuse doesn't invalidate the whole token family).

---

## 5. Performance evaluation

Measured with `scripts/benchmark.py` against a single `uvicorn` worker,
local PostgreSQL 14 (Apple Silicon), 200 requests at concurrency 20:

| Endpoint | Throughput | p50 | p95 | p99 |
|----------|-----------:|----:|----:|----:|
| `GET /users/me` (token verify + indexed query) | **~580 req/s** | 25 ms | 76 ms | 116 ms |
| `POST /auth/login` (bcrypt verify) | **~6 req/s** | 2.7 s | 6.4 s | 10.9 s |

**Key finding.** The token-validation path is fast and scales well. The login
path is ~100× slower because **bcrypt (cost 12) is a synchronous, CPU-bound call
executed directly inside an `async def` route — it blocks the event loop**, so
concurrent logins serialize behind a single thread. This is by design for
hashing cost, but blocking the loop is an architectural issue.

**Recommended fix.** Offload bcrypt to a thread pool so the event loop stays free:

```python
# auth/password.py — verify in a worker thread
import asyncio, bcrypt
async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(bcrypt.checkpw, plain.encode(), hashed.encode())
```

(Then `await verify_password(...)` in the login route.) This keeps per-login cost
the same but lets concurrent logins run in parallel across CPU cores, and stops
login latency from starving every other endpoint. Tune the bcrypt cost factor to
your latency budget.

---

## 6. Scalability evaluation

**Scales well**

- **Stateless auth** — access tokens are self-contained; any instance can verify
  them with the shared secret, so the API tier scales horizontally behind a load
  balancer with no sticky sessions.
- **Async I/O + connection pooling** — non-blocking DB access handles many
  concurrent token-validation requests per worker (≈580 req/s above).

**Bottlenecks & remedies**

| Bottleneck | Impact | Remedy |
|------------|--------|--------|
| Synchronous bcrypt in async route | Login throughput collapses, blocks loop | Offload to thread pool (§5); run multiple `uvicorn` workers |
| Revocation check hits Postgres every request | Extra query per request; table grows forever | Move blacklist to **Redis with TTL = token lifetime** (auto-expiry, O(1) lookup) |
| `revoked_tokens` never pruned | Unbounded growth | TTL/Redis, or a periodic cleanup of entries past `exp` |
| Single shared HS256 secret | All instances share one signing key | RS256 for asymmetric verify; rotate keys via `kid` header |
| Single worker | One CPU core | `uvicorn --workers N` or run behind Gunicorn; horizontal scale |

---

## 7. Testing

```bash
createdb jwt_api_test          # one-time
pytest                         # 26 tests: auth, RBAC, items
```

The suite recreates the schema before each test for isolation and covers token
generation/validation, refresh rotation, logout revocation, token-type
confusion, RBAC enforcement, privilege-escalation hardening, and item CRUD.
