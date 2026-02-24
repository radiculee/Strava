# Strava Streamlit Dashboard (Streamlit Cloud First)

This is the easiest deployment path for your LinkedIn showcase.

## 1. Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py --force
streamlit run dashboard/app.py
```

Open:
- `http://localhost:8501`

## 2. Streamlit Cloud Deployment

1. Push repo to GitHub.
2. Go to Streamlit Community Cloud.
3. Click **New app**.
4. Select:
- Repository: your GitHub repo
- Branch: `main`
- Main file path: `dashboard/app.py`
5. Deploy.

## 3. App Configuration

Use these settings in `.env` (local) or Streamlit secrets (cloud):

```toml
SHOWCASE_MODE = "true"
REQUIRE_GATEWAY_AUTH = "false"
DASHBOARD_DATA_MODE = "demo"
```

Notes:
- `SHOWCASE_MODE=true` keeps data less sensitive by reducing time/metric precision.
- `REQUIRE_GATEWAY_AUTH=false` keeps deployment simple (no Cloudflare dependency).
- `DASHBOARD_DATA_MODE=demo` forces demo-only rides for public cloud deployment.
- Supabase logging is optional and disabled unless credentials are provided.

## 4. Data Modes

- `demo`: always uses generated showcase rides (recommended for public cloud)
- `personal`: only reads local `data/cycling_summary.csv`
- `auto`: uses CSV if present, otherwise demo

## 5. Data Update Model

- Pipeline remains daily-only.
- Run `run_pipeline.bat` once per day (Task Scheduler).
- Dashboard reflects latest `data/cycling_summary.csv` output.

## 5. Share on LinkedIn

- Share your Streamlit app URL.
- Prefer sanitized showcase mode for public sharing.
- Keep private/full-fidelity mode for personal/local use.

## 6. Optional (Later)

You can re-enable advanced access control and logging later (Cloudflare + Supabase), but it is not required for Streamlit deployment.
