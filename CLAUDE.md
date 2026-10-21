# CLAUDE.md

Operational rules for working in this repo. [SPEC.md](SPEC.md) and [API_SPEC.md](API_SPEC.md) are the design spec — what to build. [ROADMAP.md](ROADMAP.md) is the build order — when, and what depends on what. This file is how to build it; read all four before starting any feature.

## Repo layout
Monorepo, organized by domain (one vertical slice per resource area) rather than by layer — with ~18 resource areas in [API_SPEC.md](API_SPEC.md), a flat `models.py`/`routers.py` would be unmanageable. Each domain folder is created incrementally as [ROADMAP.md](ROADMAP.md) reaches it, not all at once.

### Root
```
/
├── CLAUDE.md  SPEC.md  API_SPEC.md  ROADMAP.md  README.md
├── docker-compose.yml
├── .gitignore
├── .github/workflows/ci.yml
├── backend/
└── frontend/
```

### `backend/`
```
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/{env.py, versions/}
├── conftest.py                  # shared fixtures: test DB, test client, user factories
├── app/
│   ├── main.py                  # FastAPI app, router registration, CORS
│   ├── config.py                # env-var settings
│   ├── database.py              # engine, SessionLocal, Base, get_db
│   ├── celery_app.py            # Celery app + beat schedule
│   ├── dependencies.py          # get_current_user, require_admin, pagination
│   ├── core/
│   │   ├── security.py          # password hashing, JWT encode/decode
│   │   ├── encryption.py        # Plaid access_token encrypt/decrypt
│   │   ├── rate_limit.py
│   │   └── errors.py            # exceptions -> {error:{code,message}} envelope
│   ├── auth/                    # §1 — User, Session
│   ├── plaid_link/               # §2
│   ├── banks/                    # §3 — Bank, Plaid_item, Institution + seed.py
│   ├── accounts/                 # §4 — polymorphic Account
│   ├── transactions/             # §5
│   ├── categories/                # §6 — + seed.py
│   ├── category_rules/            # §7 — + tasks.py (apply job)
│   ├── merchants/                 # §8
│   ├── budgets/                   # §9
│   ├── goals/                     # §10
│   ├── recurring_transactions/    # §11 — + tasks.py (scheduled detection)
│   ├── assets/                    # §12
│   ├── notifications/             # §13
│   ├── metrics/                   # §14
│   ├── dashboard/                 # §15
│   ├── reports/                   # §15
│   ├── jobs/                      # §16 infra — Job model, runner, GET /sync/jobs/{id}
│   ├── sync/                      # §16 — /sync/transactions, /sync/balances, tasks.py
│   ├── webhooks/                  # §17
│   └── admin/                     # §18 — split into sub-routers
│       ├── dependencies.py  models.py (LogEntry, AdminAuditLog, ApiToken)  audit.py  log_capture.py
│       └── users_router.py  operations_router.py  plaid_stats_router.py
│           tokens_router.py  seed_router.py  audit_router.py
├── scripts/bootstrap_admin.py     # first-admin CLI (ROADMAP 2.5)
├── Dockerfile
└── .env.example
```
Every domain folder under `app/` follows the same shape: `router.py`, `models.py` (if it owns tables), `schemas.py`, `service.py`, `tests/`.

### `frontend/`
```
frontend/
├── index.html  vite.config.ts  package.json  tsconfig.json  eslint.config.js  .env.example
├── src/
│   ├── main.tsx                  # QueryClientProvider, router
│   ├── App.tsx
│   ├── lib/{api-client.ts, query-client.ts, auth.ts}   # auth.ts: token storage + refresh interceptor
│   ├── hooks/{use-job-polling.ts, use-auth.ts}         # use-job-polling.ts: ROADMAP 3.4
│   ├── components/                # shared, feature-agnostic UI
│   ├── types/api.ts                # generated from the backend's OpenAPI spec, not hand-written
│   ├── features/
│   │   ├── auth/ accounts/ transactions/ categories/ category-rules/ merchants/
│   │   │   budgets/ goals/ recurring-transactions/ assets/ notifications/
│   │   │   dashboard/ reports/ banks/
│   │   └── admin/{users/, operations/, tokens/, audit-log/}
│   └── test/{setup.ts, mocks/handlers.ts}   # Vitest + MSW
└── Dockerfile
```
Each `features/<x>/` holds its page(s), an `api.ts` of TanStack Query hooks, local components, and colocated `.test.tsx` files.

