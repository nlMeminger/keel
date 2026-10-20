# Money App v2 — Planning Spec

## 1. Goals
- A UI that actually works: consistent interactions, mobile-friendly, real-time feedback on every sync/background operation — never a silent failure.
- Real multi-tenant support: many separate users, each with fully isolated data enforced at the query layer.
- A complete personal-finance feature set, fully implemented: accounts, transaction tracking & search, categories with auto-categorization rules, merchants, budgets, savings goals, recurring bills/subscriptions with reminders, assets, notifications, and reports & analytics (spending by category, monthly trends, net worth over time, cash flow, credit health, investment performance).
- Scheduled background jobs (transaction sync, balance refresh, recurring-bill detection) run automatically, with pollable status the frontend can show live.
- **Must run fully without any Plaid connection.** Manual accounts, manual transactions, and manual history entries (credit score, account balances, etc. — see [API_SPEC.md §14](API_SPEC.md#14-metrics-manual-history-entries)) are first-class, not a degraded fallback mode. Plaid is one way to populate data, not a dependency the app assumes exists.
- A typed, versioned JSON API clean enough to support a native mobile app later.

## 2. Architecture principles
- SPA frontend + typed JSON API backend — no server-rendered pages, no full-page reloads.
- Every sync or background operation has a real, pollable status record; the UI always reflects actual progress/success/failure, never a silent or stuck state.
- Per-user ownership checks and auth are built into every write route from the start — the acting user is always derived from the verified token, never from a client-supplied `user_id`.

## 3. Architecture

**Backend:** FastAPI (Python), SQLAlchemy 2.0, PostgreSQL, Celery + Redis for background jobs, Plaid Python SDK for bank connections. Typed JSON API (Pydantic schemas, auto-generated OpenAPI spec) — useful for a typed frontend and later a native app.

**Frontend:** React + TypeScript SPA (Vite), mobile-responsive layout, a component library for consistent UI (e.g. shadcn/ui or Mantine — decide during setup). Server state (fetching, caching, loading/error states) runs through TanStack Query — resolved now rather than left open, since it's the direct mechanism behind goal #1's real-time sync feedback; the component library pick is independent and stays open. Talks to the API over JSON; no server-rendered pages.

**Auth & multi-user:** Real per-user accounts. Short-lived JWT access token (sent via `Authorization` header, not a cookie — avoids CSRF exposure for the API itself) + rotating refresh token in an httpOnly cookie (CSRF-protected on the refresh endpoint only), backed by a `Session` table so sessions can actually be revoked (see §5, [API_SPEC.md §1](API_SPEC.md#1-auth)). Every record (`Account`, `Transaction`, `Plaid_item`, etc.) is scoped to `owner_id`; every query derives the acting user from the verified token, never from client-supplied IDs.

**Background jobs & real-time feedback:** Celery beat runs `sync_transactions`, `update_balances`, `process_recurring_bills` on a schedule. Each sync job writes a status record the frontend polls (e.g. every 2–3s while a job is in flight) to show live progress/success/failure. Plaid webhooks remain the primary trigger for real-time updates; polling covers the scheduled/background path. (SSE/websockets are a reasonable v2 upgrade for push notifications — e.g. bill due reminders — not required for v1.)

**Mobile:** Responsive web now; backend is designed API-first (versioned, token-based auth, no server-rendered dependency) so a native app can be added later without backend rework.

**Deployment:** Undecided — keep it portable. Docker Compose for local/self-hosted now, structured so it can move to a cloud platform (Fly.io/Railway/Render) later without rearchitecting. Decide at build time.

## 4. Feature scope

All feature areas below are in scope for v1 — this is the full feature set, not a trimmed-down MVP.

| Area | Notes |
|---|---|
| Accounts (checking/savings/credit card/investment/loan/mortgage/student loan) | Single polymorphic model, not per-type sibling tables (see §5); investment accounts carry per-holding detail (Plaid-sourced or manually entered, same `Holding` table) |
| Bank linking & sync (Plaid) | Webhook signature verification; real scheduled sync via Celery beat; unlinking always removes the item Plaid-side too (see §6) |
| Transactions (list/search/filter) | Main daily-use surface — prioritize mobile UX; automatic transfer-pair detection (see §5) so self-payments (e.g. a credit card payoff) never double-count as spend and income |
| Categories + auto-categorization rules | System categories + user-owned custom categories |
| Merchants | |
| Budgets | |
| Savings goals | |
| Recurring transactions / bill reminders | Manual entry ships in v1; scheduled auto-detection is deferred post-v1 (see [ROADMAP.md](ROADMAP.md) Deferred section) — the matching heuristic (amount/date tolerance, merchant fuzzy-matching) needs its own design pass first |
| Notifications | v1 triggers: a budget crossing a usage threshold, a savings goal crossing a progress milestone, a bank needing reauth — each checked inline at its relevant write path, not a scheduled job. Recurring-bill reminders are deferred post-v1 along with auto-detection (see [ROADMAP.md](ROADMAP.md) Deferred section) |
| Assets (non-Plaid-linked net worth items) | |
| Reports & analytics | Spending by category, monthly trends, net worth over time, cash flow, credit health, investment performance |
| Multi-user | Real per-user isolation; each user links their own banks independently |
| Manual history / metrics (credit score, manual account balances) | Required for running fully without Plaid (see §1); also backs net-worth-history for Plaid-linked accounts |
| Admin tooling (user management, Plaid access control, usage/cost tracking, API tokens) | See [API_SPEC.md §18](API_SPEC.md#18-admin) |

## 5. Data model notes
Core entities: `User`, `Plaid_item`, `Bank`, `Account`, `Holding`, `Transaction`, `Category`, `CategoryRule`, `Merchant`, `Budget`, `SavingsGoal`, `GoalContribution`, `RecurringTransaction`, `Asset`, `Notification`, `Webhook`, `PlaidAPICall`, `Metrics`. `Account` is a single table with an `account_type` discriminator column (`checking`|`savings`|`credit_card`|`investment`|`loan`|`mortgage`|`student_loan`) plus a `detail` JSONB column holding type-specific fields (credit limit/APR, loan principal/rate/term, mortgage escrow/schedule, student loan servicer, etc.) — not per-type sibling tables, and not SQLAlchemy table inheritance either: a new or changed type-specific field is a Pydantic schema change, not a migration, and the API's nested detail object ([API_SPEC.md §4](API_SPEC.md#4-accounts)) maps directly onto this column. Type safety for `detail` is enforced at the Pydantic layer (one schema per `account_type`), not the database — the same free-form-at-the-DB-layer tradeoff already made for `Metrics.type`/`Asset.asset_type` below. Investment accounts' holdings stay in the dedicated `Holding` table below, never inside this JSON blob.

`Holding`: `account_id`, `security_id` (nullable — unset for a manually-entered holding with no Plaid security match), `symbol`, `name`, `quantity`, `cost_basis`, `current_value`, `source` (`plaid` | `manual`). Plaid-sourced holdings are read-only (overwritten on sync, never user-editable); manual investment accounts support full CRUD on their own holdings via [API_SPEC.md §4](API_SPEC.md#4-accounts) — both exist in the same table so `/reports/investments` doesn't need two code paths. An investment account's own `account_balance` Metrics entries (from Plaid's reported total value, or a manual entry) are tracked independently of the sum of its `Holding.current_value` rows — Plaid reports both separately (e.g. uninvested cash isn't a holding), and the app doesn't reconcile or enforce them matching. `Holding` backs the per-position detail in `/reports/investments`; it is never treated as a derivation of the account-level balance.

`Transaction` carries transfer-pairing fields: `is_transfer` (bool, default `false` — only becomes `true` once a candidate pair is user-confirmed), `paired_transaction_id` (nullable, self-referential FK to the matching transaction on the other account), `transfer_status` (`none` | `suggested` | `confirmed` | `rejected`). Pairing is detected automatically — same owner, two *different* accounts, opposite-sign amounts, dates within ±1-2 business days — and surfaces as `suggested` for the user to confirm or reject via `PATCH /transactions/{id}` (see [API_SPEC.md §5](API_SPEC.md#5-transactions)); it never auto-applies to reports without that confirmation. A confirmed pair is excluded from cash-flow, spending-by-category, and budget spend-so-far regardless of its assigned category. Detection runs independently of category — it's never gated on one being pre-assigned, since manually-entered transactions have no Plaid categorization to depend on — and instead *assigns* both sides to the seeded system "Transfer" category as a byproduct of confirmation. This is what lets a self-payment (e.g. paying off a credit card from checking) net to zero instead of counting as both an expense and unrelated income. Detection itself runs inline wherever a transaction is written: synchronously on `POST /transactions` (one bounded, indexed query against the user's other accounts), and as a step inside the existing `bulk_import`/`transaction_sync` jobs for bulk import and Plaid sync (see [API_SPEC.md §16](API_SPEC.md#16-sync--background-jobs)) rather than a separate job type of its own.

`Category` has a nullable `owner_id`: `null` = system/seeded category (read-only), set = a user's custom category (see [API_SPEC.md §6](API_SPEC.md#6-categories)). One seeded system category, "Transfer", is what transfer-pairing confirmation assigns automatically (see above) — never created directly by a user.

`Budget`: `category_id` (nullable — `null` means an overall budget across all non-transfer spending, set means scoped to one category), `amount_limit`, `period` (`monthly` only for v1 — no custom/rolling windows, no rollover of unspent amounts between periods), `start_date`. Spend-so-far is always computed from transactions, never stored, and never counts a transaction with `is_transfer=true` regardless of its category.

`SavingsGoal`: `target_amount`, `target_date` (nullable). Progress is the sum of its `GoalContribution` rows (`amount`, `date`, `note`), not a stored running total — manual contributions only for v1; a mode that ties a goal's progress to a linked account's live balance is a reasonable later addition, not needed now.

`Asset`: `name`, `asset_type` (free-form string, same style as `Metrics.type`), `current_value`. Every value change writes a `Metrics` row the same way a manual account's balance change does (see `Metrics` below) — without this, `/reports/net-worth-history` would never actually include assets, since it reconstructs net worth purely from `Metrics` entries.

`Metrics` carries a nullable `asset_id` alongside its existing nullable `account_id` (mutually exclusive — exactly one is set per row). Net-worth-history sums the latest `Metrics` entry per account *and* per asset, not accounts alone.

`Merchant`: `name`, `aliases` (array of raw bank-provided description strings that map to it). Purely an aliasing/grouping construct for display and search — merchant-based auto-categorization goes through `CategoryRule`, not a second `default_category_id` mechanism on `Merchant` itself (two separate auto-categorization paths would need a precedence rule between them for no real benefit).

`CategoryRule`: a fixed, AND-ed set of optional conditions rather than a general condition DSL — `merchant_contains` (substring match), `amount_min`/`amount_max`, `account_id` — plus `category_id` (the result it assigns), `priority` (int, breaks ties when multiple rules match the same transaction), `active`.

`Notification`: `type` (free-form string), `title`, `body`, `related_type`/`related_id` (nullable — points back at whatever triggered it, e.g. a `Bank` needing reauth), `read_at` (nullable timestamp, not a boolean — gives "when," not just "whether").

`User` has: `role` (`user` | `admin`); `status` (`active` | `suspended`); `plaid_enabled` (default `true`); `plaid_monthly_call_limit` (default `null` — unlimited); `must_change_password` (set by an admin-initiated password reset). Defaults always favor unrestricted access; admins opt a specific user *into* a restriction, never the other way around. See [API_SPEC.md §18](API_SPEC.md#18-admin).

`ApiToken` entity for admin-issued external API tokens: `id`, `user_id` (whose data the token acts as), `label`, `scopes` (`["read"]` or `["read","write"]`), `token_hash` (never the raw secret — shown once at creation, like a password), `created_by_admin_id`, `created_at`, `last_used_at`, `expires_at`, `revoked_at`.

`AdminAuditLog` entity backing `/admin/audit-log`: `id`, `admin_user_id`, `action`, `target_type`, `target_id`, `metadata` (JSON), `created_at`.

`Session` entity backing refresh-token rotation and revocation (see [API_SPEC.md §1](API_SPEC.md#1-auth)): `id`, `user_id`, `family_id`, `token_hash`, `issued_at`, `expires_at`, `revoked_at`, `last_used_at`, `user_agent`, `ip_address`. Backs self-service logout, "log out everywhere," and the admin `revoke-sessions` action.

## 6. Security baseline (non-negotiable from day one)
- Every write route resolves the acting user from the verified token; never trust a client-supplied `user_id`/`account_id` for authorization, only for addressing (and always check ownership).
- Plaid webhook endpoint verifies the `Plaid-Verification` JWT before processing anything.
- No secrets (DB creds, JWT secrets, Plaid tokens) in git, ever — `.env`/config gitignored from commit 1, example file uses obvious placeholders.
- No access tokens or secrets in logs (mask to last 4-5 chars).
- Rate limiting on login/register/refresh — starting point: 5 login attempts / 15 min per IP+username, 10 registrations / hour per IP, 30 refreshes / hour per user. Tune based on real usage, these aren't load-tested numbers.
- Cookie flags: `Secure`, `HttpOnly`, `SameSite=Lax` on the refresh cookie once served over HTTPS.
- Locked-down CORS (specific origins, not wide open).
- Admin (`role=admin`) is a separate trust boundary from ownership-based access: `/admin/*` routes never serve infra secrets (DB password, Plaid secret, JWT signing key) over the API, log every admin write to an audit trail, and block demoting/deleting the last remaining admin.
- Secrets at rest are split by whether the app needs to reuse the raw value: `Session.token_hash` and `ApiToken.token_hash` are one-way hashed (same treatment as passwords) since the app only ever verifies them. `Plaid_item.access_token` is reversibly **encrypted**, not hashed, because the app has to decrypt and reuse it to call Plaid — with the encryption key stored separately from the JWT signing key.
- Unlinking a bank — self-service (`DELETE /banks/{bank_id}`) or as part of an admin hard-deleting a user — always calls Plaid's `item/remove` and soft-deletes the `Plaid_item` row (`removed_at` set, row retained) rather than dropping it outright, so a stale item can't keep accruing Plaid API costs after the app considers it gone. A webhook-side check and a scheduled reconciliation job both watch for a removed item Plaid still considers live and alert via `/admin/logs` if one turns up (see [API_SPEC.md §17](API_SPEC.md#17-webhooks-inbound)/[§18](API_SPEC.md#18-admin)).
- Every write route ships with an ownership/authorization test (wrong user's token → 403/404, never a silent success) as part of "done." The auth flow (login → refresh → rotation → theft-detection revocation) gets its own integration test suite, since that's the highest-value path to get right.

## 7. Open questions / next steps
- Component library choice for the frontend (shadcn/ui vs Mantine vs other) — decide during setup.
- Deployment target (self-host vs cloud) — left open, architecture stays portable either way.

**Resolved:**
- Audience is multi-tenant: separate, unrelated users each with fully isolated data — this is what the admin console in §4/[API_SPEC.md §18](API_SPEC.md#18-admin) is for. A shared/household visibility feature is not planned for v1; it's a deliberate future design decision if ever needed, since it forks the single-`owner_id` ownership model everything else assumes.
- Historical data migration: see §8 — a planned post-v1 task, not an open question.

## 8. Data migration (planned, not v1-blocking)
v1 ships and runs on a clean schema, with zero rows carried over. The old `finance-app` Postgres DB is reference material only, not a dependency — migrating its data is a deliberate, separate task to scope later, once the new `Account`/`Transaction` model (the inheritance restructure in §5) is finalized and stable:
- Map each source account type onto the new discriminated `Account` model.
- Decide the id strategy (preserve source primary keys vs. remint with a mapping table).
- Resolve ownership: decide which new user the migrated data is assigned to.
- Backfill `Metrics` balance-history from whatever source balance snapshots exist, so net-worth-history isn't empty on day one for migrated data.
This is explicitly sequenced after v1 ships, not a blocker for it.
