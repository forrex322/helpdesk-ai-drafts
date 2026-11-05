# 07: Reply Delivery and the mock Helpdesk

**What to build:** Approved Replies are delivered to `reply_url` with a stable `Idempotency-Key`, retried on `5xx`/timeouts, and the Customer (as seen in the mock Helpdesk) receives each Reply exactly once. The mock Helpdesk randomly fails and stalls, deduplicates by key, and shows what Customers received.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] Worker delivers `approved` Tickets: `201` → `sent` with timestamp; `5xx`/timeout/network error → retry with backoff; other `4xx` → `send_failed`; 8 attempts max
- [ ] Mock `POST /mock-helpdesk/tickets/<id>/replies` with configurable failure and slow rates; duplicate key → `201`, not stored twice, counter incremented
- [ ] `/mock-helpdesk/` shows received Replies and duplicate counts
- [ ] End-to-end test: flaky mock + retries → exactly one stored Reply
