# Collably — India-First Creator–Brand Marketplace (MVP)

Collably is a two-sided marketplace connecting UGC creators and influencers with Indian D2C brands. This repository holds the MVP implementation: a FastAPI backend, a Next.js 14 App Router frontend, and a Postgres database. The internal package names (`backend`, `frontend`) stay functional and are not renamed.

> This is an early-stage MVP. Nothing in this repository is a legal, financial, or regulatory statement. Real-money flows are not approved for production until the payment and compliance launch gates below have passed.

## Prerequisites

- **Node.js** 20 or newer
- **Python** 3.11 or newer
- **Docker Desktop** (for the local Postgres container)
- **Git**
- A **Clerk** account (see "Clerk setup" below)

Verify on your machine:

```powershell
# Windows PowerShell
node --version
python --version
docker --version
```

```bash
# macOS / Linux
node --version
python --version
docker --version
```

## Clerk setup

Authentication is handled by [Clerk](https://clerk.com). You need a Clerk application wired up before sign-in will work end to end.

- Create a Clerk account and a new **application**. Enable **Email + Password**; **Google OAuth** is optional but recommended.
- From the Clerk dashboard copy the **Publishable key** into `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (frontend `.env.local`) and the **Secret key** into `CLERK_SECRET_KEY` (both `backend/.env` and `frontend/.env.local`).
- Copy the **JWKS URL** and the **Issuer** (frontend API URL) into `CLERK_JWKS_URL` and `CLERK_ISSUER` in `backend/.env`.
- Add a **webhook endpoint** pointing at `http://localhost:8000/api/v1/clerk/webhook` (use `svix-cli listen` or an `ngrok` tunnel for local dev). Subscribe it to the `user.created`, `user.updated`, and `user.deleted` events, then copy its **signing secret** into `CLERK_WEBHOOK_SECRET` in `backend/.env`.
- The backend boots with placeholder Clerk values so you can run migrations and start the server, but real sign-in requires the keys above. Prod boot refuses placeholder or empty Clerk values.

## First-time setup

### 1. Clone and configure environment

```powershell
# Windows PowerShell (from the repository root)
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
```

```bash
# macOS / Linux
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Open `backend/.env` and replace the placeholder values for the Clerk keys (see "Clerk setup"), `FILE_TOKEN_SECRET` (at least 32 chars, used only for signed download URLs — rotate independently of Clerk), `MOCK_PAYMENT_WEBHOOK_SECRET`, and `PAYOUT_FIELD_ENC_KEY` before anything is deployed. The placeholders are fine for local development only.

### 2. Start Postgres

```powershell
docker compose up -d postgres
docker compose exec postgres pg_isready -U marketplace
```

```bash
docker compose up -d postgres
docker compose exec postgres pg_isready -U marketplace
```

Expect `accepting connections`.

### 3. Install and migrate the backend

```powershell
# Windows PowerShell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
```

```bash
# macOS / Linux
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
```

### 4. Install and run the frontend

```powershell
cd ..\frontend
npm install
npm run dev
```

```bash
cd ../frontend
npm install
npm run dev
```

The landing page serves at <http://localhost:3000>.

### 5. Run the backend

In a second terminal (with the venv activated):

```powershell
cd backend
uvicorn app.main:app --port 8000 --reload
```

```bash
cd backend
uvicorn app.main:app --port 8000 --reload
```

Smoke check: `curl http://localhost:8000/api/v1/health` returns `{"status":"ok"}`. For readiness with database connectivity: `curl http://localhost:8000/api/v1/health/ready` returns `{"status":"ready","db":"connected"}`.

### 6. Run the email worker

In another backend terminal, start the outbox worker:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.cli email_worker
```

Notifications enqueue email in the same database transaction. The worker sends
queued messages using `EMAIL_PROVIDER` and retries transient failures. The
development default (`console`) logs email metadata only; configure SMTP in
`backend/.env` to deliver real email. Apply the Alembic migrations before
starting the worker.

## Admin creation

Admin accounts cannot be registered through the public API. The user must sign in via Clerk at least once first — that first sign-in auto-provisions a local row on `GET /api/v1/users/me`. Then promote them from the CLI:

```powershell
cd backend
python -m app.cli grant_admin admin@example.com
```

```bash
cd backend
python -m app.cli grant_admin admin@example.com
```

The identifier may be either the user's email or their Clerk user id. The command is idempotent and prints the promoted user's id, Clerk id, and email.

## Seed demo data

`python -m app.cli seed_demo` creates a demo brand and demo creator keyed by placeholder Clerk ids (`demo_brand_clerk_id` and `demo_creator_clerk_id`). To actually sign in as these demo users, create matching Clerk accounts in your Clerk application and set each account's **external_id** to the corresponding placeholder (`demo_brand_clerk_id` / `demo_creator_clerk_id`). Without that step the demo rows exist in Postgres but no Clerk user maps to them.

## Running the tests

Backend tests run against a dedicated database (`marketplace_test`) and run `alembic upgrade head` once per session, so Postgres must be up (`docker compose up -d postgres`). `backend/tests/conftest.py` sets `TESTING_BYPASS_CLERK=true` plus an ephemeral `TESTING_CLERK_LOCAL_SECRET` before importing `app.*`, which switches the Clerk verifier to a local HS256 shim for the test suite only. **Never set `TESTING_BYPASS_CLERK` when `ENV=prod`** — the production startup check refuses to boot if it is truthy.

```powershell
cd backend
pytest -q
```

```bash
cd backend
pytest -q
```

Frontend:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
npm run test
```

## Payments disclosure

**Do not enable real payments in production yet.** The Razorpay / RazorpayX adapter is under integration and requires verified staging tests, webhook idempotency checks, provider credentials, payout-account configuration, and compliance review. Real payouts additionally require a provider-driven payout-method verification flow. The production deployment defaults to mock payment mode with mock endpoints disabled.

## Deployment

Collably is designed to deploy with:
- **Backend:** Fly.io (Mumbai region) or Render
- **Frontend:** Vercel
- **Database:** Managed Postgres on Fly.io or Render
- **File storage:** private S3 bucket; local filesystem is for development only

See the detailed deployment guides:
- [Deploy Backend to Fly.io](./docs/deploy-flyio.md) — step-by-step guide for deploying the FastAPI backend to Fly.io with managed Postgres in the Mumbai (`bom`) region
- [Deploy Frontend to Vercel](./docs/deploy-vercel.md) — step-by-step guide for deploying the Next.js frontend to Vercel
- [Deploy Backend to Render](./docs/deploy-render.md) — alternative deployment guide for Render (simpler setup, free tier with spin-down)
- [Production Checklist](./docs/production-checklist.md) — complete checklist before launching to production

Quick summary: the backend runs as a Docker container on Fly.io or Render, the frontend deploys to Vercel with zero config, and the database is a managed Postgres instance. All secrets are managed via `flyctl secrets set` (Fly.io) or Render/Vercel environment variables (never committed to git).

## Secrets Management

Collably uses environment variables for all configuration. Secrets are never committed to git.

- **Backend secrets:** Set via `flyctl secrets set` (Fly.io) or Render dashboard → Environment Variables. See `.env.example` for required variables.
- **Frontend secrets:** Set via Vercel dashboard → Settings → Environment Variables. `NEXT_PUBLIC_*` vars are baked at build time; runtime-only vars (e.g., `CLERK_SECRET_KEY`) can be updated without redeploying.
- **Rotation:** Keys can be rotated independently. Generate new secrets:
  - `PAYOUT_FIELD_ENC_KEY`: `openssl rand -base64 32`
  - `FILE_TOKEN_SECRET`: `openssl rand -hex 32`
  - Clerk keys: regenerate from Clerk dashboard
- **Verification:** Before any public push or deploy, verify `.gitignore` covers `.env`, `.env.local`, and `.env.*` files. Never commit secrets to git.

## Production Readiness Status

**What IS ready:**
- Infrastructure: Docker containers, multi-stage builds, health checks (`/health`, `/health/ready`, `/health/live`)
- Configuration: production validation in `validate_production()` refuses to boot with placeholder secrets or insecure defaults (`ENV=prod`)
- Authentication: Clerk integration with webhook-driven user sync
- Dashboards: creator and brand dashboards with profile management
- Campaigns: campaign creation, application flow, collab management
- Deliverables: deliverable submission and approval flow
- Mock payments: end-to-end collab flow with mock payment provider
- CORS: configurable origins, no wildcards in prod
- Secrets: encrypted payout fields (AES-256-GCM), signed file download tokens (HS256)

**What is NOT ready (blockers for real money):**
- Razorpay / RazorpayX production release: the adapter has not passed staging verification; payout configuration, sandbox testing, and compliance sign-off remain required
- Legal documents: Terms of Service, Privacy Policy, Refund Policy (must be published before accepting payments)
- RBI PA/PG licensing: Reserve Bank of India Payment Aggregator or Payment Gateway licensing requirements (must be assessed)
- KYC for payouts: `CreatorPayoutMethod.verified` is a boolean; real provider verification flow not implemented (PAN, Aadhaar, etc.)
- DPDP Act compliance: Digital Personal Data Protection Act obligations not implemented

See [docs/production-checklist.md](./docs/production-checklist.md) for the complete pre-launch checklist.

## Not implemented (v1)

- Production approval and full staging verification of the Razorpay / RazorpayX integration.
- Real `CreatorPayoutMethod.verified` provider verification flow.
- Actual money movement for dispute `split` resolutions (recorded as bookkeeping only in v1).
- AI matching, mobile apps, rich chat, subscription tiers, public ratings, affiliate tracking.
- Full WCAG certification; multi-language; multi-currency.
- SOC2 / ISO / DPDP Act compliance implementation.
- Clerk integration tested only against placeholder config; a real Clerk account must be configured for sign-in to work end-to-end.

## India compliance TODOs

- RBI PA/PG licensing requirements for payment aggregation.
- GST invoicing for brand-side spend and creator-side receipts.
- Escrow / nodal account terminology — current MVP uses the mock provider only.
- KYC for payouts (PAN / Aadhaar — not currently stored).
- Digital Personal Data Protection Act (DPDP) obligations.

Legal review is required before accepting real money through this platform.
