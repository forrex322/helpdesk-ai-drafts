# Support Drafts

Django service: Helpdesk webhook → LLM Draft grounded in the Knowledge Base → Operator moderation → Reply Delivery. `README.md` covers running and deploying.

## Before changing code

- Use the vocabulary in `GLOSSARY.md` (Ticket, Draft, Reply, Delivery, Operator…) in code, tests and commit messages.
- Read the ADRs in `docs/adr/` that touch the area: the job queue (0001), exactly-once Replies (0002), the LLM rate limit (0003).
- Spec and tickets live in `.scratch/support-drafts/`; how skills use them is in `docs/agents/`.

## Tests

- Postgres is required (no SQLite: we rely on `SKIP LOCKED`, advisory locks, `pg_trgm`): `docker compose up -d db`, then `.venv/bin/pytest`.
- Test at the agreed seams only: HTTP (Django test client), one worker step `Worker.run_once()`, and the LLM / Helpdesk adapters with faked transports. Assert what an Operator, the Helpdesk or a Customer would see (pages, HTTP responses, the mock Helpdesk page), not rows.
- Time is injected: pass `FakeClock` (`tests/conftest.py`) as the worker's `now`. It starts at the real time of first use; advance it after actions that stamp real time (webhook, Approval).
- Route in-process HTTP through Django's test `Client` (see `HelpdeskNetwork` in `tests/test_delivery.py`); calling the WSGI app directly closes the test's DB connection.
- Threaded tests need `@pytest.mark.django_db(transaction=True)` and `connection.close()` at the end of each thread.

## Invariants

- Every worker completion is an update fenced on `lease_id` (`Worker._complete`); a worker that lost its lease must not write.
- Every Operator decision is a conditional update from the one status it is valid in (`tickets/moderation.py`).
- Every LLM call goes through `rate_limiter.acquire()` first, in stub mode too. Keep SDK retries off.
- New per-row unique defaults (like `reply_idempotency_key`) need a data step in the migration: `AddField` evaluates a callable default once for all existing rows.

## Workflow

One branch and PR per ticket (`ticket/NN-slug`), merged with a merge commit, never squash. Commit messages close the ticket they implement.
