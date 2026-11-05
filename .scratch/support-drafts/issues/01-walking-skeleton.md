# 01: Walking skeleton: Postgres, docker compose, health, test harness

**What to build:** `docker compose up` starts Postgres, the web process and the worker process from one image; `GET /health` answers `200 OK`; settings come from environment variables; `pytest` runs against the compose Postgres.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `docker compose up` brings up db, web, worker; web waits for db and runs migrations
- [ ] `GET /health` → `200`, body `OK`
- [ ] Settings read SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DATABASE_URL and app settings from env with dev-friendly defaults
- [ ] pytest + pytest-django configured; a health test passes against Postgres
