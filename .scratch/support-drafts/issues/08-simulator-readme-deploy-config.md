# 08: Load simulator, README, deploy config

**What to build:** `simulate_webhooks` fires N Events with duplicates and concurrency at any base URL and reports webhook latency; README explains running, testing, simulating and deploying (in Ukrainian); Railway config is ready; CLAUDE.md points agents at the glossary, ADRs, spec and test commands.

**Blocked by:** 07

**Status:** done

- [x] `simulate_webhooks --count 500 --duplicate-rate 0.3 --concurrency 20` works locally and against the deployment
- [x] README: architecture, run with docker compose, env vars, tests, simulator, deployment, design decisions
- [x] Railway config for web and worker
- [x] CLAUDE.md committed
