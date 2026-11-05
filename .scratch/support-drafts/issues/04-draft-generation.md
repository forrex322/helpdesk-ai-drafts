# 04: Draft generation in the background worker

**What to build:** The worker picks up `new` Tickets, finds Articles, asks the LLM for a Draft citing them and stores it; the Operator sees the Draft and its Articles on the Ticket page. Works with a real Anthropic key and in stub mode without one. Failures retry with backoff, then `draft_failed`; a killed worker's Tickets are picked up again after the lease expires.

**Blocked by:** 02, 03

**Status:** done

- [x] `run_once()` claims one due Ticket (`SKIP LOCKED`, lease, fencing `lease_id`) and drafts it → `draft_ready`
- [x] Two workers never draft the same Ticket at once; an expired lease is reclaimed; a stale worker cannot overwrite
- [x] LLM failure → back to `new` with backoff and `last_error`; after 5 attempts → `draft_failed`
- [x] Anthropic adapter with SDK retries off; stub mode makes the real request, then returns a static Draft with Article links after a total of 5–30 s
- [x] `run_worker` command runs N threads and stops gracefully on SIGTERM
- [x] Ticket detail page shows message, Draft and cited Articles
