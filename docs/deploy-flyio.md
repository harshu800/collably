# Deploy Collably Backend to Fly.io

This guide walks through deploying the Collably FastAPI backend to [Fly.io](https://fly.io) in the Mumbai (`bom`) region, with a managed Postgres database.

## Prerequisites

- A [Fly.io](https://fly.io) account (free tier available)
- [flyctl CLI](https://fly.io/docs/hands-on/install-flyctl/) installed and authenticated
- Docker Desktop running (for building the image)
- A Clerk application configured with production keys

Verify flyctl:

```bash
flyctl version
flyctl auth login
```

## Step 1: Create Fly.io Postgres Database

Create a managed Postgres cluster in the Mumbai region:

```bash
flyctl postgres create --name collably-db --region bom
```

When prompted:
- Select the **Development** configuration (free tier: 1 shared CPU, 256MB RAM, 1GB storage)
- Or choose a larger plan for production

Note the connection details provided after creation. Fly.io will automatically provision a `DATABASE_URL` when you attach the database in the next step.

## Step 2: Create the Application

From the repository root, create the Fly.io app:

```bash
flyctl apps create collably-api
```

This reserves the name `collably-api.fly.dev`.

## Step 3: Attach Postgres to the Backend

Attach the database to your app. This automatically sets the `DATABASE_URL` secret:

```bash
flyctl postgres attach collably-db --app collably-api
```

Fly.io will inject both `DATABASE_URL` (async, `postgresql+asyncpg://...`) and `DATABASE_URL_SYNC` (for Alembic migrations).

## Step 4: Set Application Secrets

Set all required secrets. Replace placeholders with your real Clerk keys and generated secrets:

```bash
flyctl secrets set \
  CLERK_SECRET_KEY=your_clerk_secret_key \
  CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key\
  CLERK_WEBHOOK_SECRET=your_clerk_webhook_secret \
  CLERK_JWKS_URL=https://your-tenant.clerk.accounts.dev/.well-known/jwks.json \
  CLERK_ISSUER=https://your-tenant.clerk.accounts.dev \
  PAYOUT_FIELD_ENC_KEY=$(openssl rand -base64 32) \
  FILE_TOKEN_SECRET=$(openssl rand -hex 32) \
  MOCK_PAYMENT_WEBHOOK_SECRET=$(openssl rand -hex 32) \
  EMAIL_PROVIDER=smtp \
  SMTP_HOST=smtp.your-email-provider.example \
  SMTP_PORT=587 \
  SMTP_FROM_EMAIL=notifications@your-domain.example \
  SMTP_USERNAME=your-smtp-username \
  SMTP_PASSWORD=your-smtp-password \
  --app collably-api
```

**Notes:**
- `PAYOUT_FIELD_ENC_KEY`: 32-byte base64-encoded key for AES-256-GCM encryption of payout account numbers
- `FILE_TOKEN_SECRET`: at least 32 characters, used for signed download URLs
- `MOCK_PAYMENT_WEBHOOK_SECRET`: used by the mock payment provider (even though `ENABLE_MOCK_PAYMENT_ENDPOINTS=false` in prod, the secret must be non-placeholder)
- The Fly production template selects `PAYMENT_PROVIDER=razorpay`. Configure `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, and `RAZORPAYX_ACCOUNT_NUMBER` as Fly secrets before starting the service; production startup fails closed if they are missing.
- Begin with Razorpay test credentials in a separate staging app and complete the payment, payout, refund, and webhook checks. Do not put live credentials in the staging app or use live credentials until the release gates in the checklist pass.
- Production requires SMTP email configuration. Use port 465 for implicit TLS or a provider port that requires STARTTLS; set both SMTP credentials or neither. Authenticate your sender domain with the provider before launch.

## Step 4a: Configure Private S3 Storage

The production Fly configuration requires S3; local disk storage is for development only.
Create a private bucket in the data region approved for your deployment, block all public
access, require TLS, and grant the app identity only the required bucket/object permissions.
Uploads request server-side AES-256 encryption. Configure the bucket and region:

```bash
flyctl secrets set S3_BUCKET=your-private-bucket S3_REGION=ap-south-1 --app collably-api
```

For AWS S3, block public access at both the account and bucket levels. A bucket policy should
deny non-TLS requests:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::your-private-bucket",
        "arn:aws:s3:::your-private-bucket/*"
      ],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    },
    {
      "Sid": "RequireServerSideEncryption",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::your-private-bucket/collably/*",
      "Condition": {
        "StringNotEquals": {
          "s3:x-amz-server-side-encryption": "AES256"
        }
      }
    }
  ]
}
```

Attach an identity policy granting `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`,
`s3:AbortMultipartUpload`, and `s3:ListMultipartUploadParts` only on
`arn:aws:s3:::your-private-bucket/collably/*`. Do not grant public access or bucket
administration.

Prefer short-lived cloud credentials where your hosting setup supports them. Fly.io does not
automatically provide AWS credentials; configure an explicit supported identity mechanism or
use a dedicated least-privilege key stored as a Fly secret:

```bash
flyctl secrets set S3_ACCESS_KEY_ID=... S3_SECRET_ACCESS_KEY=... --app collably-api
```

Set both access-key values or neither; with both omitted, boto3 uses its default credential
chain, which must be configured for the deployed runtime. The app intentionally refuses to
start in production if S3 bucket or region configuration is missing.

## Step 5: Set CORS Origins (After Vercel Deploy)

After deploying the frontend to Vercel (see [deploy-vercel.md](./deploy-vercel.md)), update the CORS origins:

```bash
flyctl secrets set CORS_ORIGINS=https://collably.vercel.app --app collably-api
```

Replace `collably.vercel.app` with your actual Vercel domain. For multiple domains, use comma-separated values (no spaces):

```bash
flyctl secrets set CORS_ORIGINS=https://collably.vercel.app,https://www.collably.in --app collably-api
```

## Step 6: Deploy the Backend

From the repository root:

```bash
flyctl deploy --config backend/fly.toml
```

Fly.io will:
1. Build the Docker image from `backend/Dockerfile`
2. Push it to Fly's registry
3. Launch a VM with 1 shared CPU and 256MB RAM in the `bom` region
4. Start the uvicorn server on port 8000 using the configured private S3 bucket

The first deploy takes ~2-3 minutes.

## Step 7: Run Database Migrations

Once the app is deployed, run Alembic migrations:

```bash
flyctl ssh console --app collably-api -C "cd /app && alembic upgrade head"
```

This connects to the running VM and executes `alembic upgrade head`.

## Step 8: Start the Email Worker

The app and email worker are separate Fly process groups. Scale the API and one
worker machine:

```bash
flyctl scale count app=1 email_worker=1 --app collably-api
```

The worker claims email outbox rows, sends them through the configured SMTP
provider, and retries transient failures. Monitor worker logs for
`email_delivery_failed` and `email_delivery_succeeded` events:

```bash
flyctl logs --app collably-api
```

Delivery is at-least-once: if a worker crashes after the SMTP server accepts a
message but before the database records success, the message can be sent again.

## Step 9: Verify the Deployment

Check the health endpoint:

```bash
curl https://collably-api.fly.dev/api/v1/health/ready
```

Expected response:

```json
{"status":"ready","db":"connected"}
```

If you get `{"status":"not_ready","db":"unreachable"}`, check the database connection:

```bash
flyctl logs --app collably-api
```

## Step 10: Note the Backend URL for Vercel

Your backend is now live at:

```
https://collably-api.fly.dev
```

Use this URL for the `NEXT_PUBLIC_API_BASE_URL` environment variable in Vercel:

```
NEXT_PUBLIC_API_BASE_URL=https://collably-api.fly.dev/api/v1
```

See [deploy-vercel.md](./deploy-vercel.md) for frontend deployment.

## Optional: Create an Admin User

After deploying and setting up Clerk, sign in to the frontend once to create your user record via the Clerk webhook. Then promote yourself to admin:

```bash
flyctl ssh console --app collably-api -C "python -m app.cli grant_admin your@email.com"
```

## Troubleshooting

### Check S3 Configuration

The backend requires `S3_BUCKET` and `S3_REGION` in production. Confirm they are set as
Fly secrets and check application startup logs if the machine fails health checks. Do not
make the bucket public to resolve access errors; fix the app's least-privilege permissions.

### View Logs

```bash
flyctl logs --app collably-api
```

### SSH into the VM

```bash
flyctl ssh console --app collably-api
```

From inside the VM:
- Check environment variables: `env | grep DATABASE_URL`
- Test database: `python -c "from app.db.session import get_engine; import asyncio; asyncio.run(get_engine().connect().__aenter__())"`

### Scale the VM

If the free tier is too small, scale up:

```bash
flyctl scale memory 512 --app collably-api
flyctl scale vm shared-cpu-1x --app collably-api
```

Or upgrade to a dedicated CPU:

```bash
flyctl scale vm dedicated-cpu-1x --app collably-api
```

### Reset Database Migrations

If migrations fail or are out of sync:

```bash
flyctl ssh console --app collably-api -C "cd /app && alembic downgrade base && alembic upgrade head"
```

**Warning:** `downgrade base` drops all tables. Only use in dev/staging.

## Cost Estimate

- **App VM:** Free tier includes 3 shared-cpu-1x VMs with 256MB RAM. If you exceed the free tier, expect ~$2/month for a single shared-cpu-1x VM with 256MB RAM.
- **Postgres:** Free tier includes 1 shared-cpu-1x Postgres with 256MB RAM and 1GB storage. Paid plans start at ~$2/month for 512MB RAM.
- **Object storage:** billed by the chosen S3 provider for storage, requests, and transfer.
- **Bandwidth:** First 100GB/month free; $0.02/GB thereafter.

Total estimated cost for MVP: **$0-5/month** depending on traffic.

## Next Steps

- [Deploy the frontend to Vercel](./deploy-vercel.md)
- [Complete the production checklist](./production-checklist.md)
- Configure Clerk webhook endpoint: `https://collably-api.fly.dev/api/v1/clerk/webhook`
