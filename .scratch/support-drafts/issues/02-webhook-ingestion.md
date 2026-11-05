# 02: Webhook ingestion with dedup, visible to Operators

**What to build:** The Helpdesk posts Events to `POST /webhooks/helpdesk`; each Event becomes exactly one Ticket (even under concurrent duplicates), answered within the 2 s budget. A logged-in Operator sees the new Tickets in a list at `/tickets/`.

**Blocked by:** 01

**Status:** done

- [x] Valid Event → `200 {"status": "accepted"}` and a `new` Ticket
- [x] Same `event_id` again (also concurrently from many threads) → `200 {"status": "duplicate"}`, still one Ticket
- [x] Malformed JSON / missing fields / bad email / non-http reply_url → `400` with errors, nothing stored
- [x] `/tickets/` requires login; lists Tickets newest first with status; filter by status
- [x] Demo Operator created from `OPERATOR_USERNAME`/`OPERATOR_PASSWORD` by a startup command
