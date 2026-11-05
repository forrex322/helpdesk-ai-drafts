# 05: Global LLM rate limit

**What to build:** No more than `LLM_RATE_LIMIT_PER_MINUTE` (60) LLM calls start in any 60-second window across all worker threads and replicas, in both real and stub mode.

**Blocked by:** 04

**Status:** done

- [x] Sliding-window limiter in Postgres with an advisory lock; `acquire()` → go or seconds to wait
- [x] Many threads hammering the limiter never exceed the limit in a window
- [x] Worker waits for the limiter before every LLM call
