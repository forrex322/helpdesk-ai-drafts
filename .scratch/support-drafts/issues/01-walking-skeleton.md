# 01: Walking skeleton: Postgres, docker compose, health, test harness

**What to build:** `docker compose up` starts Postgres, the web process and the worker process from one image; `GET /health` answers `200 OK`; settings come from environment variables; `pytest` runs against the compose Postgres.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `docker compose up` brings up db, web, worker; web waits for db and runs migrations
- [x] `GET /health` → `200`, body `OK`
- [x] Settings read SECRET_KEY, DEBUG, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DATABASE_URL and app settings from env with dev-friendly defaults
- [x] pytest + pytest-django configured; a health test passes against Postgres
