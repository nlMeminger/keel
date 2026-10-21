# Roadmap

Sequencing and dependencies for building what [SPEC.md](SPEC.md) and [API_SPEC.md](API_SPEC.md) describe. Those two documents are the *what*; this one is *in what order, what's blocking what, and how to know each piece is actually done*. Follow [CLAUDE.md](CLAUDE.md)'s rules while executing any item below.

## How to read this
- **Depends on** = a hard, code-level prerequisite. The item literally cannot be built (or tested) before that one exists.
- **Blocked by** = an external resource or open decision — not code, something that has to happen or be decided outside this repo.
- **Success** = a concrete, checkable condition — something you can verify is true or false, not a vibe. If an item's success criterion can't be checked by running something (a test, a request, a query), it isn't specific enough.
- **Failure** (where present) = the explicit error/edge-case handling the item must cover — what happens on bad input, a missing/foreign id, or an upstream failure — checked the same way as Success (a test or request you can actually run), not just "don't crash."
- Phase numbers are the recommended build order, not a strict wall: two items with no dependency on each other can be built in parallel or swapped, and it's called out below where that's true.
- Each phase also has **exit criteria** — the integration-level check that the phase as a whole is done, beyond its individual items.

## Open decisions (blockers not tied to one phase)
- **D1 — Component library.** Resolved: Mantine ([SPEC.md §3](SPEC.md#3-architecture)). No longer blocks styling of any frontend item below.
- **D2 — Deployment target** (self-host vs cloud, [SPEC.md §7](SPEC.md#7-open-questions--next-steps)). Doesn't block local dev (Docker Compose covers that); needed before Phase 9.
- **D3 — Plaid developer account + sandbox API keys.** Nothing in Phase 7 can be built or tested without this. Unlike D1/D2, this has external lead time (signup/approval) — worth starting now even though Phase 7 is late, so it's ready when you get there.

---

## Phase 1 — Environment & scaffolding
Goal: both apps boot locally against real Postgres + Redis, with CI running a (currently empty) test suite.

- **1.1 — Backend skeleton.** FastAPI app, SQLAlchemy engine/session, Alembic configured, `GET /health`.
  - Depends on: —
  - Success: `uvicorn` boots the app locally with no errors; `GET /health` returns `200`; `alembic upgrade head` runs cleanly against a fresh database.
- **1.2 — Frontend skeleton.** Vite + React + TS, ESLint/Prettier, TanStack Query provider, router stub.
  - Depends on: —
  - Success: `npm run dev` serves a page with zero console errors; `npm run lint` and `npm run build` both pass untouched.
- **1.3 — Docker Compose.** Postgres, Redis, backend, frontend, all boot with one command.
  - Depends on: 1.1, 1.2
  - Success: `docker compose up` from a clean checkout brings up all four services with no manual steps; `GET /health` is reachable from the host.
- **1.4 — CI pipeline.** Backend tests + frontend tests + lint/type-check for both, on every push.
  - Depends on: 1.1, 1.2
  - Success: a pushed branch shows green on all four jobs; a deliberately broken test or lint rule on a throwaway branch turns the run red.
- **1.5 — `.env.example` + `.gitignore`.** Covers every secret-bearing file pattern per [CLAUDE.md](CLAUDE.md) Git rules.
  - Depends on: 1.1, 1.2
  - Success: a locally-created `.env` shows as ignored in `git status`, not untracked-but-visible; nothing but placeholder values exists in the example files.

**Exit:** `docker compose up` boots everything; CI is green on an empty app.

## Phase 2 — Auth & tenancy foundation
Goal: register → log in → authenticated request → refresh → logout works, and every later route has a proven ownership-check pattern to copy.

- **2.1 — `User` model + migration.** Includes `role`, `status`, `plaid_enabled`, `plaid_monthly_call_limit`, `must_change_password` now, even though admin routes come later, to avoid a second migration.
  - Depends on: 1.1
  - Success: `alembic upgrade head` creates `users` with correct defaults (`role='user'`, `status='active'`, `plaid_enabled=true`, `plaid_monthly_call_limit=NULL`); inserting a user with just email/password/name yields sane defaults for the rest.
- **2.2 — `Session` model + migration.** `family_id`, `token_hash`, `revoked_at`, etc.
  - Depends on: 1.1
  - Success: the table exists with an index on `token_hash` so lookups aren't a table scan.
- **2.3 — Auth routes.** Register, login, refresh (rotation + theft detection), logout, sessions list/revoke, me (get/patch).
  - Depends on: 2.1, 2.2
  - Success: an integration test walks register → login → `GET /auth/me` → refresh (old refresh token now rejected) → logout (further refresh with that token 401) — all green in one run.
- **2.4 — Ownership-check dependency.** Used by every future write route.
  - Depends on: 2.3
  - Success: a test calling it with another user's valid token returns *that* user's identity — provably scoped per-token, not a cached/global lookup.
- **2.5 — Admin-bootstrap CLI.** One-time first-admin creation, not an API route ([API_SPEC.md §18](API_SPEC.md#18-admin)).
  - Depends on: 2.1
  - Success: running it against an empty database creates exactly one `role='admin'` user; running it again doesn't silently create an unaudited second admin.
- **2.6 — Rate limiting** on login/register/refresh ([SPEC.md §6](SPEC.md#6-security-baseline-non-negotiable-from-day-one) starting numbers).
  - Depends on: 2.3
  - Success: a test firing 6 login attempts for the same IP+username inside 15 minutes gets a 429 on the 6th; a legitimate attempt after the window resets succeeds.
- **2.7 — Frontend auth screens.** Login, register, session management, token storage + refresh interceptor, protected-route wrapper.
  - Depends on: 2.3, 1.2
  - Success: a user can register/log in through the actual UI, stay logged in across a token-expiry refresh with no visible interruption, and logging out clears client state and redirects.

**Exit:** the full auth loop works end-to-end, with a passing test proving a second user's token can't touch the first user's `/auth/me`.

## Phase 3 — Background job infrastructure
Goal: the job/polling contract ([API_SPEC.md §16](API_SPEC.md#16-sync--background-jobs)) exists and is proven before anything real depends on it.

- **3.1 — Celery + Redis wiring** (worker, beat).
  - Depends on: 1.3
  - Success: both processes start cleanly against the Compose Redis instance; a trivial enqueued task executes and its result is retrievable.
- **3.2 — `Job` status table + generic job-runner wrapper.**
  - Depends on: 3.1, 2.1
  - Success: wrapping a task that deliberately raises leaves a `Job` row with `status='failed'` and a populated `error` field — not a swallowed exception, not an unhandled 500.
- **3.3 — `GET /sync/jobs/{job_id}`.**
  - Depends on: 3.2
  - Success: polling immediately after triggering returns `pending`/`running` with progress; polling after completion returns a terminal status exactly once, with no flapping back to `running`.
- **3.4 — Frontend job-polling hook** (2s→10s backoff, reusable by any job-returning action).
  - Depends on: 3.3, 2.7
  - Success: triggering a job-returning action shows a live in-progress state with no page reload, and clears itself at the terminal state without a tight poll loop.

Note: Phase 3 has no dependency on Phase 4 and vice versa — swappable or parallelizable. Sequenced here so the job pattern is proven on a trivial job before Phase 5/7 need it for real.

**Exit:** a trivial job can be triggered, polled to completion, and rendered in the UI.

## Phase 4 — Manual-first financial core
Goal: every core feature works fully on manually-entered data. **This is the milestone that proves [SPEC.md](SPEC.md)'s "works without Plaid" goal by construction, not assertion.**

- **4.1 — `Account` model + migration** (single table: `account_type` discriminator + `detail` JSONB column — not sibling tables, not SQLAlchemy inheritance; see [SPEC.md §5](SPEC.md#5-data-model-notes)).
  - Depends on: 2.1
  - Success: a checking account and a mortgage account both persist through the same table, with mortgage-specific fields readable straight off `detail` with no second query or join; a `detail` payload that doesn't match its `account_type`'s Pydantic schema is rejected at the API layer before it reaches the database.
- **4.2 — Accounts CRUD routes** (manual only).
  - Depends on: 4.1, 2.4
  - Success: full create/read/update/delete works via the API; a second user's token addressing the first user's account id gets 404.
- **4.3 — `Category` model + seed migration/CLI.**
  - Depends on: 1.1
  - Success: seeding populates system categories with `owner_id IS NULL`, including the seeded "Transfer" category used by 4.13's pairing detection; running the seed twice doesn't duplicate rows.
- **4.4 — Categories CRUD routes.**
  - Depends on: 4.3, 2.4
  - Success: a user can create a custom category; `PATCH`/`DELETE` on a system category returns 403; deleting a category still referenced by a transaction returns 409 unless `reassign_to` is supplied, in which case the transaction's category updates and the delete succeeds.
- **4.5 — `Transaction` model + migration.**
  - Depends on: 4.1, 4.3
  - Success: a transaction links correctly to both an account and a category, with the amount-sign convention (inflow vs. outflow) covered by at least one test.
- **4.6 — Transactions CRUD + search routes.**
  - Depends on: 4.5, 2.4
  - Success: combined filters (`account_id` + `date_from/to` + `amount_min/max`) return exactly the expected subset on a seeded dataset built to have both matches and non-matches; pagination defaults/max are enforced.
- **4.7 — `Merchant` model + CRUD.**
  - Depends on: 1.1, 2.4
  - Success: a merchant alias can be created and assigned to a transaction; ownership-scoping test passes.
- **4.8 — `Metrics` model + CRUD + bulk routes.**
  - Depends on: 4.1
  - Success: a `credit_score` entry and a free-form `type` entry both persist with just `{type, value, date}`; `POST /metrics/bulk` with 50 entries creates all 50 in one request.
- **4.9 — Auto-write Metrics on balance/value change.**
  - Depends on: 4.2, 4.8, 4.12
  - Success: patching a manual account's balance twice produces two new `account_balance` Metrics rows, not one overwritten row; patching an asset's `current_value` twice produces two new `asset_value` Metrics rows the same way — both verified by a test asserting the count.
- **4.10 — `Budget` model + CRUD.**
  - Depends on: 4.3, 4.6
  - Success: logging a transaction in a budgeted category updates that budget's spend-so-far on the next `GET`, with no separate manual recompute step; a transaction later confirmed as a transfer (4.13) drops out of spend-so-far on the next `GET` without the budget being edited.
- **4.11 — `SavingsGoal` + contributions.**
  - Depends on: 2.1
  - Success: two contributions update the goal's progress total correctly, visible on `GET /goals` without a separate contributions fetch.
- **4.12 — `Asset` model + CRUD.**
  - Depends on: 2.1
  - Success: CRUD + ownership test pass in isolation (net-worth inclusion is verified later, in 6.1/6.2).
- **4.13 — Transfer-pair detection.**
  - Depends on: 4.6
  - Success: two manually-entered transactions on two of the same user's accounts, opposite-sign, same amount, dated within 2 business days of each other, come back from the detection pass with `transfer_status=suggested` and linked `paired_transaction_id`s; confirming via `PATCH /transactions/{id}` sets `is_transfer=true` on both, assigns the seeded "Transfer" category to both, and a third account belonging to a *different* user is never considered a candidate even when amount/date coincidentally match.
- **4.14 — `Holding` model + manual holdings CRUD.**
  - Depends on: 4.1
  - Success: a manual investment account accepts a hand-entered holding (symbol, quantity, cost basis) via the API; the same routes return 403 against a Plaid-linked account's holdings (those are sync-populated, proven for real once 7.3 lands).
- **4.15 — Frontend screens** for Accounts (incl. Holdings), Transactions (incl. transfer suggestion review), Categories, Merchants, Budgets, Goals, Assets.
  - Depends on: matching backend item + 2.7
  - Success: for every resource, a full CRUD loop is completable through the UI alone — create, see it listed, edit, delete, list updates without a manual refresh; a suggested transfer pair is visibly reviewable and confirming/rejecting it updates both transactions without a page reload.

**Exit:** a brand-new user with zero Plaid connections can create accounts (with manual holdings on an investment account), log and categorize transactions, confirm a detected transfer pair, set budgets and goals, track assets, and log a manual metric — entirely through the UI.

## Phase 5 — Automation layer
Goal: features that act on the core data, not just store it.

- **5.1 — `CategoryRule` model + CRUD + test + apply routes** (`apply` runs through Phase 3's job infra).
  - Depends on: 4.4, 4.6, 3.2
  - Success: `/category-rules/test` on a rule shows matching uncategorized transactions without changing them; `/category-rules/apply` actually updates their category and its job reaches `succeeded` with a match count in the result.
- **5.2 — `RecurringTransaction` model + CRUD + payments route** (manual entry only — no auto-detection in this phase, see Deferred section).
  - Depends on: 4.6
  - Success: a user can create a recurring item by hand, and recording a payment against it updates its "last paid" state, visible on the next `GET`.
- **5.3 — `Notification` model + CRUD.**
  - Depends on: 2.1
  - Success: create/list (with `unread_only`)/mark-read/dismiss all work and are scoped per-user.
- **5.4 — Budget/goal threshold notifications.** Crossing a budget usage threshold or a savings-goal progress milestone creates a `Notification` row, checked inline at the relevant transaction/contribution write path (see [API_SPEC.md §9](API_SPEC.md#9-budgets)/[§10](API_SPEC.md#10-savings-goals)) — not a new scheduled job.
  - Depends on: 4.10, 4.11, 5.3
  - Success: a transaction that pushes a budget's spend-so-far past 90% (and, separately, past 100%) creates exactly one new unread notification per threshold crossed, not a duplicate on a later `GET`/re-check; a contribution that pushes a goal past 50%/100% does the same.
- **5.5 — Frontend screens** for Category Rules, Recurring Transactions/Bills, Notifications (including the threshold notifications from 5.4).
  - Depends on: matching backend item
  - Success: a user can create/view/edit a recurring transaction and log a payment against it, and create/view a notification, entirely through the UI.

**Exit:** a rule auto-categorizes a new transaction; a user can manually track a recurring bill and log payments against it through the UI; crossing a budget or goal threshold produces a visible notification for a manual-only user with zero Plaid connections. (Auto-detection + notification wiring for recurring *bill* reminders specifically is deferred — see Deferred section at the end of this document.)

## Phase 6 — Dashboard & Reports
Goal: everything built so far becomes visible as one picture.

- **6.1 — `GET /dashboard/summary`.**
  - Depends on: 4.2, 4.6, 4.8, 4.10
  - Success: for a seeded test user, one call returns net worth, this-month in/out, recent transactions, and budget status, with values matching numbers computed independently in the test — not just a 200.
- **6.2 — Balance-history / net-worth-history.**
  - Depends on: 4.8, 4.9, 4.12
  - Success: `granularity=month` net worth for a manual-only user matches a hand-computed expectation from the seeded Metrics rows (accounts *and* assets) across two consecutive months.
- **6.3 — Cash-flow / spending-by-category.**
  - Depends on: 4.6, 4.13
  - Success: a date range with known inflows/outflows returns totals matching a manual computation; a confirmed transfer pair is excluded from both reports even though its underlying transactions still carry the "Transfer" category and are visible in the plain transaction list.
- **6.4 — Credit-health.**
  - Depends on: 4.2, 4.8
  - Success: one response includes both computed utilization and credit-score history for a seeded credit-card account + credit-score metric.
- **6.5 — Investments report** (shape + manual holdings now; Plaid-sourced holdings after 7.3).
  - Depends on: 4.14 (shape + manual data); 7.3 (Plaid data)
  - Success now: returns correct per-holding performance for a user with manually-entered holdings, and an empty-but-correctly-shaped response for a user with none, rather than erroring.
- **6.6 — Frontend dashboard/report views.**
  - Depends on: matching backend item
  - Success: a brand-new manual-only user's dashboard shows real, non-placeholder numbers — zeros/empty states are fine, broken requests or `undefined` in the UI are not.

**Exit:** dashboard renders a sensible, non-empty view using only Phase 4 manual data, proving reports don't secretly require Plaid.

## Phase 7 — Plaid integration
Goal: bank-linked accounts work end to end, as an addition to the manual-first core, not a replacement for it.

**Blocked by: D3** for every item below — nothing here can be built or tested without Plaid sandbox credentials.

- **7.1 — `Plaid_item` and `Bank` models + migrations.**
  - Depends on: 2.1
  - Success: a Bank can exist with a linked Plaid_item and zero accounts yet (link succeeded, accounts not pulled) without constraint errors.
- **7.2 — Plaid Link routes** (link-token, link-token/update, exchange-token).
  - Depends on: 7.1, D3
  - Success: using real sandbox credentials, a Link token is created, a sandbox institution is linked through Plaid's test flow, and `exchange-token` produces a real access token stored against a new Bank.
- **7.3 — Plaid-linked Accounts + Banks CRUD** (incl. investment holdings).
  - Depends on: 4.1, 7.1, 4.14
  - Success: after linking a sandbox bank, `GET /accounts` shows Plaid-pulled accounts alongside manual ones from Phase 4, in the same list; a sandbox investment account's holdings populate the same `Holding` table 4.14 built for manual entries, read-only.
- **7.4 — Sync jobs + manual trigger routes.**
  - Depends on: 3.2, 7.3
  - Success: `POST /banks/{id}/sync` returns a job id; polling it to completion results in new/updated transactions visible in `GET /transactions`.
- **7.5 — Scheduled sync via Celery beat.**
  - Depends on: 7.4
  - Success: without any manual trigger, a sandbox account's balance updates on its own within one scheduled interval after the underlying sandbox data changes.
- **7.6 — `PlaidAPICall` logging.**
  - Depends on: 7.2
  - Success: after several sandbox calls, querying the table shows one row per actual call with correct endpoint/user attribution.
- **7.7 — `Plaid_item.access_token` encryption at rest.**
  - Depends on: 7.1
  - Success: the raw database row shows an encrypted value, not plaintext; the app still successfully makes a live Plaid call using the decrypted value.
- **7.8 — Inbound webhook + `Plaid-Verification` check.**
  - Depends on: 7.1
  - Success: a request with a missing/invalid verification header is rejected before any processing; a validly-signed test webhook triggers the expected side effect (e.g. a sync job enqueued).
- **7.9 — Frontend Plaid Link flow.**
  - Depends on: 7.2, 7.3
  - Success: a user can link a sandbox bank through the UI and see the new bank and accounts appear without a manual page refresh.
- **7.10 — Plaid item removal on unlink.**
  - Depends on: 7.1, 7.2
  - Success: unlinking a sandbox bank (`DELETE /banks/{bank_id}`) calls Plaid's `item/remove`, sets `Plaid_item.removed_at` (row retained, not dropped), and a second unlink attempt against the same already-removed item doesn't error.
- **7.11 — Ghost-item detection** (webhook-side check + scheduled `reconcile_removed_plaid_items` job).
  - Depends on: 7.8, 7.10
  - Success: a webhook received for an item with `removed_at` already set produces an ERROR-level log entry visible via `/admin/logs`; running the reconciliation job against a genuinely-removed sandbox item confirms Plaid also reports it gone (no alert), and against an item still active despite `removed_at` being set (simulate by skipping the real `item/remove` call in a test) produces the same alert.
- **7.12 — Frontend Banks list & detail pages** (`/banks`, `/banks/:bankId`, `/accounts/:accountId`, cross-links back from `/accounts` — see [API_SPEC.md §3](API_SPEC.md#3-banks-linked-connections)).
  - Depends on: 4.1, 7.3
  - Success: `/banks` renders one row per linked `Bank` with the correct `health` badge, `last_synced_at`, and account count sourced from `GET /banks`; clicking a bank navigates to `/banks/:bankId` and shows exactly the accounts whose `bank_id` matches (`GET /accounts?bank_id=`); clicking an account forwards to `/accounts/:accountId` showing the same data as its row on the flat `/accounts` list; clicking "Sync now" returns a job id and the bank's `last_synced_at` updates once the job completes, with no manual page refresh.
  - Failure: a bank with `health` of `needs_reauth` or `error` renders visibly distinct from `healthy` (not a silently identical row) and names the needed action, rather than failing silently; `/banks/:bankId` or `/accounts/:accountId` for an id that doesn't belong to the current user, or doesn't exist, renders a not-found state and never another user's data — covered by an authorization test per [CLAUDE.md](CLAUDE.md)'s "every write route gets an authorization test," extended here since these are new owner-scoped read routes; unlinking a bank that still has accounts removes it from `/banks` and those accounts show as unlinked/inactive on `/accounts` rather than silently keeping a dangling `bank_id`; a failed "Sync now" (job errors, or Plaid reports the item revoked) surfaces an error state on the bank card instead of a spinner that never resolves.

**Exit:** linking a real sandbox bank produces real accounts/transactions in the same screens Phase 4 built, with scheduled sync running in the background, and unlinking it leaves no active item behind on Plaid's side.

## Phase 8 — Admin console
Goal: the operational surface — built last because it depends on nearly everything above.

- **8.1 — Admin auth dependency** (`role=admin`, separate from ownership).
  - Depends on: 2.1
  - Success: a non-admin's token gets 403 on any `/admin/*` route; an admin's token succeeds; a test shows a non-owner admin still gets through where a non-owner non-admin wouldn't, proving it's a distinct check.
- **8.2 — User management routes.**
  - Depends on: 8.1, 2.2, 7.10
  - Success: an admin can list/create/view/edit/reset-password/suspend/delete a user; a test attempting to suspend, demote, or delete the last remaining admin is rejected; deleting a user with a linked sandbox bank calls Plaid `item/remove` for it before the user's data is removed.
- **8.3 — Operations routes** (jobs, logs, sync-all, bank health-check, config, Plaid item reconciliation trigger).
  - Depends on: 8.1, 3.2, 7.4, 7.11
  - Success: `/admin/jobs` and `/admin/logs` return real data from a system with at least one job run and log line; a planted fake secret in log output is masked, not raw, on inspection; `POST /admin/plaid/reconcile-items` surfaces the same ghost-item alert 7.11's scheduled job would produce.
- **8.4 — `PlaidAPICall`-backed usage/cost routes.**
  - Depends on: 8.1, 7.6
  - Success: `group_by=user` on a dataset with calls from two users returns two distinct, correctly-summed rows, not a combined total.
- **8.5 — `ApiToken` model + issuance/list/revoke + token-auth middleware.**
  - Depends on: 8.1
  - Success: a newly issued token authenticates a normal resource request scoped to its bound user, returns its secret exactly once at creation, and a revoked token gets 401 on next use.
- **8.6 — `AdminAuditLog` + write-hook on every admin write route + `GET /admin/audit-log`.**
  - Depends on: 8.2–8.5
  - Success: every write performed across 8.2–8.5's own tests produces a matching audit-log row — verified by asserting the count, not just a 200 from the endpoint.
- **8.7 — Reference-data seed routes** (categories, banks).
  - Depends on: 4.3, 8.1
  - Success: re-running seeding is idempotent (no duplicate rows); a non-admin request gets 403.
- **8.8 — Frontend admin screens** (thin/functional is enough for v1).
  - Depends on: 8.2–8.7
  - Success: an admin can list/view/suspend a user and view the audit log through the UI without hand-crafting API requests.

**Exit:** an admin can manage users, see an audit trail of their own actions, and issue a working API token, with no route leaking another user's financial data.

## Phase 9 — Hardening & deploy prep

- **9.1 — CORS lock-down** to real origins.
  - Depends on: revisit before any non-local deploy
  - Success: a request from a non-allow-listed origin is rejected by the browser; the real frontend origin still works.
- **9.2 — Rate-limit tuning** against real usage.
  - Depends on: enough real usage to observe
  - Success: a documented decision (keep or change the SPEC §6 starting numbers) backed by actual observed data, not a guess.
- **9.3 — Resolve D2 and stand up the chosen deployment target.**
  - Depends on: Phases 1–8 substantially done
  - Success: the app is reachable at a real non-localhost URL on the chosen target, with the same test suite passing against it as passes locally.
- **9.4 — Full pass against [CLAUDE.md](CLAUDE.md)'s Definition of Done + Don't-do-this list, across every route.**
  - Depends on: everything
  - Success: every route has been checked at least once, with findings either fixed or explicitly logged as an accepted risk — nothing silently skipped.
- **9.5 — Scope the data-migration task** ([SPEC.md §8](SPEC.md#8-data-migration-planned-not-v1-blocking)) for real.
  - Depends on: 4.1 finalized
  - Success: a concrete plan exists (mapping, id strategy, ownership resolution, backfill) detailed enough to start executing without re-deriving the approach from scratch — doesn't have to be executed yet.

## Deferred to post-v1

Explicitly decided, not forgotten — these don't block v1 shipping:

- **Recurring-bill auto-detection** (`process_recurring_bills` scheduled job + wiring its matches to notifications). Manual recurring-transaction entry and payment tracking (5.2), the `Notification` model (5.3), and budget/goal threshold notifications (5.4) all ship in Phase 5 as normal; only this pattern-matching detection job and its notification wiring are deferred.
  - Depends on: 5.2, 5.3, 3.1
  - Blocked by: a design pass on the actual matching heuristic — amount/date drift tolerance, merchant fuzzy-matching — none of which is specified yet (see [SPEC.md §4](SPEC.md#4-feature-scope)).
  - Success: running it against a seeded history with 3+ monthly occurrences of the same merchant/amount creates a `RecurringTransaction` with no human flagging it first; running it against a bill due inside its reminder window creates exactly one new unread notification — not zero, not a duplicate on a second run.
- **Data migration from the old `finance-app` database** — see [SPEC.md §8](SPEC.md#8-data-migration-planned-not-v1-blocking) and 9.5 above.
