# 06: Moderation: approve (with edits), reject, retry

**What to build:** On the Ticket page an Operator can edit the Draft and approve it, reject it, or retry a failed Ticket. Concurrent or repeated actions are safe: only the first one wins, the others see "already handled".

**Blocked by:** 04

**Status:** done

- [x] Approve: `draft_ready → approved`, stores edited Reply text and approving Operator
- [x] Reject: `draft_ready → rejected`
- [x] Retry: `draft_failed → new`, `send_failed → approved`
- [x] Second approval of the same Ticket does nothing and shows a message
