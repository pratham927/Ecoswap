# EcoSwap React experience

The React frontend lives in `frontend/`. `api/app.py` exposes the existing Python engine over HTTP; `ecoswap/engine.py` and the original Streamlit entrypoint are unchanged. No database, API keys, or paid model service are required.

## Local development

Requires Python 3.12 and Node 22.12 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-api.txt
python -m api.app
```

In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite. Its `/api` proxy forwards requests to port 8000. Keep `VITE_API_BASE_URL` unset locally. The Home and How It Works pages render without the API. Swap Studio and Research need the API; they display loading, timeout, and retry states rather than fabricated results.

## Free deployment: Render API and Cloudflare Pages

1. In Render, create a Blueprint from `pratham927/Ecoswap`, branch `redesign/react-experience`, using the root `render.yaml`. It explicitly requests the Free service plan. If using a manual Web Service, use `pip install -r requirements-api.txt` for build and `gunicorn api.app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` for start. Select Python 3.12.
2. Render will request `ALLOWED_ORIGINS`. Set it to your exact frontend origin (for example, your assigned `https://YOUR-SITE.pages.dev`). If that address has not been assigned yet, leave this value empty initially and set it after step 3. Do not use `*`. Multiple exact origins can be comma-separated. The health check does not need CORS.
3. In Cloudflare Pages, import the same repository and branch. Root directory: `frontend`. Build command: `npm run build`. Output directory: `dist`. Set `NODE_VERSION=22` and `VITE_API_BASE_URL` to the actual Render HTTPS URL, without a trailing `/api`. Cloudflare installs npm dependencies automatically.
4. Set Render's `ALLOWED_ORIGINS` to the assigned Cloudflare origin and redeploy the API. If you change the API URL, rebuild the frontend because Vite embeds this setting at build time.
5. Verify the homepage photos, all four page URLs, browser back/forward, and the mobile menu. In Swap Studio, run the first recipe, compare alternatives, change the cap to 0%, and import the downloaded example JSON. Visit Research and download the pilot materials. Check the API `/api/health` endpoint returns JSON.

The supplied `_redirects` file supports direct links to `/studio`, `/how-it-works`, and `/research`. The homepage slideshow has pause/manual controls and respects reduced-motion preferences. Drafts and results persist in memory between page visits; a hard reload clears them. Imported recipes are processed in memory and are not saved to a database.

The API sleeps after 15 idle minutes on Render's free tier and may take about a minute to wake. Monthly compute, bandwidth and build limits apply. The static homepage does not depend on API availability. Review the provider's current limits when creating the services. This configuration does not create accounts, deploy services, or incur paid charges by itself.

After the redesign is merged, change each provider's production branch and `render.yaml` to `main`. The existing Streamlit deployment continues to use its unchanged `app.py`.

## Checks

```sh
python -m pytest -q
cd frontend
npm test
npm run build
```

The GitHub Actions workflow runs engine/API regression tests, frontend state-helper tests, and a production build including photo downloads. A successful build is not a substitute for visual browser checks.

## API

- `GET /api/health`: health and ingredient count.
- `GET /api/catalogue`: recipe scenarios, ingredient names, food states and roles.
- `POST /api/options`: recipe, source, alpha, max_fraction and exclude; returns ranked replacements, adapted recipes, carbon estimates and evidence.
- `GET /api/research`: evaluation, mappings, source manifest and fitted weights.
- `GET /api/download/<name>`: allowlisted research downloads.

Uploads are limited to 256 KB and 100 ingredients. Input errors return JSON. CORS is limited to configured origins. Carbon calculations always use the existing engine. The frontend only displays and compares returned estimates.
