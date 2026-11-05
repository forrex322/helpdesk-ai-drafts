# Support Drafts: LLM-drafted replies with Operator moderation

**Status:** ready-for-agent

## Problem Statement

Support Operators answer every Ticket from scratch, even though most questions are already covered by the Knowledge Base. The Helpdesk can push new Tickets to a webhook, but it is impatient (2 s timeout, then it redelivers), it may deliver the same Event several times (even concurrently), it bursts up to 500 Tickets in 10 minutes, and it is unreliable when we send Replies back (`5xx`, timeouts). The LLM that could draft answers is slow (5–30 s per call) and limited to 60 requests per minute for the whole service. Tickets must never be lost, and a Customer must never receive the same Reply twice.

## Solution

A Django service that:

1. Accepts Events on `POST /webhooks/helpdesk`, stores each Ticket exactly once and answers immediately.
2. In a background worker, finds the most relevant Articles in the Knowledge Base and asks the LLM for a Draft that cites them, while staying under the global LLM rate limit.
3. Shows Operators a login-protected web interface listing Tickets and their Drafts, where they can edit and approve, or reject, each Draft.
4. Delivers each approved Reply to the Helpdesk's `reply_url`, retrying until the Helpdesk acknowledges it, without ever producing a duplicate for the Customer.

It runs with `docker compose up`, works without an LLM API key (stub mode), and ships with a mock Helpdesk and a load simulator so the whole loop can be exercised locally and on the public deployment.

## User Stories

1. As the Helpdesk, I want the webhook to answer within 2 seconds, so that I don't redeliver Events that were received.
2. As the Helpdesk, I want to get a `200` for an Event I already delivered, so that I stop retrying it.
3. As the Helpdesk, I want concurrent deliveries of the same Event to result in a single Ticket, so that the Customer is not handled twice.
4. As the Helpdesk, I want a `400` with a reason when my payload is malformed, so that I can tell bad data from an outage.
5. As the service owner, I want every Ticket committed to the database before the webhook answers, so that no Ticket is ever lost even if the worker is down.
6. As the service owner, I want bursts of 500 Tickets in 10 minutes to be accepted without slowing the webhook, so that peaks are absorbed by the queue.
7. As the service owner, I want a `/health` endpoint that answers `200 OK`, so that the platform can probe liveness.
8. As the service owner, I want Drafts generated in a background worker, so that slow LLM calls never block the webhook.
9. As the service owner, I want the worker to process many Tickets in parallel, so that a peak of ~50 Tickets/min is drafted at the LLM's pace rather than one by one.
10. As the service owner, I want all LLM calls across all worker threads and replicas to stay within 60 per minute, so that the provider never throttles us.
11. As the service owner, I want a crashed or killed worker's in-flight Tickets to be picked up again automatically, so that nothing is stuck forever.
12. As the service owner, I want failed LLM calls retried with exponential backoff and a cap on attempts, so that transient failures heal and permanent ones surface.
13. As the service owner, I want the service to work without an LLM API key, still making the real request to the provider and then substituting a static Draft after a 5–30 s delay, so that the whole system can be demoed for free.
14. As the service owner, I want the LLM model and API key configurable through environment variables, so that I can switch models without code changes.
15. As an Operator, I want each Draft grounded in the most relevant Articles, so that the answer matches our documentation.
16. As an Operator, I want the Draft to include links to the Articles it relied on, so that I can verify it and the Customer can read more.
17. As an Operator, I want to see which Articles were found for a Ticket, so that I can judge the Draft's grounding.
18. As an Operator, I want to log in before I can see or act on Tickets, so that strangers on the public deployment can't send Replies.
19. As an Operator, I want a list of Tickets with their status, newest first, so that I know what needs my attention.
20. As an Operator, I want to filter the list by status (e.g. waiting for moderation), so that I can focus on my queue.
21. As an Operator, I want to open a Ticket and see the Customer's message, email and the Draft side by side, so that I can moderate it.
22. As an Operator, I want to edit the Draft's text before approving it, so that I can fix small issues without rejecting.
23. As an Operator, I want to approve a Draft, so that it is delivered to the Customer.
24. As an Operator, I want to reject a Draft, so that it is never sent.
25. As an Operator, I want a double click or a colleague approving the same Ticket at the same time to produce only one Reply, so that the Customer never receives duplicates.
26. As an Operator, I want to be told when a Ticket was already handled by someone else, so that I don't think my action was lost.
27. As an Operator, I want to see Tickets whose drafting or Delivery gave up, with the last error, so that I can react.
28. As an Operator, I want to retry a Ticket whose drafting or Delivery failed, so that I can recover from outages without developer help.
29. As an Operator, I want to see when a Reply was delivered, so that I know the Customer has it.
30. As a Customer, I want to receive the approved Reply exactly once, even if the Helpdesk was slow or failing when it was sent, so that the conversation is not confusing.
31. As the service owner, I want Delivery retried with backoff on `5xx`, network errors and timeouts, so that Helpdesk hiccups don't lose Replies.
32. As the service owner, I want Delivery to stop and surface a `4xx`, so that a permanently rejected Reply doesn't retry forever.
33. As the service owner, I want each Delivery to carry an `Idempotency-Key` that is stable across retries, so that the Helpdesk can drop duplicates after an ambiguous timeout.
34. As a reviewer, I want a mock Helpdesk that accepts Replies, randomly fails with `5xx` or answers too slowly, and deduplicates by `Idempotency-Key`, so that I can see the retry and exactly-once behaviour.
35. As a reviewer, I want a page in the mock Helpdesk showing what each Customer actually received and how many duplicate deliveries were absorbed, so that I can verify exactly-once by eye.
36. As a reviewer, I want a command that fires N Events at the webhook with duplicates and concurrency and reports webhook latency, so that I can reproduce peak load.
37. As a reviewer, I want public Article pages, so that the links in Drafts actually open.
38. As a reviewer, I want to start everything with `docker compose up`, so that setup is one command.
39. As a reviewer, I want a README with detailed run, test and deploy instructions, so that I can evaluate the service quickly.
40. As a reviewer, I want a public deployment with the webhook and Operator interface reachable, so that I can try it without running anything.

