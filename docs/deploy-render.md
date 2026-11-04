# Deploy Collably Backend to Render (Alternative to Fly.io)

[Render](https://render.com) is a simpler alternative to Fly.io for deploying the Collably backend. It provides managed Postgres, Docker-based web services, and automatic deployments from GitHub.

## Why Render?

- **Simpler setup:** No CLI required for basic deploys (can use dashboard)
- **Free tier:** Free Postgres (limited), free web service (suspended after inactivity)
- **Auto-deploy:** Connect GitHub and auto-deploy on push to `main`
- **Managed Postgres:** No manual volume management

**Tradeoffs vs. Fly.io:**
- Free tier web services spin down after 15 minutes of inactivity (first request after spin-down takes ~30s)
- Less control over VM configuration and regions (Render's default India region is `singapore`, not Mumbai)
- Render's free Postgres expires after 90 days (must upgrade to paid or migrate)

## Prerequisites

- A [Render](https://render.com) account (free tier available)
- Your Collably repository pushed to GitHub
- A Clerk application configured with production keys

## Step 1: Create a Render Account and Connect GitHub

1. Sign up at [render.com](https://render.com)
2. Go to **Account Settings → GitHub** and connect your GitHub account
3. Grant Render access to your Collably repository

## Step 2: Create a Postgres Database

1. In the Render dashboard, click **New +** → **PostgreSQL**
2. Configure:
   - **Name:** `collably-db`
   - **Database:** `collably_prod`
   - **User:** `collably` (auto-generated)
   - **Region:** `Singapore` (closest to India on free tier; paid plans offer more regions)
   - **Plan:** **Free** (for MVP; expires after 90 days) or **Starter** ($7/month)
3. Click **Create Database**

Render will provision the database and provide an **Internal Database URL** and an **External Database URL**. Copy the **Internal Database URL** (starts with `postgresql://`).

## Step 3: Create the Web Service

1. In the Render dashboard, click **New +** → **Web Service**
2. Select your GitHub repository (`collably`)
3. Configure:
   - **Name:** `collably-api`
   - **Region:** `Singapore` (or closest available)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Environment:** `Docker`
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Plan:** **Free** (for MVP) or **Starter** ($7/month for no spin-down)

## Step 4: Set Environment Variables

In the web service settings, go to **Environment** and add the following variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENV` | `prod` | |
| `DEBUG` | `false` | |
| `DATABASE_URL` | `<Internal Database URL from Step 2>` | Change `postgresql://` to `postgresql+asyncpg://` |
| `DATABASE_URL_SYNC` | `<Internal Database URL from Step 2>` | Change `postgresql://` to `postgresql+psycopg2://` |
| `CLERK_SECRET_KEY` | `your_clerk_secret_key` | From Clerk dashboard |
| `CLERK_PUBLISHABLE_KEY` | `your_clerk_publishable_key` | From Clerk dashboard |
| `CLERK_WEBHOOK_SECRET` | `your_clerk_webhook_secret` | From Clerk webhook settings |
| `CLERK_JWKS_URL` | `https://your-tenant.clerk.accounts.dev/.well-known/jwks.json` | From Clerk dashboard |
| `CLERK_ISSUER` | `https://your-tenant.clerk.accounts.dev` | From Clerk dashboard |
| `PAYOUT_FIELD_ENC_KEY` | `<base64-32-bytes>` | Generate: `openssl rand -base64 32` |
| `FILE_TOKEN_SECRET` | `<min-32-chars>` | Generate: `openssl rand -hex 32` |
| `MOCK_PAYMENT_WEBHOOK_SECRET` | `<random-string>` | Generate: `openssl rand -hex 32` |
| `CORS_ORIGINS` | `https://collably.vercel.app` | Replace with your Vercel domain |
| `TRUST_PROXY` | `true` | |
| `ENABLE_MOCK_PAYMENT_ENDPOINTS` | `false` | |
| `PAYMENT_PROVIDER` | `mock` | |
| `STORAGE_PROVIDER` | `s3` | Production requires private object storage |
| `S3_BUCKET` | `<private bucket name>` | Create a private bucket in an approved region |
| `S3_REGION` | `<bucket region>` | For example, `ap-south-1` if approved for your data residency needs |
| `S3_ACCESS_KEY_ID` | `<least-privilege key>` | Optional only when using a supported workload identity/default credential chain |
| `S3_SECRET_ACCESS_KEY` | `<least-privilege secret>` | Set with the access key, or leave both blank for workload identity |
| `APP_BASE_URL` | `https://collably-api.onrender.com` | Replace with your Render URL |
| `FRONTEND_BASE_URL` | `https://collably.vercel.app` | Replace with your Vercel domain |
| `EMAIL_PROVIDER` | `smtp` | Production rejects the console provider |
| `SMTP_HOST` | `<provider SMTP hostname>` | Use your email provider's authenticated SMTP endpoint |
| `SMTP_PORT` | `587` | Requires STARTTLS; port `465` uses implicit TLS |
| `SMTP_FROM_EMAIL` | `notifications@your-domain.example` | Verify sender/domain with your provider |
| `SMTP_USERNAME` | `<SMTP username>` | Set with `SMTP_PASSWORD`, or leave both blank if provider requires no auth |
| `SMTP_PASSWORD` | `<SMTP password>` | Store as a protected Render environment secret |

Keep the S3 bucket private: block public access, require TLS, and grant the app only the
necessary object permissions. Uploads request server-side AES-256 encryption. Do not make
the bucket public to work around an application permissions error.
If using AWS S3, see [the Fly.io guide](./deploy-flyio.md#step-4a-configure-private-s3-storage)
for an example TLS-only bucket policy and a narrow object-access policy. Render does not
automatically provide AWS credentials; configure a supported identity mechanism or set a
dedicated least-privilege key pair as protected environment secrets.

**Important:** Render's Internal Database URL uses `postgresql://` by default. You must change the protocol:
- For `DATABASE_URL`: change to `postgresql+asyncpg://`
- For `DATABASE_URL_SYNC`: change to `postgresql+psycopg2://`

## Step 5: Create the Email Background Worker

Create a separate Render **Background Worker** from the same repository:

- Root Directory: `backend`
- Environment: `Docker`
- Dockerfile Path: `backend/Dockerfile`
- Start Command: `python -m app.cli email_worker`
- Copy the web service's database, Clerk, storage, and email environment variables

The worker and web service share the durable email outbox in Postgres. Do not
run the worker until migrations are applied. Configure at least one worker
instance and monitor its logs for `email_delivery_failed` and
`email_delivery_succeeded`.

Delivery is at-least-once: if a worker crashes after the SMTP server accepts a
message but before the database records success, the message can be sent again.

## Step 6: Deploy

Click **Create Web Service**. Render will:
1. Clone your repository
2. Build the Docker image from `backend/Dockerfile`
3. Start the uvicorn server
4. Assign a URL like `https://collably-api.onrender.com`

The first deploy takes ~3-5 minutes.

## Step 7: Run Database Migrations

Render provides a **Shell** interface to run commands inside the running service.

1. In the web service dashboard, click **Shell** (top right)
2. Run:

```bash
cd /app
alembic upgrade head
```

This creates all tables and applies migrations.

## Step 8: Verify the Deployment

Check the health endpoint:

```bash
curl https://collably-api.onrender.com/api/v1/health/ready
```

Expected response:

```json
{"status":"ready","db":"connected"}
```

## Step 8: Configure Auto-Deploy

Render automatically deploys on every push to the `main` branch. To disable or change:

1. Go to **Settings → Build & Deploy**
2. Toggle **Auto-Deploy**

## Step 9: Deploy the Frontend to Vercel

Follow [deploy-vercel.md](./deploy-vercel.md) to deploy the frontend, using:

```
NEXT_PUBLIC_API_BASE_URL=https://collably-api.onrender.com/api/v1
```

## Optional: Create an Admin User

After deploying and setting up Clerk, sign in to the frontend once, then promote yourself to admin via the Render Shell:

```bash
cd /app
python -m app.cli grant_admin your@email.com
```

## Upgrading from Free Tier

Render's free web service spins down after 15 minutes of inactivity. To keep it always-on:

1. Go to **Settings → Plan**
2. Upgrade to **Starter** ($7/month)

Render's free Postgres expires after 90 days. To keep it permanently:

1. Go to the database settings
2. Upgrade to **Starter** ($7/month)

## Comparison: Render vs. Fly.io

| Feature | Render Free | Render Starter | Fly.io Free | Fly.io Paid |
|---------|-------------|----------------|-------------|-------------|
| **Cost** | $0 | $14/month (web + db) | $0 | ~$5/month |
| **Spin-down** | Yes (15 min idle) | No | Yes (auto-stop) | No |
| **Postgres expiry** | 90 days | Permanent | Permanent | Permanent |
| **Region (India)** | Singapore | Singapore | Mumbai (bom) | Mumbai (bom) |
| **Setup complexity** | Low (dashboard) | Low | Medium (CLI) | Medium |
| **Auto-deploy** | Yes (GitHub) | Yes | Yes (GitHub Actions) | Yes |

**Recommendation:**
- **MVP / Hobby:** Render free tier (accept spin-down delay)
- **Production (low cost):** Fly.io free tier + paid Postgres (~$2/month)
- **Production (simple):** Render Starter ($14/month, no spin-down, simpler ops)

## Troubleshooting

### Build fails

Check **Logs** in the Render dashboard for build errors.

### Database connection fails

- Verify `DATABASE_URL` is the **Internal Database URL** (not External)
- Verify the protocol is `postgresql+asyncpg://` (not `postgresql://`)
- Check that the database is in the same region as the web service (or upgrade both to paid for cross-region access)

### Migrations fail

Run migrations manually via Shell (see Step 6).

### Service spins down (free tier)

Expected behavior. First request after spin-down takes ~30s. Upgrade to Starter to keep always-on.

## Frontend Deployment

For the frontend, still use Vercel (see [deploy-vercel.md](./deploy-vercel.md)). Render's Static Sites do not support Next.js App Router with server components.

## Next Steps

- [Complete the production checklist](./production-checklist.md)
- Configure uptime monitoring (e.g., UptimeRobot) to ping the service every 5 minutes (prevents spin-down on free tier)
- Set up error tracking (e.g., Sentry)
