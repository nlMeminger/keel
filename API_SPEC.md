# API Spec v1

Scope: endpoint design only, no implementation. Builds on [SPEC.md](SPEC.md) — FastAPI backend, React SPA consumer, JWT bearer auth.

## Conventions

- **Base path:** `/api/v1`
- **Auth:** `Authorization: Bearer <token>` on every endpoint except `/auth/register`, `/auth/login`, `/auth/refresh`, and `/webhooks/plaid`. The bearer token is either a user's JWT access token (SPA/mobile) or an admin-issued API token (external integrations, see §18) — either way it resolves server-side to an acting `user_id` (+ `scopes`, for API tokens). No endpoint ever accepts a `user_id` from the request body or query string.
- **Response envelope:**
  - Single resource: `{ "data": { ... } }`
  - Collection: `{ "data": [ ... ], "pagination": { "page", "page_size", "total_count", "total_pages" } }`
  - Error: `{ "error": { "code": "string", "message": "string" } }` with an appropriate 4xx/5xx status — never a raw stack trace or `str(e)` to the client.
- **Pagination:** `page` (default 1), `page_size` (default 25, max 200) query params on every list endpoint — no unbounded collections.
- **Reads are GET, writes are POST/PATCH/DELETE.**
- **IDs:** UUIDs in the path, never in the request body, for identifying which record a request addresses.

---

## 1. Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (email, password, name) |
| POST | `/auth/login` | Creates a new `Session` row (new `family_id`), sets refresh cookie, returns access token |
| POST | `/auth/refresh` | Validates the refresh cookie against an active `Session` row, **rotates** it (revoke old row, issue new row in the same `family_id`), returns a new access token + refresh cookie |
| POST | `/auth/logout` | Revokes the current session only |
| GET | `/auth/sessions` | List the current user's own active sessions (`created_at`, `last_used_at`, `user_agent`, which one is "this session") |
| DELETE | `/auth/sessions/{session_id}` | Revoke one of your own sessions (e.g. a lost phone) |
| DELETE | `/auth/sessions` | Revoke every session except the current one ("log out everywhere else") |
| GET | `/auth/me` | Current user profile |
| PATCH | `/auth/me` | Update own profile/settings (timezone, name); always acts on the token's identity |

**Refresh-token theft detection:** if a *revoked* session's token is ever presented again (a replayed/stolen token — rotation means a legitimate client would never do this), the entire `family_id` is revoked immediately, not just that one row, forcing a real re-login. Access tokens are short-lived (~15 min, stateless JWT); refresh tokens are opaque values with only their hash stored (same pattern as passwords and API tokens below), sliding ~30-day expiry capped at 90 days absolute.

This `Session` table is also what the admin `revoke-sessions` endpoint (§18) and an admin-initiated password reset revoke.

## 2. Plaid Link
| Method | Path | Description |
|---|---|---|
| POST | `/plaid/link-token` | Create a Link token for adding a new bank |
| POST | `/plaid/link-token/update` | Create a Link token in update mode for a reauth-needed bank |
| POST | `/plaid/exchange-token` | Exchange `public_token` for access token, create the bank connection |

Update-mode (`/plaid/link-token/update`) additionally requires a Plaid-side `user_id`, obtained via the idempotent `/user/create` (same `client_user_id` always returns the same `user_id`, so this is never a duplicate-creation risk) — Plaid began enforcing this on every update-mode request regardless of product usage, not just consumer-report-style products. `exchange-token` also triggers the initial accounts/holdings pull synchronously (see §3/§4) rather than waiting for the first sync job.

## 3. Banks (linked connections)
| Method | Path | Description |
|---|---|---|
| GET | `/banks` | List linked banks for current user: institution, `health`, `last_synced_at`, `account_count` |
| GET | `/banks/{bank_id}` | Same shape as one row above — linked accounts themselves come from `GET /accounts?bank_id=`, not nested here |
| DELETE | `/banks/{bank_id}` | Unlink a bank — calls Plaid's `item/remove`, then soft-deletes the `Plaid_item` (`removed_at` set, row retained rather than dropped, so a later ghost-item check has something to verify against, see §17/§18) |
| POST | `/banks/{bank_id}/sync` | Force an immediate sync for this bank — returns `202` + job id (see §16) |