## Implementation Decisions

- **Framework and stack**: Django 6.1, PostgreSQL 17, psycopg 3, gunicorn (threaded workers) for the web process, a management-command worker process. One Docker image, two commands (`web`, `worker`). Configuration comes from environment variables only.
- **Apps**: `tickets` (Tickets, webhook, worker, Operator UI, LLM and Helpdesk adapters), `knowledge_base` (Articles, search, public Article pages), `mock_helpdesk` (stand-in Helpdesk and load simulator).
- **Postgres is the job queue (ADR-0001)**: the Ticket row carries `status`, `available_at`, `lease_id`, `attempts` and `last_error`. Due work is `status IN (new, drafting, approved, sending) AND available_at <= now()`; for `new`/`approved`, `available_at` is the next attempt time, for `drafting`/`sending` it is lease expiry. Claiming happens in a short transaction with `FOR UPDATE SKIP LOCKED`, sets the in-flight status, a fresh `lease_id`, `available_at = now + lease`, and increments `attempts`. Every completion is a conditional update on `lease_id`; if it matches no row, the result is discarded. A partial index on `available_at` covers the due-work query.
- **Webhook contract**: `POST /webhooks/helpdesk` with JSON `{event_id, ticket_id, customer_email, message, reply_url}`. `event_id`, `ticket_id`, `message` and `reply_url` (an http(s) URL) are required; `customer_email` is accepted as given and NUL characters are dropped, because the Helpdesk does not retry a `400` and a Ticket must never be lost over a field we only display (amended after code review). Valid → insert-or-ignore on unique `event_id` → `200 {"status": "accepted"|"duplicate"}`. Invalid JSON or missing required fields → `400` with errors. No other work happens in the request. A new `event_id` with an already-known Helpdesk ticket id is a separate Ticket.
- **Worker**: `run_worker` management command, a pool of threads (default 30) each looping claim → process → sleep briefly when idle. Graceful stop on SIGTERM/SIGINT. A single `run_once()` step is the testable unit. Drafting: up to 5 attempts, backoff `min(10 s × 2^(attempt-1), 10 min)`, then `draft_failed`. Delivery: up to 8 attempts, same backoff shape, then `send_failed`; `4xx` → `send_failed` immediately.
- **LLM adapter**: one interface, `generate(ticket_message, articles) → draft text`. The Anthropic implementation uses the official SDK with SDK-level retries disabled (job-level retries own that, and SDK retries would bypass the rate limit), a request timeout, model from `LLM_MODEL` (default `claude-sonnet-5-5`). Stub mode activates when `ANTHROPIC_API_KEY` is empty: the SDK still sends a real request with a placeholder key (5 s timeout, so the call stays within 5–30 s); whatever comes back (expected `401`) is ignored and a static Ukrainian Draft that includes the found Articles' links is returned once a randomly chosen 5–30 s total duration has elapsed. In both modes, any cited Article link the Draft lacks is appended, so "Draft with links to the Articles" never rests on the prompt alone.
- **Global LLM rate limit (ADR-0003)**: sliding window of call start timestamps in Postgres, serialised by a transaction-scoped advisory lock, limit from `LLM_RATE_LIMIT_PER_MINUTE` (default 60). `acquire()` returns either "go" or the seconds to wait; the worker sleeps and retries. Applies in stub mode too.
- **Knowledge Base**: 8 short Ukrainian Articles about the Product "Звітник", seeded by a data migration. Search uses `pg_trgm` word similarity: the query is split into meaningful words (stop-words and very short tokens dropped), each word's best word-similarity against title + keywords + body is summed, Articles above a threshold are ranked, top 3 returned. Articles are public at `/kb/<slug>/`; absolute links are built from `PUBLIC_BASE_URL`.
- **Moderation**: Approval is a conditional update `draft_ready → approved` storing the (possibly edited) Reply text, the approving Operator and resetting attempts; Rejection is `draft_ready → rejected`; Retry is `draft_failed → new` or `send_failed → approved`. If the conditional update matches no row, the Operator sees "already handled".
- **Delivery and exactly-once (ADR-0002)**: `POST reply_url` with `{ticket_id, message}` and header `Idempotency-Key: <per-Ticket UUID>`, timeout `HELPDESK_TIMEOUT_SECONDS` (default 10). `201` (or any other `2xx`: the Helpdesk has the Reply, and resending after success is the one thing that must never happen) → `sent` with timestamp. `5xx`, `408`/`425`/`429`, network error, timeout → retry. Other status → `send_failed` (amended after code review).
- **Operator UI**: server-rendered Django templates, Django auth login. List (`/tickets/`, filter by status, auto-refresh), detail with message, Draft textarea, cited Articles, Approve/Reject/Retry, last error and attempts. A demo Operator is created at startup from `OPERATOR_USERNAME`/`OPERATOR_PASSWORD`.
- **Mock Helpdesk**: `POST /mock-helpdesk/tickets/<ticket_id>/replies`, fails with `503` at `MOCK_HELPDESK_FAILURE_RATE` (default 0.2) without storing, and at `MOCK_HELPDESK_SLOW_RATE` (default 0.1) stores the Reply then sleeps `MOCK_HELPDESK_SLOW_SECONDS` (default 15, above our timeout). Repeated `Idempotency-Key` → `201` without storing again, duplicate counter incremented. `/mock-helpdesk/` lists received Replies with duplicate counts. `simulate_webhooks` command posts N Events (sample Ukrainian questions) with a duplicate ratio and concurrency, and reports p50/p95/max webhook latency.
- **Deployment**: Railway, one Dockerfile, web and worker services, Railway Postgres. The same image is used locally through docker compose.

