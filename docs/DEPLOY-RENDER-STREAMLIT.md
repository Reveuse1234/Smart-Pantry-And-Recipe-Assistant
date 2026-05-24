# Deploy: Render (API) + Streamlit Cloud (UI)

## What each URL is for

| URL | What you see | Who uses it |
|-----|----------------|-------------|
| `https://….onrender.com` | JSON API (`/health`, `/docs`) | **Not** the main app screen |
| `https://….streamlit.app` | Smart Pantry UI | **Share this link** |

If only Render is deployed, opening the Render link in a browser is **not** the full app.

## Render (API)

1. **Build command:** `pip install -r requirements-render.txt` (not `requirements.txt`)
2. **Start command:** `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Environment:** `PYTHON_VERSION=3.11.9`, `PANTRY_SECRET=<secret>`
4. After Streamlit exists: `CORS_ORIGINS=https://your-app.streamlit.app`
5. Test: `https://YOUR-API.onrender.com/health` → `{"status":"ok"}`

## Streamlit Cloud (UI)

1. [share.streamlit.io](https://share.streamlit.io) → repo → `frontend/streamlit/Home.py`
2. Secrets:

```toml
BACKEND_URL = "https://YOUR-API.onrender.com"
PUBLIC_APP_URL = "https://YOUR-APP.streamlit.app"
PANTRY_SECRET = "same-as-render"
CORS_ORIGINS = "https://YOUR-APP.streamlit.app"
```

3. Open the `.streamlit.app` URL on phone/laptop.
