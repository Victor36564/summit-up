import requests

from cache import cache
from config import Settings
from schemas import PlaceDetails, Review, TrailSummary

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
SEARCH_FIELD_MASK = "places.displayName,places.formattedAddress,places.id,places.location"
DETAILS_FIELD_MASK = (
    "displayName,rating,userRatingCount,formattedAddress,websiteUri,"
    "regularOpeningHours,reviews,photos"
)


def _headers(settings: Settings, field_mask: str) -> dict[str, str]:
    if not settings.google_maps_api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not configured")
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": field_mask,
    }


def search_places(settings: Settings, query: str) -> list[TrailSummary]:
    key = f"places:search:{query.lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    response = requests.post(
        PLACES_SEARCH_URL,
        headers=_headers(settings, SEARCH_FIELD_MASK),
        json={"textQuery": query},
        timeout=30,
    )
    response.raise_for_status()
    results = []
    for place in response.json().get("places", []):
        display_name = place.get("displayName", {})
        location = place.get("location", {})
        results.append(
            TrailSummary(
                place_id=place.get("id", ""),
                name=display_name.get("text", "Unnamed hike"),
                address=place.get("formattedAddress"),
                latitude=location.get("latitude"),
                longitude=location.get("longitude"),
            )
        )
    return cache.set(key, results, settings.cache_ttl_seconds)


def get_place_details(settings: Settings, place_id: str) -> PlaceDetails:
    key = f"places:details:{place_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    response = requests.get(
        f"https://places.googleapis.com/v1/places/{place_id}",
        headers=_headers(settings, DETAILS_FIELD_MASK),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    display_name = data.get("displayName", {})
    location = data.get("location", {})
    hours = data.get("regularOpeningHours", {}).get("weekdayDescriptions", [])
    reviews = [
        Review(
            author=review.get("authorAttribution", {}).get("displayName", "Anonymous"),
            rating=review.get("rating"),
            relative_time=review.get("relativePublishTimeDescription"),
            text=review.get("text", {}).get("text", ""),
        )
        for review in data.get("reviews", [])
    ]
    photos = [photo.get("name", "") for photo in data.get("photos", []) if photo.get("name")]
    details = PlaceDetails(
        place_id=place_id,
        name=display_name.get("text", "Unnamed hike"),
        address=data.get("formattedAddress"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        rating=data.get("rating"),
        user_rating_count=data.get("userRatingCount"),
        website_uri=data.get("websiteUri"),
        opening_hours=hours,
        reviews=reviews,
        photos=photos,
    )
    return cache.set(key, details, settings.cache_ttl_seconds)
