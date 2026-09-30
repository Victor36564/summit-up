import re

from apify_client import ApifyClient

from cache import cache
from config import Settings
from schemas import TrailMetrics

ACTOR_ID = "crawlerbros/alltrails-scraper"


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_metrics(settings: Settings, name: str, country: str | None = None) -> TrailMetrics:
    country = country or settings.default_country
    key = f"alltrails:{country}:{name.strip().lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    if not settings.all_trails_api_key:
        return TrailMetrics(name=name, available=False)

    client = ApifyClient(settings.all_trails_api_key)
    run = client.actor(ACTOR_ID).call(
        run_input={
            "mode": "searchTrails",
            "query": name,
            "country": country,
            "fetchTrailDetails": True,
        }
    )
    dataset_id = getattr(run, "default_dataset_id", None)
    if dataset_id is None and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
    if not dataset_id:
        raise RuntimeError("AllTrails actor did not return a dataset ID")
    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        return cache.set(key, TrailMetrics(name=name, available=False), settings.metrics_cache_ttl_seconds)
    trail = items[0]
    metrics = TrailMetrics(
        name=_text(trail.get("name")) or name,
        area_name=_text(trail.get("areaName")),
        city=_text(trail.get("city")),
        state=_text(trail.get("state")),
        length_miles=_number(trail.get("lengthMiles")),
        length_km=_number(trail.get("lengthKm")),
        elevation_gain_feet=_number(trail.get("elevationGainFeet")),
        elevation_gain_meters=_number(trail.get("elevationGainMeters")),
        difficulty=_text(trail.get("difficulty")),
        route_type=_text(trail.get("routeType")),
    )
    return cache.set(key, metrics, settings.metrics_cache_ttl_seconds)
