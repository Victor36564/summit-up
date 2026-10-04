# Summit Up

Summit Up is a New Zealand-first hiking exploration app with a Shorts-style trail feed, an interactive map, and an anonymous saved-trail vault.

## Stack

- FastAPI, Pydantic v2, SQLAlchemy, and Uvicorn backend
- React, Vite, TypeScript, Tailwind CSS, and Lucide frontend
- Google Places API (New) for trail identity and reviews
- YouTube Data API v3 for portrait hiking Shorts
- Apify AllTrails scraper for trail metrics
- SQLite persistence keyed by an anonymous browser session

## Local setup

1. Copy `.env.example` to `.env` and fill in the provider keys. Keep the server keys private. Restrict `VITE_GOOGLE_MAPS_API_KEY` to your development/deployment origins and the Maps JavaScript API.
2. Install backend dependencies and start FastAPI:

```powershell
cd summit-up
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

3. In another terminal, install and start the frontend:

```powershell
cd summit-up\frontend
npm install
npm run dev
```

The Vite development server expects the API at the same origin in production. For local development, use a reverse proxy or start the frontend with a proxy configuration pointing `/api` to `http://localhost:8000`.

## API

- `GET /api/health`
- `GET /api/feed/shorts?query=...&limit=10`
- `GET /api/trails/search?query=...`
- `GET /api/trails/details/{place_id}`
- `GET /api/trails/metrics?name=...`
- `GET /api/recommendations/options`
- `POST /api/recommendations`
- `GET /api/saved`
- `POST /api/saved`

Saved requests use the `X-Session-ID` header. The frontend creates one anonymous UUID and stores it in local storage; no account system is included in this MVP.

Provider calls are cached in memory. AllTrails calls use a longer cache TTL because the Apify actor can take several seconds. Missing credentials produce a useful provider error or unavailable metrics state instead of silently fabricating data.

Recommendations use the supplied saved models and catalog with the TF-IDF backend. They do not require Google, YouTube, or Apify credentials. Results are explicitly experimental seasonal recommendations based on selectively reported reviewer conditions, not validated probabilities or safety guarantees.

Example request body for `POST /api/recommendations`:

```json
{
	"travel_date": "2027-01-15",
	"region": "Otago",
	"max_distance_km": 10,
	"max_elevation_gain_m": 700,
	"preferences_text": "mountain views and a peaceful lake walk",
	"desired_features": ["views", "lake"],
	"condition_weights": {"overall_good": 1.0, "bugs": 0.8, "mud": 0.5},
	"allow_experimental": true,
	"top_k": 10
}
```

The ML artifacts require `scikit-learn==1.8.0`; install `backend\requirements.txt` before starting FastAPI. The recommender loads once during startup. If its assets or dependencies are unavailable, provider-only routes remain available and recommendation requests return `503`.

## Docker / Hugging Face Spaces

Build and run the unified image from the repository root:

```powershell
docker build -t summit-up .
docker run --env-file .env -p 7860:7860 summit-up
```

The image builds the Vite app, copies it into the Python runtime, runs as UID 1000, and serves both the SPA and `/api/*` on port `7860`.

## Testing

The scripts under `test/` are provider experiments and references for the production services under `backend/services/`. Unit and mocked API tests should run without credentials. Live provider smoke tests should be opt-in because Google, YouTube, and Apify usage may incur quota or scraping costs.