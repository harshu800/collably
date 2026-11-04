# Production Readiness Checklist

Use this checklist before launching Collably to production. Each section groups related tasks. Mark items complete only after verification.

---

## Secrets & Configuration

- [ ] **All placeholder env vars replaced**
  - `CLERK_SECRET_KEY` is a real `sk_live_*` key (production startup rejects test keys)
  - `CLERK_PUBLISHABLE_KEY` is a real `pk_live_*` key (production startup rejects test keys)
  - `CLERK_WEBHOOK_SECRET` is a real `whsec_*` secret (not `whsec_REPLACE_ME`)
  - `CLERK_JWKS_URL`, `CLERK_ISSUER`, `APP_BASE_URL`, and `FRONTEND_BASE_URL` use HTTPS
  - `PAYOUT_FIELD_ENC_KEY` is a 32-byte base64-encoded key (not `change-me-base64-32-bytes-...`)
  - `FILE_TOKEN_SECRET` is at least 32 characters (not `change-me-min-32-chars-...`)
  - `MOCK_PAYMENT_WEBHOOK_SECRET` is a strong random string (not `change-me-mock-secret`)

- [ ] **Production environment flags set**
  - `ENV=prod`
  - `DEBUG=false`
  - `ENABLE_MOCK_PAYMENT_ENDPOINTS=false`

- [ ] **CORS configured**
  - `CORS_ORIGINS` set to your real frontend domain(s) (e.g., `https://collably.vercel.app`)
  - HTTPS origins only, with no paths, wildcard (`*`), or localhost origins (enforced at startup)

- [ ] **Proxy trust configured**
  - `TRUST_PROXY=true` (required for Fly.io, Render, or any reverse proxy)

- [ ] **Secrets stored securely**
  - Backend secrets set via `flyctl secrets set` or Render environment variables (never in `fly.toml` or `.env`)
  - Frontend `NEXT_PUBLIC_*` vars set in Vercel dashboard → Environment Variables
  - No secrets committed to git (verify `.gitignore` covers `.env`, `.env.local`, `.env.*`)

- [ ] **Transactional email configured**
  - Production requires `EMAIL_PROVIDER=smtp`; the console provider is development-only
  - Set `SMTP_HOST`, `SMTP_PORT`, and `SMTP_FROM_EMAIL`
  - Use SMTP port 465 (implicit TLS) or a port with mandatory STARTTLS support
  - Set `SMTP_USERNAME` and `SMTP_PASSWORD` together when the provider requires authentication
  - Confirm delivery, bounce handling, and sender-domain authentication (SPF/DKIM/DMARC) with your email provider
  - Apply migrations and run at least one `email_worker` process
  - Monitor queued/retrying/failed messages; SMTP delivery is at-least-once

---

## Authentication (Clerk)

- [ ] **Clerk webhook endpoint created**
  - Endpoint URL: `https://your-backend/api/v1/clerk/webhook`
  - Subscribed to: `user.created`, `user.updated`, `user.deleted`
  - `CLERK_WEBHOOK_SECRET` matches the signing secret from Clerk dashboard

- [ ] **Clerk allowed origins configured**
  - Clerk dashboard → Settings → Paths → Allowed origins includes your Vercel domain (e.g., `https://collably.vercel.app`)

- [ ] **Clerk JWKS and Issuer set**
  - `CLERK_JWKS_URL` points to your Clerk instance (e.g., `https://your-tenant.clerk.accounts.dev/.well-known/jwks.json`)
  - `CLERK_ISSUER` matches your Clerk instance (e.g., `https://your-tenant.clerk.accounts.dev`)

- [ ] **Test auth end-to-end**
  - Sign up via Clerk on your Vercel domain
  - Verify user is created in the database (check `users` table)
  - Verify user is redirected to `/onboarding`
  - Verify `GET /api/v1/users/me` returns the user's profile

- [ ] **Admin account created**
  - Sign in via Clerk at least once
  - Run: `flyctl ssh console --app collably-api -C "python -m app.cli grant_admin your@email.com"`
  - Verify admin privileges in the frontend (e.g., access to admin reports)

---

## Database

- [ ] **Alembic migrations applied**
  - Run: `flyctl ssh console --app collably-api -C "cd /app && alembic upgrade head"` (Fly.io)
  - Or via Render Shell: `cd /app && alembic upgrade head` (Render)
  - Verify no errors in logs

- [ ] **Daily backups configured**
  - Fly.io Postgres auto-backups enabled: `flyctl postgres backup list --app collably-db`
  - Or Render Postgres backups enabled (paid plan only)

- [ ] **Test backup restore (staging/dev)**
  - Restore a backup to a test database
  - Verify data integrity

