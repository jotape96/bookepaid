# BookepAId Next.js Rewrite — Implementation Stages

Tracks progress rebuilding the backend (Prisma/NextAuth/API routes) and frontend UI
(matching the Claude Design prototype, project id `df8e52a5-0dbd-4eec-86b5-f8978eca6aea`)
inside `frontend/`, per the approved plan at
`/home/cachorro_cami/.claude/plans/i-need-you-to-glittery-quilt.md`.

Rules: `backend/` (Python/Streamlit) is never modified or deleted. Styling is CSS
Modules only — no Tailwind, no inline styles. Theme tokens + light/dark toggling live
in `frontend/src/app/globals.css`. Path alias is `#@/*` → `./src/*` (not `@/*`).

- [x] **S0 — Grounding** — read Next.js 16.2.12 docs (proxy, route handlers, `after()`, runtime config, auth guide); read the full Claude Design prototype (screens, design system, tokens/themes, landing page); `npx prisma db pull` against real Supabase DB, diff vs. planned schema.
  - Notes: S0 done — confirmed all 5 Next.js 16.2.12 API claims from the plan (proxy.ts rename w/ Node.js-only runtime, Promise-based route params, after() works on plain `next start` with no waitUntil plumbing, runtime="nodejs" required for Prisma, cookies()/headers() async) and the `#@/*` tsconfig alias. Fully read/decoded the Claude Design prototype: all screens in `BookePaid App.dc.html` (auth, onboarding x2 steps, invite, dashboard, upload incl. stepper/error states, ledger, invoice detail, plates, plate editor incl. match-ingredient modal, price history, export, settings incl. preview-empty toggle), the full design-system readme (Ledger/Counter direction + light/dark = 4 forms), every token/theme/CSS file (literal custom-property values captured), and confirmed `ds-base.js`/`support.js`/`_ds_bundle.js`/the `x-dc`/`sc-if`/`sc-for`/`DCLogic` markup are Claude-Design-canvas prototyping glue only — NOT to be ported; only the token values, class names, and component prop contracts are reusable. Full findings delivered in the S0 report to the main thread (npx prisma db pull against real Supabase not run in this pass — still pending for S1).