### Defaults
Python dependency management: `uv`. Frontend package manager: `npm`. Both boring/standard, swap freely if you'd rather use poetry/pnpm — nothing above depends on which one.

## Code style
- Concise and clean: no speculative abstractions, no unused flexibility, no dead code. Three similar lines beat a premature helper. A bug fix doesn't need surrounding cleanup.
- Every non-trivial function or block gets a comment explaining what it does, not just why — write for someone reading the file cold, with no other context. Skip comments on lines that are already obvious from naming; a comment that just restates the code is worse than no comment.
- Full type coverage: type hints everywhere on the backend (mypy-clean), `strict: true` on the frontend, no `any` escape hatches without a one-line reason.
- Match the repo's formatter/linter exactly (black/ruff for Python, eslint/prettier for TS) — don't hand-format against it.

## Testing — non-negotiable
- Every feature ships with its tests in the same change, not as a follow-up.
- Backend: `pytest`. Route-level tests via FastAPI's `TestClient`/`httpx`; plain unit tests for business logic (categorization rules, balance math, recurring-bill detection, job status transitions, etc.).
- Frontend: Vitest + React Testing Library for components; mock the API at the network boundary (MSW), not by stubbing individual fetch calls.
- Every write route gets an authorization test: a second user's token must get 403/404, never a silent success. This is the single highest-value test category in the app — see [SPEC.md §6](SPEC.md#6-security-baseline-non-negotiable-from-day-one).
- The auth flow (login → refresh → rotation → theft-detection revocation) has its own integration suite, not just route-level smoke tests.
- Nothing is "done" until `pytest` (backend) and the frontend test runner both pass, with no tests skipped or stubbed out to fake coverage.

