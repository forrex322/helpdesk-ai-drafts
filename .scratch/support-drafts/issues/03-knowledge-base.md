# 03: Knowledge Base: seeded Articles, search, public pages

**What to build:** 8 Ukrainian Articles about "Звітник" exist after migrations, are readable at `/kb/<slug>/`, and a search returns the most relevant Articles for a Customer's message (e.g. "Не можу експортувати звіт у PDF" → the PDF export Article first).

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Data migration seeds 8 Articles; `pg_trgm` enabled by migration
- [ ] `/kb/` lists Articles, `/kb/<slug>/` shows one (public, no login)
- [ ] Search returns at most 3 Articles ranked by relevance, nothing for an unrelated message
- [ ] Absolute Article links are built from `PUBLIC_BASE_URL`