- [x] **S1 — Prisma schema + migration** — `schema.prisma`, additive migration, force-password-reset data migration.
  - Notes: Installed `prisma@7.9.1`/`@prisma/client`/`@prisma/adapter-pg`/`pg`/`dotenv`/`tsx` (pnpm `onlyBuiltDependencies` updated in `pnpm-workspace.yaml` for prisma/esbuild postinstall). **Prisma 7 changed conventions**: no `url =` in `schema.prisma` — connection info lives in `frontend/prisma.config.ts` (loads plain `.env` via `dotenv/config`, not `.env.local`); client generator needs `provider = "prisma-client"` + explicit `output` (`../src/generated/prisma`, gitignored); runtime client requires an explicit driver adapter (`@prisma/adapter-pg`), no more bare `new PrismaClient()`.
    **Connectivity finding**: the true direct connection (`db.<ref>.supabase.co:5432`) resolves to an IPv6-only address unreachable from this environment. Switched to Supabase's pooler (Supavisor) instead — transaction-mode (`:6543`, `pgbouncer=true`) for `DATABASE_URL`/app runtime, session-mode (`:5432`) for `DIRECT_URL`/Prisma CLI (transaction-mode hangs indefinitely on `db pull`/`migrate` — needs session-level Postgres features). Region resolved to `ca-central-1` by matching the IPv6 prefix against AWS's `ip-ranges.json`. Also found the password in `.env.local` was stale; corrected (both `.env.local` and CLI's `.env` now use `postgresql://postgres.amiyqvjfousaxdnatucw:<url-encoded-password>@aws-0-ca-central-1.pooler.supabase.com:{6543|5432}/postgres`).
    **Schema ground truth**: `npx prisma db pull` against the real project confirmed the `public` schema was genuinely empty (only Supabase-internal `auth`/`storage`/`realtime`/`extensions`/`vault` schemas existed) — user confirmed this is the correct, intentionally-empty project. Per user decision, originated `schema.prisma` from scratch (not an introspection reconciliation) using table/column names reconstructed from reading `backend/models.py`, `data.py`, `plates.py`, `invoice.py`, `app.py` directly, with conservative real types: `String @id @default(uuid()) @db.Uuid` PKs/FKs throughout; `@db.Date` for the three date-only columns (`invoices.date`, `line_items.date`, `plate_history.date` — Python truncates to `[:10]`); `@db.Timestamptz(6)` for new `created_at`/`updated_at` audit columns; `Decimal(12,2)` for money (`line_items.total`, `plates.selling_price`) vs `Decimal(12,4)` for sub-cent-precision quantities/prices (`line_items.quantity`/`unit_price`, `ingredients.quantity_kg`, `plate_history.cost` — all directly fed by Python's `round(x, 4)` calls). Added `UserRole` (owner|manager) and `LineItemCategory` (COGS|Packaging|Labour|Overhead|Other) enums, both `@map`-ed per-value to the exact-case strings `backend/` writes/reads (so raw supabase-py inserts keep matching the Postgres enum labels). All 7 base tables `@@map`-ed to their existing snake_case table names.
    **Additive scope layered in**: `users.password_hash` (nullable), `users.must_reset_password` (`Boolean @default(true)`), legacy `users.password` kept (nullable, sha256, never written by the new app); `invoices.storage_path`/`storage_bucket` (nullable); new `PasswordResetToken` model (`token_hash` unique, `expires_at`, `used_at`); new `InvoiceJob` model with `InvoiceJobSourceType` (INVOICE|MENU_ONBOARDING) and `InvoiceJobStatus` (PENDING|PROCESSING|DONE|FAILED, no finer sub-states, matching the plan's collapsed design) — all fields from the spec (`storage_path`/`bucket`, `original_filename`, `mime_type`, `file_size_bytes`, `estimated_duration_ms`, `started_at`/`finished_at`, `result_json`, `error_message`, nullable `invoice_id` FK, `created_at`/`updated_at`). No NextAuth adapter tables.
    **Migration**: `npx prisma migrate dev --name init` created and applied `prisma/migrations/20260731151352_init/` directly against the real DB — reviewed the generated SQL and confirmed it's 100% `CREATE TYPE`/`CREATE TABLE` (nothing to alter/drop since the DB was empty). Verified via a raw query that all 9 tables now exist in `public` (`businesses`, `users`, `invoices`, `line_items`, `plates`, `ingredients`, `plate_history`, `password_reset_tokens`, `invoice_jobs`) plus `_prisma_migrations` recording the applied migration.
    **`frontend/src/lib/prisma.ts`**: globalThis-cached singleton instantiating the generated client with `new PrismaPg({ connectionString: process.env.DATABASE_URL })` passed as the `adapter` option (Prisma 7's required pattern — no adapter, no working client).
    **Force-password-reset script**: written at `prisma/scripts/force-password-reset.ts` (`npx tsx ... --dry-run` counts only; without the flag it runs `updateMany`). Dry-run against the real DB reports 0 users (table is empty — no legacy rows exist yet, so running it for real today would be a no-op). Deliberately NOT executed for real — deferred to post-S2 per the plan's rollout order.
    Full project `tsc --noEmit` and `prisma validate`/`format` both clean.
- [ ] **S2 — Auth** — NextAuth v5 config, `proxy.ts`, `auth-guards.ts`, signup + password-reset routes.
  - Notes:
- [ ] **S3 — Design system port** — tokens/themes into `globals.css`, base layout shell.
  - Notes:
- [ ] **S4 — Login/reset-password/signup screens**
  - Notes:
- [ ] **S5 — Onboarding** — routes + screen.
  - Notes:
- [ ] **S6 — Invoice upload + job pipeline + stepped AI loading UI**
  - Notes:
- [ ] **S7 — Plate costing** — routes + screen.
  - Notes:
- [ ] **S8 — Dashboard** — aggregation routes + charts/screen.
  - Notes:
- [ ] **S9 — Settings / user management + exports** — users CRUD, CSV/PDF export, settings + error-state screens.
  - Notes:
- [ ] **S10 — Landing page**
  - Notes:
- [ ] **S11 — Verification pass** — parity checks, full click-through both themes, confirm `backend/` untouched.
  - Notes:
