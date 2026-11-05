# Postgres is the job queue

The Helpdesk waits at most 2 s for the webhook, while one LLM call takes 5–30 s, so drafting must happen in the background. Instead of adding Celery and Redis, the `tickets` table itself is the queue: the webhook only commits the Ticket and answers, and a separate worker process claims due Tickets with `SELECT … FOR UPDATE SKIP LOCKED` in a short transaction, holding a time-limited lease (`available_at` plus a fencing `lease_id`) instead of an open transaction while it calls the LLM or the Helpdesk.

## Considered Options

- **Celery + Redis**: a second datastore to run, deploy and keep consistent with Postgres, so a Ticket could be committed but never enqueued, or the reverse.
- **`django.tasks` (Django 6)**: no production backend ships with Django; the database backend is a third-party package, and we'd still need our own leases and retries.

## Consequences

- A Ticket is durable the moment the webhook answers `200`, so Tickets are never lost; a crashed worker's leases expire and another worker picks the Ticket up.
- A worker that loses its lease (because it was too slow) cannot overwrite the new owner's result: every completion is a conditional update on `lease_id`.
- Throughput comes from threads in the worker (default 30, sized for 50 Tickets/min at up to 30 s per LLM call) and from running more worker replicas.
