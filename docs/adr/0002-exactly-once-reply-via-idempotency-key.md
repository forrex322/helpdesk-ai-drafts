# Exactly-once Reply via an Idempotency-Key

The Helpdesk sometimes answers `5xx` or times out, and after a timeout we cannot know whether it stored the Reply, so no sender-side trick alone can guarantee the Customer gets it exactly once. We retry Delivery with backoff on `5xx`, network errors and timeouts, and send a per-Ticket `Idempotency-Key` header that stays the same across retries; the Helpdesk (our mock implements this) stores the first Reply for a key and answers `201` to repeats without storing them again. We rejected "never retry after a timeout, flag for manual check" because it turns every slow Helpdesk response into Operator work.

## Consequences

- The real Helpdesk API must honour `Idempotency-Key`; this is a requirement we place on the integration, recorded here because the given API contract does not mention it.
- Approval is a conditional update from `draft_ready` to `approved`, so a double click or two Operators approving at once produce one Reply.