- [ ] **Connection pooling configured (optional for high traffic)**
  - Consider PgBouncer or Fly.io's built-in connection pooling for >100 concurrent connections

---

## Private File Storage

- [ ] **S3 bucket created in the approved data region**
  - Configure `S3_BUCKET` and `S3_REGION`
  - For India data residency, confirm the selected region and contractual requirements before use
- [ ] **Bucket access is private**
  - Block public access and do not grant public ACLs
  - Require TLS in the bucket policy
  - Restrict the app identity to the required bucket and object operations
- [ ] **Credentials and encryption configured**
  - Prefer a short-lived workload identity; otherwise use a dedicated least-privilege key stored only as a deployment secret
  - S3 uploads request server-side AES-256 encryption
  - Require TLS in the bucket policy and block public access at account and bucket level
  - Enable and test key rotation/revocation procedures
- [ ] **Application identity permissions restricted**
  - Grant `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` only on `arn:aws:s3:::<bucket>/collably/*`
  - Grant multipart upload cleanup/list permissions only where required by the SDK
  - Do not grant public ACL, bucket policy administration, or account-wide access
- [ ] **File lifecycle verified**
  - Test authorized upload/download/delete and unauthorized access in staging
  - Test backup/versioning and restore according to the retention policy
  - Confirm object deletion behavior for user deletion and legal retention requirements

---

## Health & Monitoring

- [ ] **Health endpoints operational**
  - `curl https://your-backend/api/v1/health` returns `{"status":"ok"}` (200)
  - `curl https://your-backend/api/v1/health/ready` returns `{"status":"ready","db":"connected"}` (200)
  - `curl https://your-backend/api/v1/health/live` returns `{"status":"live"}` (200)

- [ ] **Frontend loads**
  - `curl https://your-frontend` returns HTML (200)
  - Landing page renders in browser
  - No CORS errors in browser console

- [ ] **Error tracking configured (recommended)**
  - Sentry, Rollbar, or similar integrated
  - Test error capture: trigger a 500 error and verify it appears in your error tracker

- [ ] **Uptime monitoring configured (recommended)**
  - UptimeRobot, Pingdom, or similar pinging `/api/v1/health` every 5 minutes
  - Email/SMS alerts on downtime

- [ ] **SSL/TLS verified**
  - Fly.io and Vercel auto-provision SSL certificates
  - Verify HTTPS works: visit `https://your-backend` and `https://your-frontend`
  - Check SSL certificate validity: `curl -I https://your-backend`

---

## Payments (BLOCKER for Real Money)

**Razorpay is selected in the Fly production template, but provider accounts and staging have not been verified.** Do NOT accept real money until the following are complete:

