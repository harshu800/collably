# Deploy Collably Frontend to Vercel

This guide walks through deploying the Collably Next.js frontend to [Vercel](https://vercel.com), which provides zero-config hosting for Next.js applications with automatic HTTPS, CDN, and deployment previews.

## Prerequisites

- A [Vercel](https://vercel.com) account (free tier available)
- [Vercel CLI](https://vercel.com/docs/cli) installed (optional but recommended)
- A deployed backend on Fly.io (see [deploy-flyio.md](./deploy-flyio.md))
- Clerk application configured with production keys

## Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

Verify installation:

```bash
vercel --version
```

## Step 2: Authenticate with Vercel

```bash
vercel login
```

This opens a browser window to log in or create an account.

## Step 3: Deploy the Frontend (First Time)

From the `frontend/` directory:

```bash
cd frontend
vercel
```

The CLI will prompt:
- **Set up and deploy "~/frontend"?** → Yes
- **Which scope?** → Select your account or team
- **Link to existing project?** → No (first deploy)
- **What's your project's name?** → `collably` (or your preferred name)
- **In which directory is your code located?** → `./` (press Enter)
- **Want to override the settings?** → No (Vercel auto-detects Next.js)

Vercel will:
1. Build the Next.js app (this first deploy uses default env vars)
2. Deploy to a preview URL (e.g., `collably-abc123.vercel.app`)
3. Create a project in your Vercel dashboard

**Note:** The first deployment will not work end-to-end because environment variables are not set yet. Continue to Step 4.

## Step 4: Set Environment Variables in Vercel Dashboard

Go to your [Vercel dashboard](https://vercel.com/dashboard), select the `collably` project, then go to **Settings → Environment Variables**.

Add the following variables for **Production** environment:

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://collably-api.fly.dev/api/v1` | Your Fly.io backend URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `your_clerk_publishable_key` | From Clerk dashboard → API Keys |
| `CLERK_SECRET_KEY` | `your_clerk_secret_key` | From Clerk dashboard → API Keys (keep secret!) |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` | Clerk sign-in page route |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` | Clerk sign-up page route |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/onboarding` | Where to redirect after sign-in |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/onboarding` | Where to redirect after sign-up |

**Important:** Variables prefixed with `NEXT_PUBLIC_` are baked into the build at build time and exposed to the browser. If you change these values, you must redeploy.

Save all variables, then continue to Step 5.

## Step 5: Deploy to Production

From the `frontend/` directory:

```bash
vercel --prod
```

This triggers a production build with the environment variables from Step 4. Vercel will assign a production domain like `collably.vercel.app`.

## Step 6: Note Your Vercel Domain

Your frontend is now live at:

```
https://collably.vercel.app
```

(or your custom domain if you've configured one)

## Step 7: Update Backend CORS

Go back to your Fly.io backend and update `CORS_ORIGINS` to include your Vercel domain:

```bash
flyctl secrets set CORS_ORIGINS=https://collably.vercel.app --app collably-api
```

If you have multiple domains (e.g., a custom domain), use comma-separated values:

```bash
flyctl secrets set CORS_ORIGINS=https://collably.vercel.app,https://www.collably.in --app collably-api
```

## Step 8: Update Clerk Allowed Origins

In your [Clerk dashboard](https://dashboard.clerk.com), go to **Settings → Paths**, then add your Vercel domain to the **Allowed origins** list:

- `https://collably.vercel.app`

Also configure the **Webhook endpoint** in Clerk:

- **Endpoint URL:** `https://collably-api.fly.dev/api/v1/clerk/webhook`
- **Subscribe to events:** `user.created`, `user.updated`, `user.deleted`
- Copy the **Signing Secret** and ensure it matches the `CLERK_WEBHOOK_SECRET` you set in Fly.io (Step 4 of the Fly.io guide)

## Step 9: Verify End-to-End

Visit your Vercel domain:

```
https://collably.vercel.app
```

- The landing page should load
- Click "Sign In" and authenticate via Clerk
- After sign-in, you should be redirected to `/onboarding`
- The frontend should successfully call the backend API (check Network tab in DevTools)

If you see CORS errors, double-check Step 7.

## Optional: Add a Custom Domain

In the Vercel dashboard, go to **Settings → Domains** and add your custom domain (e.g., `collably.in`, `www.collably.in`).

Vercel will provide DNS records to add to your domain registrar. Once DNS propagates, Vercel automatically provisions an SSL certificate.

After adding a custom domain:
1. Update `CORS_ORIGINS` in Fly.io to include the new domain
2. Update Clerk's allowed origins

## Deploying Updates

Whenever you push changes to the `frontend/` directory:

1. **Automatic deploys (recommended):** Connect your GitHub repo to Vercel. Vercel will auto-deploy on push to `main`.
2. **Manual deploys:** Run `vercel --prod` from `frontend/`.

## Rollback a Deployment

If a deploy breaks production, roll back in the Vercel dashboard:

1. Go to **Deployments**
2. Find the last working deployment
3. Click **⋯ → Promote to Production**

## Important Notes on `NEXT_PUBLIC_*` Variables

- `NEXT_PUBLIC_*` variables are **baked into the JavaScript bundle at build time**
- They are **visible to the browser** (do not put secrets here)
- If you change a `NEXT_PUBLIC_*` variable in the Vercel dashboard, you must **redeploy** for the change to take effect
- Runtime-only variables (like `CLERK_SECRET_KEY`) can be changed without redeploying

## Troubleshooting

### Build fails: "Module not found"

Check that all dependencies are in `package.json` and committed to git.

### Environment variables not working

- Verify variables are set for the **Production** environment in Vercel dashboard
- `NEXT_PUBLIC_*` variables require a redeploy to take effect
- Check build logs: Vercel → Deployments → [latest] → Logs

### CORS errors

- Verify `CORS_ORIGINS` in Fly.io includes your Vercel domain (no trailing slash)
- Check that the Vercel domain matches exactly (e.g., `https://` vs `http://`, `www.` prefix)

### Clerk authentication fails

- Verify `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` in Vercel dashboard
- Check Clerk dashboard → Settings → Paths → Allowed origins includes your Vercel domain
- Check Clerk webhook is pointing at `https://collably-api.fly.dev/api/v1/clerk/webhook`

### API calls fail (network errors)

- Verify `NEXT_PUBLIC_API_BASE_URL=https://collably-api.fly.dev/api/v1` in Vercel dashboard
- Check that the backend is running: `curl https://collably-api.fly.dev/api/v1/health`

## Cost Estimate

- **Vercel Free Tier:** Includes 100GB bandwidth/month, unlimited deployments, automatic HTTPS, and 1 concurrent build. Sufficient for MVP.
- **Vercel Pro:** $20/month if you exceed free tier limits or need team collaboration.

## Next Steps

- [Complete the production checklist](./production-checklist.md)
- Configure uptime monitoring (e.g., UptimeRobot, Pingdom)
- Set up error tracking (e.g., Sentry)
