# Money App v2 — Planning Spec

## 1. Goals
Rebuild the personal finance tracker (prior version: `finance-app`, Flask/Jinja) from scratch with:
- A UI that actually works: consistent interactions, mobile-friendly, clear feedback during syncs/updates (not silent failure).
- Real multi-user support with proper per-user data isolation.
- Feature parity with the old app, plus the holes below actually filled in rather than stubbed.
- An API clean enough to support a native mobile app later.

## 2. Why a rewrite, not a patch
The old app's UI problems trace to its architecture: server-rendered Jinja pages, full-page reloads, per-page vanilla JS (`banks.js`, `goals.js`, `expenses.js`, ...) with no shared state or consistent async pattern. That's what produces "clunky," "not mobile friendly," and "no feedback on sync." Patching it page-by-page would keep hitting the same ceiling, so the UI layer is a full rewrite: SPA frontend + JSON API backend.

Known holes in the old app (confirmed in code, not guesses):
- `app/tasks/scheduled_tasks.py`: `sync_all_transactions`, `update_all_balances`, `process_recurring_bills` are empty stubs (`pass`). Scheduled auto-sync never ran — only webhook-triggered or manual sync worked.
- `app/tasks/report_tasks.py`: report generation has a `TODO`, never implemented. "Financial reports and analytics" from the old README didn't exist in practice.
- `SECURITY_AUDIT.md` documented missing auth on most write routes, no Plaid webhook signature verification, no CSRF protection, and real-looking DB credentials committed to git history. A later commit (`63723e4`) added per-user access control + CSRF, but the new build should bake these in from day one rather than retrofit them.

## 3. Architecture

**Backend:** FastAPI (Python), SQLAlchemy 2.0, PostgreSQL, Celery + Redis for background jobs. Keeps the Plaid Python SDK and DB engine from the old stack (low risk, proven), but replaces Flask's template-rendering routes with a typed JSON API (Pydantic schemas, auto-generated OpenAPI spec — useful for a typed frontend and later a native app).

**Frontend:** React + TypeScript SPA (Vite), mobile-responsive layout, a component library for consistent UI (e.g. shadcn/ui or Mantine — decide during setup). Talks to the API over JSON; no server-rendered pages.

**Auth & multi-user:** Real per-user accounts. Short-lived JWT access token (sent via `Authorization` header, not a cookie — avoids CSRF exposure for the API itself) + rotating refresh token in an httpOnly cookie (CSRF-protected on the refresh endpoint only). Every record (`Account`, `Transaction`, `Plaid_item`, etc.) is scoped to `owner_id`; every query derives the acting user from the verified token, never from client-supplied IDs — this was the old app's biggest security gap (routes trusting `user_id` from the request body).

**Background jobs & real-time feedback:** Celery beat actually runs `sync_transactions`, `update_balances`, `process_recurring_bills` on a schedule (not stubs). Each sync job writes a status record the frontend polls (e.g. every 2–3s while a job is in flight) to show live progress/success/failure instead of the old silent-fail pattern. Plaid webhooks remain the primary trigger for real-time updates; polling covers the scheduled/background path. (SSE/websockets are a reasonable v2 upgrade for push notifications — e.g. bill due reminders — not required for v1.)

**Mobile:** Responsive web now; backend is designed API-first (versioned, token-based auth, no server-rendered dependency) so a native app can be added later without backend rework.

**Deployment:** Undecided — keep it portable. Docker Compose for local/self-hosted (like before) now, structured so it can move to a cloud platform (Fly.io/Railway/Render) later without rearchitecting. Decide at build time.

## 4. Feature scope

All feature areas below are confirmed in active use — full parity target, not a trimmed-down v2.

| Area | Status | Notes |
|---|---|---|
| Accounts (checking/savings/credit card/investment/loan/mortgage/student loan) | Carry over | Revisit the data model (see §5) |
| Bank linking & sync (Plaid) | Carry over + fix | Add webhook signature verification; implement real scheduled sync |
| Transactions (list/search/filter) | Carry over + redesign UI | Main daily-use surface — prioritize mobile UX here |
| Categories + auto-categorization rules | Carry over | |
| Merchants | Carry over | |
| Budgets | Carry over | |
| Savings goals | Carry over | |
| Recurring transactions / bill reminders | Carry over + fix | `process_recurring_bills` never ran in old app |
| Notifications | Carry over + fix | Pair with real scheduled jobs + bill reminders |
| Assets (non-Plaid-linked net worth items) | Carry over | |
| Reports & analytics | **New** (was never implemented) | e.g. spending by category, monthly trends, net worth over time |
| Multi-user | **New** (old app was single-user in practice despite having a `User` model) | Real per-user isolation, each user links their own banks |

## 5. Data model notes
Carry over the old entity list (`User`, `Plaid_item`, `Bank`, `Account`, `Transaction`, `Category`, `CategoryRule`, `Merchant`, `Budget`, `SavingsGoal`, `RecurringTransaction`, `Asset`, `Notification`, `Webhook`, `PlaidAPICall`, etc.) as the starting point. One known awkwardness to fix: the old `Account` was specialized via sibling tables (`CreditCardAccount`, `SavingsAccount`, `CheckingAccount`, `InvestmentAccount`, `LoanAccount`, `Mortgage`, `StudentLoan`) instead of real inheritance, requiring route-by-route knowledge of which concrete model applies. Use SQLAlchemy joined-table or single-table inheritance (or a type-discriminator + JSON detail column) instead.

## 6. Security baseline (non-negotiable from day one)
- Every write route resolves the acting user from the verified token; never trust a client-supplied `user_id`/`account_id` for authorization, only for addressing (and always check ownership).
- Plaid webhook endpoint verifies the `Plaid-Verification` JWT before processing anything.
- No secrets (DB creds, JWT secrets, Plaid tokens) in git, ever — `.env`/config gitignored from commit 1, example file uses obvious placeholders.
- No access tokens or secrets in logs (mask to last 4-5 chars, as the old code did in one place).
- Rate limiting on login/register/refresh.
- Cookie flags: `Secure`, `HttpOnly`, `SameSite=Lax` on the refresh cookie once served over HTTPS.
- Locked-down CORS (specific origins, not wide open).

## 7. Open questions / next steps
- Component library choice for the frontend (shadcn/ui vs Mantine vs other) — decide during setup.
- Deployment target (self-host vs cloud) — left open, architecture stays portable either way.
- Household/shared-account model (e.g. partner sees shared accounts) — not raised yet; flag if relevant before building multi-user data model.
- Whether to import historical data from the old `finance-app` Postgres DB or start clean.
