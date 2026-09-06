# TarkaRaksha — Complete Step-by-Step Render Deployment Guide

> **Target Audience**: Anyone deploying TarkaRaksha for the first time with **zero prior deployment experience**.
> **Stack**: FastAPI (Python 3.12) Backend + Next.js 15 (Node.js) Frontend.
> **No Docker required**. All hosting is native, fully managed, and free tier compatible.

---

## Overview of What You Are Setting Up

You will deploy two connected services:
1. **Backend Service** (`tarkaraksha-backend`): The FastAPI deterministic integrity control plane running on Render.
2. **Frontend Service** (`tarkaraksha-frontend`): The Next.js 15 web application. You can deploy it either directly on **Render** (all-in-one place) or on **Vercel** (the native home of Next.js). Both methods are explained step-by-step below.

---

# SECTION 1: Deploying the Backend on Render (Click-by-Click)

### Step 1: Open Render Dashboard
1. Go to [https://dashboard.render.com](https://dashboard.render.com).
2. Sign in with your **GitHub** account (this allows Render to access your repository).

---

### Step 2: Create a New Web Service
1. On your Render dashboard, look at the top right and click the blue **`+ New`** button.
2. From the dropdown menu, click **`Web Service`**.

---

### Step 3: Connect Your GitHub Repository
1. You will see a screen titled **"Connect a repository"**.
2. Select **`Git Provider: GitHub`**.
3. In the search box, search for your repository name: **`TarkaRaksha`** (or `ankit-choubey/TarkaRaksha`).
4. Click the blue **`Connect`** button next to your repository.

---

### Step 4: Fill in the Configuration Fields Exactly as Follows

When the configuration form opens, fill in every field matching these exact values:

| Field on Screen | What to Type / Select Exactly | Why This Is Needed |
| :--- | :--- | :--- |
| **Name** | `tarkaraksha-backend` | Gives your backend a recognizable name and generates its public URL (e.g., `https://tarkaraksha-backend.onrender.com`). |
| **Region** | Select the closest region (e.g., **`Singapore (Southeast Asia)`** or **`Frankfurt (Europe)`**) | Choose the region closest to you for lowest latency. |
| **Branch** | `main` | Deploys your primary production branch. |
| **Root Directory** | Leave **BLANK** (empty) | Your Python backend files and `requirements.txt` reside in the repository root. |
| **Runtime** | Select **`Python 3`** | Native Python environment (no Docker needed). |
| **Build Command** | `pip install -r requirements.txt` | Automatically installs FastAPI, Uvicorn, Pydantic, HTTPX, Razorpay, and Groq SDKs. |
| **Start Command** | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` | Starts the production ASGI web server binding to Render's allocated port. |
| **Instance Type** | Select **`Free`** ($0/month) | Ideal for demonstrations, evaluations, and testing. |

---

### Step 5: Add Environment Variables (Under "Advanced")
1. Scroll down the form and click to expand **`Advanced`**.
2. Click the **`Add Environment Variable`** button for each variable below:

| Key (Variable Name) | Value to Enter | Note |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.2` | Locks Render to Python 3.12 runtime. |
| `RAZORPAY_KEY_ID` | Your Razorpay Key ID (e.g. `rzp_test_...`) | Optional for synthetic runs; required for live test mode. |
| `RAZORPAY_KEY_SECRET` | Your Razorpay Key Secret | Optional for synthetic runs; required for live test mode. |
| `GROQ_API_KEY` | Your Groq API Key (e.g. `gsk_...`) | Optional; if not set, deterministic fallback explanations are used automatically. |

3. In the **Health Check Path** field under Advanced, type:
   ```text
   /health
   ```
   *(Render will ping this URL to confirm your service is 100% healthy before routing traffic to it).*

---

### Step 6: Click "Create Web Service"
1. Scroll to the very bottom of the page.
2. Click the large blue **`Deploy Web Service`** (or **`Create Web Service`**) button.
3. **Wait 2–3 minutes**. You will see the live terminal logs:
   - `==> Installing dependencies with pip install -r requirements.txt...`
   - `==> Uploading build...`
   - `==> Starting service with 'uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT'...`
   - `Application startup complete.`
   - `==> Your service is live 🎉`
4. Look near the top of the page under the service name. You will see your live Backend URL, for example:
   ```text
   https://tarkaraksha-backend.onrender.com
   ```
5. **COPY THIS URL!** You will need it to connect the Frontend in Section 2.

---

# SECTION 2: Deploying the Frontend

You have two simple options. Choose whichever you prefer:

---

## OPTION A: Deploy Frontend on Render (All in One Place on Render)

### Step 1: Create a Second Web Service on Render
1. From the Render dashboard header, click **`+ New`** → **`Web Service`**.
2. Select the same repository: **`TarkaRaksha`** and click **`Connect`**.

### Step 2: Fill in the Frontend Form Fields Exactly:

| Field on Screen | What to Type / Select Exactly | Note |
| :--- | :--- | :--- |
| **Name** | `tarkaraksha-frontend` | Your frontend app name. |
| **Region** | Select the **same region** you selected for the backend | Keeps latency minimal. |
| **Branch** | `main` | Production branch. |
| **Root Directory** | `frontend` | **CRITICAL**: Type `frontend` because the Next.js app lives in the `frontend/` folder. |
| **Runtime** | Select **`Node`** | Native Node.js environment. |
| **Build Command** | `npm install && npm run build` | Builds the production Next.js application. |
| **Start Command** | `npm run start` | Starts Next.js on port 3000. |
| **Instance Type** | Select **`Free`** ($0/month) | Free tier. |

### Step 3: Add the Backend Connection Environment Variable
1. Scroll down, expand **`Advanced`**.
2. Click **`Add Environment Variable`**:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: Paste your backend URL from Section 1 (e.g. `https://tarkaraksha-backend.onrender.com` without trailing slash).
3. Click **`Add Environment Variable`** again:
   - **Key**: `NODE_VERSION`
   - **Value**: `20.11.0`

### Step 4: Click Deploy
1. Click **`Create Web Service`**.
2. After 2–3 minutes, your frontend is live with a public URL (e.g., `https://tarkaraksha-frontend.onrender.com`).

---

## OPTION B: Deploy Frontend on Vercel (Fastest & Native for Next.js)

If you prefer Vercel for the frontend:
1. Go to [https://vercel.com](https://vercel.com) and sign in with GitHub.
2. Click **`Add New...`** → **`Project`**.
3. Import your **`TarkaRaksha`** repository.
4. On the configuration screen:
   - **Root Directory**: Click "Edit" and select **`frontend`**.
   - **Framework Preset**: Auto-detected as **Next.js**.
   - **Environment Variables**:
     - Key: `NEXT_PUBLIC_API_URL`
     - Value: Paste your Render backend URL (e.g. `https://tarkaraksha-backend.onrender.com`).
5. Click **`Deploy`**.
6. In ~60 seconds, your site is live with a custom `.vercel.app` URL and global edge caching!

---

# SECTION 3: How to Verify Everything Works (Smoke Test)

Once both services are deployed:

1. **Verify Backend Health**:
   Open a browser tab to:
   ```text
   https://YOUR-BACKEND-URL.onrender.com/health
   ```
   You should see:
   ```json
   {"status": "ok", "service": "tarkaraksha-control-plane", "timestamp": "..."}
   ```

2. **Verify Interactive API Documentation**:
   Open:
   ```text
   https://YOUR-BACKEND-URL.onrender.com/docs
   ```
   You should see the complete Swagger UI documentation for all endpoints (`/api/v1/hero-transaction/run`, `/api/v1/control-room/live`, etc.).

3. **Verify Frontend**:
   Open your Frontend URL (`https://YOUR-FRONTEND-URL.onrender.com` or `https://YOUR-APP.vercel.app`).
   - The landing page will load with all rich animations and statistics.
   - Click **"Launch Simulation"** or **"Enter Control Room"**.
   - Select a hardware item and pick any scenario (e.g., *Clean Purchase*, *Unbudgeted Price Surge*, *Refurbished SKU Substitution*, or *AI Quality vs Budget Tradeoff*).
   - Place the order: watch the dot+line verification flow progress, intercept discrepancies in real-time, generate MRDP proofs, and seal the Transaction Passport!

---

# Alternative: 1-Click "Blueprint" Deployment (Even Easier!)

Render also supports reading our newly added [`render.yaml`](file:///Users/theankit/Documents/AK/Projects/TarkaRaksha/render.yaml) file to automatically configure **BOTH** services in 1 single click:

1. Go to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **`+ New`** → **`Blueprint`**.
3. Connect your **`TarkaRaksha`** repository.
4. Render will automatically read `render.yaml` and display both `tarkaraksha-backend` and `tarkaraksha-frontend` pre-filled with the exact commands, ports, and environment links!
5. Click **`Apply`**. Both services deploy simultaneously!