## Testing Decisions

- Good tests exercise external behaviour through the highest seam: HTTP requests through Django's test client, a single `run_once()` worker step, management commands. They assert on what an outsider sees (HTTP responses, Ticket status as shown to Operators, what the mock Helpdesk received), not on internal calls.
- Seams (agreed): (1) the HTTP boundary of the service, (2) the worker's `run_once()`, (3) the LLM and Helpdesk adapters, replaced by fakes in tests (a fake LLM implementing the interface; an `httpx.MockTransport` for the Helpdesk), (4) the global LLM rate limiter's `try_acquire()`, added after code review because its cross-replica guarantee (separate limiters sharing one budget, concurrent callers never exceeding it) cannot be observed through a single `run_once()`. The clock is passed in where time decisions are made.
- Tests run under pytest + pytest-django against real PostgreSQL (from docker compose), because `ON CONFLICT`, `SKIP LOCKED`, advisory locks and `pg_trgm` are what we rely on.
- Concurrency behaviour (concurrent duplicate Events, competing workers) is tested with real threads against the real database using transactional test cases.
- No prior art in the codebase; this spec establishes it.

## Out of Scope

- Authenticating the Helpdesk's webhook (signatures/shared secrets) and allow-listing `reply_url` hosts; noted as production hardening in the README.
- Follow-up messages within a Ticket, conversations, multiple Replies per Ticket.
- Regenerating a Draft after Rejection; Rejection is final here.
- Vector search / embeddings for the Knowledge Base.
- Roles and permissions beyond "logged-in Operator".
- UI design.

## Further Notes

- Sizing: 500 Tickets per 10 minutes is ~50/min, under the 60/min LLM limit; at up to 30 s per call that needs ~25 concurrent calls, hence 30 worker threads by default.
- Glossary: `GLOSSARY.md`. Decisions: `docs/adr/0001`–`0003`.