**Frontend**: `/banks` is a top-level nav item (above Accounts — it's connection management, not financial data). It lists every linked `Bank`: institution name, a `health` badge (`healthy`/`needs_reauth`/`error`, see [SPEC.md §5](SPEC.md#5-data-model-notes)), `last_synced_at`, and account count, with per-bank "Sync now" (→ the `POST .../sync` route above, polled via the existing job contract, [§16](#16-sync--background-jobs) — not a new polling mechanism) and "Unlink" actions. Clicking a bank opens `/banks/{bank_id}`: the same header plus the accounts belonging to it (`GET /accounts?bank_id=`, reusing the account-row rendering `/accounts` already has, not a second account UI). Clicking an account there forwards to `/accounts/{account_id}` — a per-account detail route that doesn't exist yet (today's `/accounts` is a single flat list with no per-account URL). Once `Account.bank_id` exists (7.3), each Plaid-linked row on the flat `/accounts` list also carries a small bank-name badge linking back to `/banks/{bank_id}`, so the two pages cross-link both ways. Manual (non-Plaid) accounts never appear on `/banks` — they have no `Bank` to group under, and keep living only on `/accounts`.

## 4. Accounts
| Method | Path | Description |
|---|---|---|
| GET | `/accounts` | List accounts (filter: `type`, `bank_id`, `active`) |
| GET | `/accounts/{account_id}` | Account detail |
| POST | `/accounts` | Create a manual (non-Plaid) account |
| PATCH | `/accounts/{account_id}` | Update account (name, type-specific fields) |
| DELETE | `/accounts/{account_id}` | Delete/deactivate an account |

Type-specific detail (loan terms, mortgage schedule, student loan servicer, investment holdings) is returned as a nested object on the account detail response rather than requiring the client to know which concrete account type to query — see [SPEC.md §5](SPEC.md#5-data-model-notes).

**Holdings** (investment accounts only)
| Method | Path | Description |
|---|---|---|
| GET | `/accounts/{account_id}/holdings` | List holdings for one investment account (Plaid-sourced and manually-entered alike) |
| POST | `/accounts/{account_id}/holdings` | Add a manual holding (`symbol`, `name`, `quantity`, `cost_basis`). 403 if the account is Plaid-linked — those are sync-populated, not user-editable |
| PATCH | `/accounts/{account_id}/holdings/{holding_id}` | Update a manual holding. 403 on a Plaid-sourced holding |
| DELETE | `/accounts/{account_id}/holdings/{holding_id}` | Remove a manual holding. 403 on a Plaid-sourced holding |

## 5. Transactions
| Method | Path | Description |
|---|---|---|
| GET | `/transactions` | List/filter/search (query params: `account_id`, `category_id`, `merchant` (free-text substring match against the linked merchant's name — not a `merchant_id` exact match), `description`, `amount_min/max`, `date_from/to`, `pending`, `transfer_status` (`none`\|`suggested`\|`confirmed`\|`rejected`), `sort`) |
| GET | `/transactions/{transaction_id}` | Transaction detail |
| POST | `/transactions` | Manually add a transaction to an account |
| POST | `/transactions/bulk/preview` | Parse an import file, return detected rows + likely duplicates/conflicts. Commits nothing |
| POST | `/transactions/bulk` | Commit a bulk import (e.g. CSV) — same payload shape as the preview response, no server-side preview state to track or expire. Returns `202` + job id (see §16) instead of blocking — import size isn't bounded |
| PATCH | `/transactions/{transaction_id}` | Update category, notes, or merchant; also where a `suggested` transfer pairing is resolved — `{ "transfer_status": "confirmed" }` or `{ "transfer_status": "rejected" }` |
| DELETE | `/transactions/{transaction_id}` | Delete a manually-added transaction |

**Not yet implemented as of Phase 4**: `/transactions/bulk/preview` and `/transactions/bulk` — deferred because the import file payload shape (column mapping, header detection) was never pinned down, and Phase 4's roadmap success criteria for Transactions didn't require them. "Split" transactions (mentioned in earlier drafts of the PATCH row) are also not implemented — no `Split`/line-item entity exists anywhere in this doc, so it's being treated as dropped rather than deferred; revisit explicitly if splitting is still wanted. Revisit both before Phase 5's `CategoryRule.apply` or Phase 7's Plaid sync assume bulk-import plumbing already exists.

**Transfer-pair detection**: runs automatically (any account creation/sync, manual or Plaid) looking for a same-owner, different-account, opposite-sign amount within ±1-2 business days. A match sets `paired_transaction_id` on both sides and `transfer_status=suggested` — it does **not** yet exclude them from reports or budgets. Only once the user confirms via the `PATCH` above does `is_transfer` flip to `true` on both sides, both get assigned the seeded system "Transfer" category, and they drop out of `/reports/cash-flow`, `/reports/spending-by-category`, and budget spend-so-far. Rejecting a suggested pair clears `paired_transaction_id` on both sides and sets `transfer_status=rejected` so the same two transactions aren't re-suggested. Execution: inline on `POST /transactions` (a single bounded, indexed query against the user's other accounts); for `POST /transactions/bulk` and Plaid sync it runs as a step inside that same job rather than a separate job type — see [§16](#16-sync--background-jobs).

## 6. Categories
| Method | Path | Description |
|---|---|---|
| GET | `/categories` | List categories visible to the user: system (seeded) + their own custom ones. Query param `scope=system\|custom\|all` (default `all`) |
| POST | `/categories` | Create a custom category (`primary_category`, optional `detailed_category`, optional `icon`/`color`) |
| PATCH | `/categories/{category_id}` | Update a custom category. 403 if the target is a system category |
| DELETE | `/categories/{category_id}` | Delete a custom category. 409 if transactions/rules/budgets still reference it unless `reassign_to=<category_id>` is supplied. As of Phase 4 the reference check covers `Transaction` and `Budget` — extend it for `CategoryRule` once Phase 5.1 adds that table |

Category seeding happens via a migration/CLI command, not a public endpoint. `owner_id` is nullable on `Category` — `null` = system/seeded (read-only via the API), set = user's custom category. Rules, budgets, and transactions reference categories by id either way, so nothing downstream needs to know which kind it is except the edit/delete permission check above. One seeded system category, "Transfer," is never created or assigned directly through this API — it's only ever applied automatically when a transfer pairing is confirmed (see §5).

## 7. Category Rules
| Method | Path | Description |
|---|---|---|
| GET | `/category-rules` | List user's auto-categorization rules |
| POST | `/category-rules` | Create a rule: `{ merchant_contains?, amount_min?, amount_max?, account_id?, category_id, priority, active }` — all provided conditions are AND-ed; `category_id` is what gets assigned on a match |
| PATCH | `/category-rules/{rule_id}` | Update a rule |
| DELETE | `/category-rules/{rule_id}` | Delete a rule |
| POST | `/category-rules/test` | Dry-run against the user's existing uncategorized transactions: `{ merchant_contains?, amount_min?, amount_max?, account_id? }` (the same matching conditions a saved rule has, without `category_id`/`priority`/`active`). Returns matches, writes nothing |
| POST | `/category-rules/apply` | Apply all active rules to existing uncategorized transactions, ascending `priority` order (lower value wins first). Returns `202` + job id (see §16) rather than blocking — can touch a large transaction set |

## 8. Merchants
| Method | Path | Description |
|---|---|---|
| GET | `/merchants` | List merchants |
| POST | `/merchants` | Create merchant: `{ name, aliases: string[] }` — a pure grouping/display construct; merchant-based auto-categorization goes through Category Rules (§7), not a default-category field here |
| PATCH | `/merchants/{merchant_id}` | Update merchant |
| DELETE | `/merchants/{merchant_id}` | Delete merchant |

## 9. Budgets
| Method | Path | Description |
|---|---|---|
| GET | `/budgets` | List budgets with current period spend-vs-limit, computed live from transactions (never stored) and never counting a transaction with `is_transfer=true`. "Current period" = the calendar month containing today, clipped so it never starts before the budget's own `start_date` |
| POST | `/budgets` | Create a budget: `{ category_id?, amount_limit, start_date }` — `category_id` omitted means an overall budget across all non-transfer spending. `period` is `monthly` only for v1, no custom/rolling windows, no rollover of unspent amounts between periods |
| PATCH | `/budgets/{budget_id}` | Update a budget |
| DELETE | `/budgets/{budget_id}` | Delete a budget |

Crossing a usage threshold (e.g. 90%/100% of `amount_limit`) creates a `Notification` (§13) — checked inline, as part of whichever transaction write (create/update/bulk/sync) changed that budget's spend-so-far, not a scheduled job.

## 10. Savings Goals
| Method | Path | Description |
|---|---|---|
| GET | `/goals` | List savings goals with progress (sum of `GoalContribution` rows, not a stored running total) |
| POST | `/goals` | Create a goal: `{ name, target_amount, target_date? }`. Manual contributions only for v1 — no mode tying progress to a linked account's live balance |
| PATCH | `/goals/{goal_id}` | Update a goal |
| DELETE | `/goals/{goal_id}` | Delete a goal |
| POST | `/goals/{goal_id}/contributions` | Add a contribution: `{ amount, date, note? }`. Returns the updated parent goal (fresh `progress_amount`), not the raw contribution — the caller never needs a second fetch to see new progress |

Crossing a progress milestone (e.g. 50%/100% of `target_amount`) on this route creates a `Notification` (§13) — checked inline, not a scheduled job.

## 11. Recurring Transactions / Bills
| Method | Path | Description |
|---|---|---|
| GET | `/recurring-transactions` | List detected/manual recurring transactions (bills + subscriptions) |
| POST | `/recurring-transactions` | Create one by hand: `{ name, amount_expected, frequency, account_id?, category_id?, merchant_id?, next_due_date?, is_bill? }` |
| PATCH | `/recurring-transactions/{id}` | Update (e.g. mark as a bill, adjust expected amount) |
| POST | `/recurring-transactions/{id}/payments` | Record a payment against it: `{ amount, date }`. Returns the updated parent (fresh `last_paid_date`), not the raw payment |
| DELETE | `/recurring-transactions/{id}` | Remove/ignore |

Manual create/edit/payment-tracking ships in v1. Scheduled auto-detection (`process_recurring_bills`, matching occurrences by merchant/amount/date pattern) is **deferred post-v1** — see [ROADMAP.md](ROADMAP.md) Deferred section; the matching heuristic needs its own design pass before it's built, so it's not in §16's active scheduled-job list below.

## 12. Assets
| Method | Path | Description |
|---|---|---|
| GET | `/assets` | List non-Plaid-linked net worth items (property, vehicles, etc.) |
| POST | `/assets` | Create an asset: `{ name, asset_type, current_value }`. `asset_type` is a free-form string, same style as `Metrics.type` |
| PATCH | `/assets/{asset_id}` | Update an asset. A `current_value` change writes a `Metrics` row (`type=asset_value`, `asset_id=...`) automatically, the same way a manual account's balance change does — without this, `/reports/net-worth-history` would never include assets |
| DELETE | `/assets/{asset_id}` | Delete an asset |

## 13. Notifications
| Method | Path | Description |
|---|---|---|
| GET | `/notifications` | List notifications (filter: `unread_only`). Each has `type` (free-form string), `title`, `body`, `related_type`/`related_id` (nullable — points back at whatever triggered it, e.g. a `Bank`), `read_at` (nullable timestamp) |
| PATCH | `/notifications/{id}` | `{ read: bool }` — sets or clears `read_at` |
| DELETE | `/notifications/{id}` | Dismiss |

No `POST` — notifications are only ever created server-side. v1 triggers: a budget crossing a usage threshold (§9), a savings goal crossing a progress milestone (§10), and a bank needing reauth (from Plaid webhook/sync handling, §17). Recurring-bill reminders are deferred post-v1 along with auto-detection (§11, [ROADMAP.md](ROADMAP.md) Deferred section). Threshold/milestone notifications use a dedicated `type` per threshold (e.g. `budget_threshold_90`, `goal_milestone_50`) so the write path that creates them can check for a prior notification of that same type against the same `related_id` before creating a duplicate — a budget's dedup window is scoped to its current period (so next month's crossing still notifies), a goal's is unscoped (it has no period, so each milestone notifies at most once ever).

## 14. Metrics (manual history entries)
Needed because the app must run fully without any Plaid connection — manual accounts and transactions already cover that, but there's no way to log a point-in-time value that isn't an account balance (e.g. credit score), or to backfill history for a manual account at all.

| Method | Path | Description |
|---|---|---|
| GET | `/metrics` | List manual history entries (query: `type`, `account_id`, `asset_id`, `date_from/to`) — powers trend charts |
| POST | `/metrics` | Add an entry: `{ type, value, date, note, account_id?, asset_id? }`. `account_id`/`asset_id` are mutually exclusive — at most one is set. `type` is a free-form key + plain numeric value — no units/display-name/chart-type registry for v1, kept simple over rich on purpose |
| POST | `/metrics/bulk` | Bulk-add entries (e.g. backfill a year of past credit-score checks at once) |
| PATCH | `/metrics/{id}` | Correct a past entry |
| DELETE | `/metrics/{id}` | Remove an entry |

`type=account_balance`/`type=asset_value` entries are usually written implicitly, not posted directly: `PATCH /accounts/{account_id}` on a manual account and `PATCH /assets/{asset_id}` both write one automatically on every value change, and the scheduled balance-sync job (§16) writes one for Plaid-linked accounts on every refresh. Either way, every account *and* every asset ends up with a real value history in the same table — which is what makes `/reports/net-worth-history` below possible without Plaid, and inclusive of assets.

## 15. Dashboard & Reports
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/summary` | Net worth (+ delta vs. last period), this-month inflow/outflow, recent transactions (capped, e.g. 10), budget status, latest credit score + trend — all at a glance. Must return something sensible with zero Plaid connections (manual-only data). "Delta vs. last period" compares against net worth at the end of last calendar month (via `/reports/net-worth-history` logic); a brand-new account/asset that predates any Metric simply counts as 0 for that prior point, same no-retroactive-backfill rule net-worth-history follows |
| GET | `/accounts/{account_id}/balance-history` | Convenience read over `/metrics?type=account_balance&account_id=...` for charting one account. Optional `date_from`/`date_to`, unbounded if omitted |
| GET | `/reports/net-worth-history` | Net worth over time, reconstructed from every account's *and* every asset's value-history entries (manual or Plaid-sourced — same `Metrics` table either way). `granularity=day\|week\|month` (default `day`) rolls up server-side to the last value per period. Optional `date_from`/`date_to`; `date_to` defaults to today, `date_from` defaults to the earliest relevant `Metrics` entry the user has (today if none yet) |
| GET | `/reports/cash-flow` | Inflow/outflow over time, by period (`granularity` as above, default `day`). Excludes any transaction with `is_transfer=true`. Optional `date_from`/`date_to`; both default to the current calendar month |
| GET | `/reports/spending-by-category` | Category breakdown over any date range. Excludes any transaction with `is_transfer=true`. Optional `date_from`/`date_to`; both default to the current calendar month |
| GET | `/reports/credit-health` | Credit utilization (computed from credit accounts) **and** credit-score history (from `/metrics?type=credit_score`) together, since they're normally read as one picture. Same `granularity`/`date_from`/`date_to` defaults as net-worth-history. `overall_utilization` is `null` (not `0`) when the user has no credit_card accounts yet, so the frontend can tell "no data" apart from "no usage" |
| GET | `/reports/investments` | Per-holding performance (quantity, cost basis, current value, gain/loss), aggregated across Plaid-sourced and manually-entered holdings alike — see `Holding` in §4 |

## 16. Sync & Background Jobs
| Method | Path | Description |
|---|---|---|
| POST | `/sync/transactions` | Force-trigger transaction sync for all (or one, via `{bank_id}` body) bank, returns job id |
| POST | `/sync/balances` | Force-trigger balance/holdings refresh for all (or one) bank, returns job id |
| GET | `/sync/jobs/{job_id}` | Poll job status (`pending`/`running`/`succeeded`/`failed`, progress, error message) — this is what the frontend polls for live sync feedback ([SPEC.md §3](SPEC.md#3-architecture)) |

`POST /banks/{bank_id}/sync` (§3) is the one-button "sync this bank now" action — it runs *both* a balance/holdings refresh and a transaction sync for that bank, still under the `transaction_sync` job type (there's no separate "full sync" entry in the type list below), rather than making the UI fire two jobs for one button.

Scheduled sync (Celery beat calling these same code paths automatically) runs `sync_transactions` and `update_balances` on a schedule — every bank in the system, not one user's, skipping (not erroring on) any bank whose owner has Plaid access disabled so one admin-disabled user never blocks the run for everyone else. Default intervals: balances hourly (cheap — one `/accounts/get` call per bank), transactions every 6 hours (heavier, and already backstopped by the `SYNC_UPDATES_AVAILABLE` webhook, §17/§8, for the common real-time case). These endpoints expose a manual trigger over the same logic. A third scheduled job, `reconcile_removed_plaid_items`, periodically re-verifies that every soft-deleted `Plaid_item` (`removed_at` set) is actually gone on Plaid's side — see §18. `process_recurring_bills` is **deferred post-v1** (see §11, [ROADMAP.md](ROADMAP.md) Deferred section) and isn't part of the active schedule.

**Job polling contract:** `{ "id", "type": "transaction_sync|balance_sync|bulk_import|category_rule_apply|plaid_item_reconciliation", "status", "progress": { "current", "total" }, "started_at", "finished_at", "error" }`. Frontend polls every 2s while `pending`/`running`, backs off to every 10s past 30s elapsed, and stops once the status is terminal — no open-ended polling loop. `recurring_detection` isn't in the active type list — it's added back when that job ships (see §11). Transfer-pair detection (§5) and budget/goal threshold notifications (§9/§10) are not job types either — both run inline at their respective write paths (or, for transfer-pairing, as a step inside `bulk_import`/`transaction_sync`), never as a standalone pollable job.

This same job/polling contract backs any write whose latency isn't bounded, not just scheduled syncs — `/transactions/bulk` (§5) and `/category-rules/apply` (§7) go through it too, for the same reason: a request that could run long shouldn't block.

## 17. Webhooks (inbound)
| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/plaid` | Inbound Plaid webhook (transactions updated, item error, etc.). Verifies the `Plaid-Verification` header JWT before processing anything; not user-authenticated, verified by signature instead |

**Ghost-item check:** after verification, the webhook's `item_id` is looked up against `Plaid_item`. If it matches a row with `removed_at` already set, Plaid is still sending webhooks — and likely still billing — for an item the app explicitly removed; this logs an ERROR-level entry (visible via `/admin/logs`, §18) immediately. This only catches items Plaid still has *active data changes* for — a fully dormant ghost item generates no webhook at all, which is what the scheduled reconciliation job in §18 is for.

## 18. Admin
All `/admin/*` routes require `role=admin`, checked by a separate dependency from normal per-user auth. Regular endpoints never let a client set or read anyone's role but their own (read-only on `/auth/me`).

**Users**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/users` | List all users (filter: `role`, `status`) |
| POST | `/admin/users` | Admin-provision a new user (email, name, role; initial password set via the same flow as reset below) |
| GET | `/admin/users/{user_id}` | Account metadata — status, created_at, last_login, linked-bank count, Plaid access settings + this month's call count. **Not** their transactions/balances; full financial-data access isn't part of this surface (see note below) |
| PATCH | `/admin/users/{user_id}` | Edit profile fields (name, email, timezone), role, or status (active/suspended). Rejects demoting/suspending the last remaining admin |
| POST | `/admin/users/{user_id}/reset-password` | Admin sets a new password directly (or omit the value to auto-generate one). Forces `must_change_password` on next login and revokes all of that user's sessions (§1) |
| DELETE | `/admin/users/{user_id}` | Hard-delete a user and their data. Requires `{ "confirm": true }`; irreversible. First calls Plaid's `item/remove` for every one of the user's linked banks (same as `DELETE /banks/{bank_id}`, §3) so nothing keeps accruing Plaid API cost after the user is gone |
| POST | `/admin/users/{user_id}/revoke-sessions` | Force logout everywhere (invalidate all refresh tokens) |
| PATCH | `/admin/users/{user_id}/plaid-access` | `{ enabled: bool, monthly_call_limit: int \| null }`. Defaults for every user are `enabled=true`, `monthly_call_limit=null` (unlimited) — this is an opt-in *restriction*, not an opt-in grant |

When `enabled=false`, any route that would call Plaid on that user's behalf returns 403 instead of calling out. When the user's call count for the current calendar month (counted live from `PlaidAPICall`, no separate counter to keep in sync) reaches `monthly_call_limit`, the same routes return 429 until the month rolls over or an admin raises/clears the limit. Either way, existing synced accounts/transactions stay fully readable — disabling Plaid access freezes future API calls, it never unlinks or hides already-synced data. If the user wants the bank gone entirely, that's a separate explicit unlink (`DELETE /banks/{bank_id}`).

**Operations**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/jobs` | Celery worker/queue/task inspection across all users |
| GET | `/admin/logs` | Tail application logs, paginated/filtered — still subject to the never-log-secrets rule in [SPEC.md §6](SPEC.md#6-security-baseline-non-negotiable-from-day-one) |
| POST | `/admin/sync/transactions` | Force-trigger transaction sync for **all** users/banks — distinct from the per-user `/sync/transactions` in §16 |
| POST | `/admin/sync/balances` | Force-trigger balance refresh for all users |
| POST | `/admin/banks/{bank_id}/health-check` | Check any bank's Plaid item health regardless of owner |
| POST | `/admin/plaid/reconcile-items` | Manual trigger for the scheduled `reconcile_removed_plaid_items` job (§16) — calls Plaid's `item/get` for every soft-deleted `Plaid_item` and logs an ERROR (via `/admin/logs`) for any that Plaid still reports as active, catching a dormant ghost item that never generated a webhook (§17) |
| GET | `/admin/config` | Non-secret operational config (feature flags, Celery beat schedule). Infra secrets (DB password, Plaid secret, JWT signing key) are never served over any API response, admin included; rotate those via deployment config only, not through this endpoint |

**Plaid usage & cost tracking**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/plaid/api-stats` | Aggregated usage: query params `group_by=user\|endpoint\|month`, `user_id`, `date_from/to`. Call counts only — maps to whatever Plaid pricing tier applies, not a hardcoded dollar estimate since Plaid's per-endpoint pricing varies and changes |
| GET | `/admin/plaid/calls` | Raw call log for drill-down (filter: `user_id`, `endpoint`, `status`, date range) — same `PlaidAPICall` rows the stats above aggregate; stats answer "how much," this answers "which calls exactly" |

**API tokens** (external API access)
| Method | Path | Description |
|---|---|---|
| GET | `/admin/api-tokens` | List issued tokens (label, owner user, scopes, created_at, last_used_at, expires_at, revoked). Never returns the secret after creation |
| POST | `/admin/api-tokens` | Issue a token bound to one user: `{ user_id, label, scopes: ["read"] \| ["read","write"], expires_at? }`. Response includes the full secret **once** — only a hash is stored, same as a password |
| PATCH | `/admin/api-tokens/{token_id}` | Rename the label or change `expires_at`. Not secret rotation — revoke and reissue for that |
| DELETE | `/admin/api-tokens/{token_id}` | Revoke a token immediately |

There's no separate "external API" endpoint tree — issued tokens authenticate against the same `/api/v1/*` resource endpoints documented in §1–17, via `Authorization: Bearer <api_token>` instead of a user's JWT (see Conventions above). The auth layer resolves a token to its bound `user_id` and `scopes`; requests act as that user, scoped to `read` vs `read`+`write`, and never get admin-level access regardless of who issued the token.

Token creation stays admin-only for v1 — self-service tokens scoped to one's own data are a reasonable later addition, not needed now. Token-authenticated requests get their own rate limit (starting point: 60 req/min per token) independent of the Plaid monthly-call cap — one throttles external API usage, the other throttles Plaid cost, and they shouldn't be conflated.

**Reference data**
| Method | Path | Description |
|---|---|---|
| POST | `/admin/categories/seed` | (Re)seed system categories, idempotent |
| POST | `/admin/banks/seed` | (Re)seed institution reference list, idempotent |

**Audit**
| Method | Path | Description |
|---|---|---|
| GET | `/admin/audit-log` | List admin actions (filter: `admin_user_id`, `action`, date range) — every admin write endpoint above logs one entry here automatically |

Deliberately **not** included: a "view as user" / impersonation endpoint that would give an admin direct read access to another user's transactions and balances. That's a meaningfully bigger trust boundary than the operational/account-metadata access above — worth revisiting only if there's an actual support need for it, as its own explicitly-audited feature.

Bootstrapping the first admin happens via a one-time CLI/seed command at deploy time, not a self-service endpoint — a "first user to register becomes admin" rule is racy and exploitable.

---

## Open questions for this layer
None currently open. Next candidates to interrogate, if anything needs revisiting: Auth, Plaid Link, Banks, Accounts (the nested type-specific detail shape in particular), Category Rules, Merchants, Budgets, Goals, Recurring Transactions, Assets, Notifications.