- [ ] **Razorpay live keys configured**
  - `PAYMENT_PROVIDER=razorpay`
  - `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and `RAZORPAYX_ACCOUNT_NUMBER` configured in the secret manager
  - Complete test-mode end-to-end validation before any live credentials are configured
  - Confirm webhook event IDs deduplicate retries and payment state is reconciled against expected order, amount, and currency

- [ ] **Legal documents reviewed**
  - Terms of Service published (link in footer)
  - Privacy Policy published (link in footer)
  - Refund Policy published (link in footer)

- [ ] **RBI PA/PG licensing assessed**
  - Reserve Bank of India Payment Aggregator (PA) or Payment Gateway (PG) licensing requirements evaluated
  - If required, license obtained or exemption documented

- [ ] **KYC for payouts implemented**
  - Live provider payouts fail closed unless `CreatorPayoutMethod.verified` is true
  - Select and integrate a KYC provider for creator identity checks (PAN and any other legally required checks)
  - RazorpayX fund-account creation alone does not verify creator identity or prove ownership of the payout destination
  - RazorpayX account validation is documented as RazorpayX Lite-only and unavailable in test mode; this deployment uses a RazorpayX current/other account, so select a separate payout-account verification path

- [ ] **Test real payment flow**
  - Test Razorpay sandbox integration (dev)
  - Test Razorpay live integration (staging with test cards)
  - Verify webhook delivery: `POST /api/v1/payment-webhooks/razorpay`
  - Verify full refund creation, retries with the same idempotency key, `refund.processed`/`refund.failed` webhooks, and retry after a failed refund
  - Keep live-money dispute refunds disabled operationally until the full refund lifecycle passes staging verification

---

## Compliance & Legal

- [ ] **DPDP Act (India) obligations reviewed**
  - Data processing notice published
  - User consent flows implemented (if required)
  - Data deletion flow implemented (`/api/v1/users/me` DELETE endpoint)
  - Data portability flow implemented (if required)

- [ ] **GST invoicing planned**
  - Brand-side spend invoicing (if acting as a marketplace aggregator)
  - Creator-side receipts (for tax reporting)

- [ ] **Accessibility (WCAG) reviewed**
  - Manual testing with screen reader (NVDA, JAWS, or VoiceOver)
  - Keyboard navigation tested
  - Color contrast verified (WCAG AA minimum: 4.5:1 for body text, 3:1 for large text)
  - Full WCAG 2.1 AA certification requires expert audit

---

## Pre-Launch End-to-End Test

- [ ] **Full collaboration flow (mock payments)**
  - Brand creates campaign
  - Creator applies to campaign
  - Brand approves application → collab created
  - Collab progresses through deliverables (submit → approve)
  - Mock payment triggered (via `POST /api/v1/mock-payments/trigger`)
  - Payment status updates to `succeeded`
  - Collab status updates to `delivered`

- [ ] **Sign-up flow**
  - Sign up via Clerk
  - Redirected to `/onboarding`
  - Complete onboarding (creator or brand profile)
  - Redirected to appropriate dashboard

- [ ] **File upload flow**
  - Upload profile picture (creators)
  - Upload campaign brief (brands)
  - Upload deliverable (creators)
  - Verify signed download URL works (`GET /api/v1/files/:id/download`)

- [ ] **Notification flow**
  - Trigger notification (e.g., application approved)
  - Verify notification appears in frontend (`GET /api/v1/notifications`)
  - Mark as read
  - Verify unread count updates

---

## Deployment Verification

- [ ] **Backend deployed**
  - Fly.io: `flyctl status --app collably-api` shows `running`
  - Or Render: web service status is `Live`

- [ ] **Frontend deployed**
  - Vercel: project status is `Ready`
  - Production URL accessible

- [ ] **Logs accessible**
  - Backend: `flyctl logs --app collably-api` or Render logs
  - Frontend: Vercel dashboard → Deployments → Logs

- [ ] **Scaling tested (optional for MVP)**
  - Backend: `flyctl scale count 2 --app collably-api` (spin up 2 instances)
  - Load test with Apache Bench or k6
  - Roll back: `flyctl scale count 1 --app collably-api`

---

## Post-Launch Monitoring

- [ ] **Monitor logs daily (first week)**
  - Check for errors, exceptions, or anomalies
  - Verify Clerk webhook delivery
  - Verify database performance

- [ ] **Monitor uptime**
  - Check uptime monitor dashboard
  - Verify health endpoints return 200

- [ ] **Monitor Vercel and Fly.io usage**
  - Verify free tier limits not exceeded
  - Plan for scaling if traffic grows

- [ ] **User feedback loop**
  - Set up a feedback form or support email
  - Monitor for bug reports, feature requests

---

## What's NOT Ready (MVP Limitations)

These features are out of scope for v1 but should be planned for future releases:

- Razorpay / RazorpayX has not passed staging verification or production/compliance sign-off
- Creator KYC and payout-account verification provider has not been selected or integrated
- Actual money movement for dispute `split` resolutions (recorded as bookkeeping only in v1)
- Terms and privacy pages are placeholders and require legal review and publication before public launch
- SMTP delivery is implemented but must be configured and verified with a production email provider
- Production S3 bucket policy, IAM permissions, backups, restore, and real upload/download flows must be configured and tested in the hosting account
- Database backups, restore, migrations, auth webhooks, and end-to-end flows must be verified in staging
- AI matching, mobile apps, rich chat, subscription tiers, public ratings, affiliate tracking
- Full WCAG certification; multi-language; multi-currency
- SOC2 / ISO / DPDP Act compliance implementation

---

## Final Checklist Summary

Before accepting real money:

1. ✅ All secrets replaced (no placeholders)
2. ✅ Clerk webhook configured and tested
3. ✅ Database migrations applied and backups configured
4. ✅ Health endpoints operational
5. ✅ Full end-to-end test passed (mock payments)
6. ❌ **BLOCKER:** Razorpay sandbox integration, live-readiness review, and payout configuration verified
7. ❌ **BLOCKER:** Legal docs published (ToS, Privacy Policy)
8. ❌ **BLOCKER:** RBI licensing requirements assessed
9. ❌ **BLOCKER:** KYC for payouts implemented

**Do NOT accept real money until all blockers are resolved.**

---

## Next Steps After Launch

- Monitor logs and uptime daily for the first week
- Gather user feedback and prioritize feature requests
- Complete Razorpay staging verification before enabling live payments
- Select and integrate a payout KYC provider before enabling live payouts
- Plan legal review for ToS, Privacy Policy, and RBI compliance