## Security — non-negotiable
Full baseline: [SPEC.md §6](SPEC.md#6-security-baseline-non-negotiable-from-day-one). Restated here because it's the easiest thing to erode under time pressure:
- Every write route resolves the acting user from the verified token. Never trust a client-supplied `user_id`/`account_id` for authorization — only for addressing, and always check ownership afterward.
- No secrets in git, ever — see Git rules below for how that's enforced.
- No secrets or tokens in logs, not even partially — if a log line must reference one, mask to the last 4-5 chars.
- `Plaid_item.access_token` is encrypted at rest (reversible, the app decrypts and reuses it). `Session`/`ApiToken` secrets are hashed (one-way, verify-only). Don't use the wrong one for either.

## Git
- Work on a feature branch per unit of work, cut from `main` (`feat/<slug>`, `fix/<slug>`, `chore/<slug>`) — don't commit directly to `main`.
- Standing authorization: commit as you go on the feature branch, without waiting to be asked each time. The moment a logical unit of work is complete and passing (one migration, one endpoint, one component, one bug fix), commit it before moving to the next one — don't let finished work sit uncommitted while you continue to other changes. This overrides the general "ask before committing" default for this repo specifically.
- Don't let changes pile up across multiple unrelated pieces of work before committing any of them — if you notice several completed-but-uncommitted changes already sitting in the working tree when you start, commit them (split appropriately per the atomicity rule below) before adding more on top.
- No secrets in git, ever — not in a commit, not in history. Any file that can hold one (`.env`, `*.pem`, downloaded service-account JSON, local credential overrides, etc.) goes into `.gitignore` before it's ever created, not added after the fact.
- If a secret is ever committed anyway, treat it as compromised immediately and rotate it — deleting the line in a later commit does not remove it from history.
- Before committing, check what's actually staged (`git status` / `git diff --cached`) rather than `git add -A` on autopilot. This is what actually catches a stray secret or accidental file before it's in history, not after.
- Commit frequently and atomically: each commit is one complete, reviewable change — one migration, one endpoint, one component — small enough that `git revert` on it cleanly undoes just that change and nothing else.
- Don't bundle unrelated changes into one commit (e.g. a feature plus an unrelated formatting pass); split them so each stays independently revertable.
- Every commit should leave the repo in a working state (tests pass). Reversibility only holds if the commit you'd revert *to* also worked.
- When the branch's work is complete and passing (see Definition of done below), merge it into `main` locally. This local merge is covered by the same standing authorization as commits — no need to ask first. Delete the merged branch locally afterward to keep the branch list clean.
- Standing authorization also covers pushing: once a unit of work is complete and passing (same bar as the commit/merge rules above), push `main` (after the local merge) to `origin` without waiting to be asked each time. Force-pushing or amending a published commit are not covered by this — those still follow the normal confirm-first rules: ask in chat and get an explicit go-ahead each time before either.

## Don't do this
Domain-specific traps this app invites, not generic advice:
- Don't call out to Plaid without checking `plaid_enabled` and `monthly_call_limit` first — see [API_SPEC.md §18](API_SPEC.md#18-admin). An admin-disabled or over-limit user must get 403/429, never a successful call that bypasses the control.
- Don't invent a new async/polling mechanism for a slow operation — route it through the existing job/polling contract ([API_SPEC.md §16](API_SPEC.md#16-sync--background-jobs)). One status-polling pattern, not several.
- Don't let an `/admin/*` route return another user's transactions, balances, or other financial data — admin access is metadata/operational only (see [API_SPEC.md §18](API_SPEC.md#18-admin)). If a route is tempted to add this, stop and flag it instead of building it.
- Don't serve infra secrets (DB password, Plaid secret, JWT signing key) over any API response, including admin ones.
- Don't write a hashed secret where the raw value needs to be reused later (Plaid's `access_token`), or an encrypted one where only verification is ever needed (`Session`/`ApiToken`) — see Security above.
- Don't add a shared/household ownership model "just in case" — it's explicitly deferred (see [SPEC.md §7](SPEC.md#7-open-questions--next-steps)); every record stays scoped to a single `owner_id` until that's revisited on purpose.

## Definition of done
Before calling any task finished:
- [ ] Tests exist for the change and pass (`pytest` / frontend test runner) — no skips standing in for coverage.
- [ ] New or touched write routes have an ownership/authorization test (wrong user's token → 403/404).
- [ ] Type checks pass (mypy / `tsc --strict`) and the formatter/linter is clean.
- [ ] No secrets, tokens, or credentials were added to git, logs, or an API response.
- [ ] If the implementation deviated from SPEC.md/API_SPEC.md, the specs were updated to match — not left stale.

## Working process
- If anything in the specs is ambiguous, underspecified, or turns out to be wrong once you're implementing it, stop and ask rather than guessing and moving on.
- Update [SPEC.md](SPEC.md)/[API_SPEC.md](API_SPEC.md) if implementation reveals the design needs to change — the specs should stay accurate, not go stale the moment code starts.

## Task visibility — non-negotiable
- Any request with more than one step gets a tracked task list (the task-tracking tool), created before work starts — not retrofitted after the fact, and not skipped because the work "looks small" if it turns out to have multiple steps.
- Keep it current in real time: mark each item completed the moment it's done, not in a batch at the end. Add items if scope grows mid-task instead of letting new work go untracked.
- Show the full list and every item's status (pending/in-progress/completed) — not just whichever one is currently active — at the start of multi-step work, after any status change worth flagging, and whenever asked what's being worked on. Silently grinding through steps with no visible list is the failure mode this rule exists to prevent.
