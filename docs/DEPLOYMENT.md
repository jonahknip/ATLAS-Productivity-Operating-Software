# ATLAS Deployment Guide

Deploy the ATLAS MVP with:
- **API**: Railway (FastAPI + PostgreSQL)
- **UI**: Vercel (React + Vite)

## Prerequisites

- GitHub account with the ATLAS repository
- [Railway](https://railway.app) account
- [Vercel](https://vercel.com) account
- A generated API token (any secure random string)

## Architecture Overview

```
┌─────────────────┐     HTTPS      ┌─────────────────┐
│   Vercel (UI)   │ ────────────── │  Railway (API)  │
│  React + Vite   │                │    FastAPI      │
└─────────────────┘                └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │    PostgreSQL   │
                                   │  (Railway Add-on)│
                                   └─────────────────┘
```

## Required Environment Variables

### API (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-set by Railway Postgres add-on) |
| `API_TOKEN` | Yes | Bearer token for `/v1/*` route authentication |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins (e.g., `https://your-app.vercel.app`) |
| `OPENAI_API_KEY` | No | OpenAI API key for cloud LLM provider |
| `OLLAMA_BASE_URL` | No | Ollama server URL (default: `http://localhost:11434`) |

### UI (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_ATLAS_API_URL` | Yes | Railway API URL (e.g., `https://your-api.up.railway.app`) |
| `VITE_ATLAS_API_TOKEN` | Yes | Same token as `API_TOKEN` on Railway |

---

## Step 1: Deploy API to Railway

### 1.1 Create Railway Project

```bash
# Install Railway CLI (optional, can use web UI)
npm install -g @railway/cli

# Login
railway login
```

Or use the web interface at [railway.app](https://railway.app).

### 1.2 Create Project from GitHub

1. Go to Railway Dashboard → **New Project**
2. Select **Deploy from GitHub repo**
3. Choose your ATLAS repository
4. Railway will auto-detect the Dockerfile in `apps/api/`

### 1.3 Configure Service

Set the **Root Directory** to `apps/api`:

```
Root Directory: apps/api
```

### 1.4 Add PostgreSQL Database

1. In your Railway project, click **+ New**
2. Select **Database** → **PostgreSQL**
3. Railway automatically sets `DATABASE_URL` in your service

### 1.5 Set Environment Variables

In Railway Dashboard → Your Service → **Variables**:

```bash
# Required
API_TOKEN=your-secure-random-token-here
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:5173

# Optional
OPENAI_API_KEY=sk-...
```

Generate a secure API token:
```bash
# macOS/Linux
openssl rand -base64 32

# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 1.6 Deploy

Railway will automatically deploy on push to main. Manual deploy:

```bash
# Using CLI
cd apps/api
railway up

# Or trigger in Dashboard → Deployments → Deploy
```

### 1.7 Verify API Deployment

```bash
# Get your Railway URL (e.g., https://atlas-api-production.up.railway.app)
RAILWAY_URL="https://your-api.up.railway.app"

# Health check (no auth required)
curl $RAILWAY_URL/health
# {"status":"healthy","version":"0.1.0"}

# Version info
curl $RAILWAY_URL/version
# {"version":"0.1.0","app_name":"ATLAS","database":"postgres"}

# Test authenticated endpoint
curl -H "Authorization: Bearer YOUR_API_TOKEN" $RAILWAY_URL/v1/receipts
# {"receipts":[],"total":0,"limit":50,"offset":0}
```

---

## Step 2: Deploy UI to Vercel

### 2.1 Import Project

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repository
3. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `apps/ui`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### 2.2 Set Environment Variables

In Vercel Dashboard → Your Project → **Settings** → **Environment Variables**:

```bash
VITE_ATLAS_API_URL=https://your-api.up.railway.app
VITE_ATLAS_API_TOKEN=your-secure-random-token-here
```

**Important**: Use the same token value as `API_TOKEN` on Railway.

### 2.3 Deploy

Vercel automatically deploys on push to main. Manual deploy:

```bash
# Using Vercel CLI
cd apps/ui
vercel --prod
```

### 2.4 Update CORS on Railway

After getting your Vercel URL, update Railway's `CORS_ORIGINS`:

```bash
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-git-main.vercel.app
```

---

## Step 3: Verify Full Deployment

### Test API from Browser Console

Open your Vercel app in browser, then in DevTools Console:

```javascript
// Should work with auth header added automatically
fetch('/v1/receipts').then(r => r.json()).then(console.log)
```

### Test Execute Endpoint

```bash
RAILWAY_URL="https://your-api.up.railway.app"
API_TOKEN="your-token"

curl -X POST "$RAILWAY_URL/v1/execute" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Create a task to review deployment"}'
```

---

## Troubleshooting

### API returns 401 Unauthorized

1. Check `API_TOKEN` is set on Railway
2. Check `VITE_ATLAS_API_TOKEN` matches on Vercel
3. Verify header format: `Authorization: Bearer <token>`

### CORS errors in browser

1. Check `CORS_ORIGINS` includes your Vercel domain
2. Include both `https://your-app.vercel.app` and preview URLs
3. Redeploy API after changing CORS settings

### Database connection fails

1. Verify PostgreSQL add-on is attached in Railway
2. Check `DATABASE_URL` is set (Railway does this automatically)
3. Check Railway logs: `railway logs`

### Build fails on Railway

1. Check Dockerfile path: should be `apps/api/Dockerfile`
2. Verify root directory is set to `apps/api`
3. Check build logs in Railway Dashboard

### UI not loading data

1. Check browser DevTools Network tab for failed requests
2. Verify `VITE_ATLAS_API_URL` is correct (no trailing slash)
3. Check browser console for CORS or auth errors

---

## Rollback

### Railway

1. Go to Railway Dashboard → Deployments
2. Find previous successful deployment
3. Click **Rollback**

### Vercel

1. Go to Vercel Dashboard → Deployments
2. Find previous deployment
3. Click **...** → **Promote to Production**

---

## Local Development

### API

```bash
cd apps/api

# Install dependencies
pip install -e ".[dev]"

# Create .env file
cp .env.example .env

# Run locally (uses SQLite)
uvicorn atlas.main:app --reload --port 8000
```

### UI

```bash
cd apps/ui

# Install dependencies
npm install

# Create .env file (optional for local dev with proxy)
cp .env.example .env.local

# Run locally (proxies to localhost:8000)
npm run dev
```

---

## Security Notes

1. **API Token**: Use a strong, randomly generated token (32+ characters)
2. **HTTPS Only**: Railway and Vercel both enforce HTTPS
3. **No Token in Logs**: Auth failures log the path, not the token
4. **Environment Variables**: Never commit tokens to git

---

## Cost Estimate (MVP)

| Service | Plan | Est. Cost |
|---------|------|-----------|
| Railway | Hobby | ~$5/month |
| Railway Postgres | Hobby | ~$5/month |
| Vercel | Hobby | Free |
| **Total** | | **~$10/month** |

For production scale, consider Railway Pro ($20/month) and Vercel Pro ($20/month).
