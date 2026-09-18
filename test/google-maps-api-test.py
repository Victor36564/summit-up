import os
import requests
from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

PLACES_NEW_URL = "https://places.googleapis.com/v1/places:searchText"


def search_hikes_in_auckland() -> list[dict[str, str | None]]:
    """Return hikes found by Google Places API (New) Text Search."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set in summit-up/.env")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # FieldMask is required by Places API (New) to control returned data and billing
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id",
    }

    payload = {
        "textQuery": "hikes in Auckland, New Zealand"
    }

    response = requests.post(PLACES_NEW_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    return [
        {
            "name": place.get("displayName", {}).get("text", "Unnamed hike"),
            "address": place.get("formattedAddress"),
            "place_id": place.get("id"),
        }
        for place in data.get("places", [])
    ]

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def get_place_details_with_reviews(place_id: str) -> dict:
    url = f"https://places.googleapis.com/v1/places/{place_id}"

    # Request the specific fields you need
    field_mask = [
        "displayName",
        "rating",
        "userRatingCount",
        "formattedAddress",
        "websiteUri",
        "regularOpeningHours",
        "reviews",  # Returns up to 5 relevant reviews
    ]

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": ",".join(field_mask),
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()



if __name__ == "__main__":
    hikes = search_hikes_in_auckland()
    if not hikes:
        print("No hikes found in Auckland.")
    else:
        for index, hike in enumerate(hikes, start=1):
            print(f"{index}. {hike['name']}")
            print(f"   Address: {hike['address'] or 'Not available'}")
            print(f"   Place ID: {hike['place_id'] or 'Not available'}")

        # Example place_id (you can get this from your Auckland hike search)
    place_id = hikes[0]["place_id"]  # Replace with a valid place_id from the search results

    data = get_place_details_with_reviews(place_id)

    name = data.get("displayName", {}).get("text", "Unknown")
    rating = data.get("rating", "N/A")
    total_reviews = data.get("userRatingCount", 0)

    print(f"Place: {name}")
    print(f"Rating: {rating} ★ ({total_reviews} total ratings)\n")
    print("--- Top Reviews ---")

    for i, review in enumerate(data.get("reviews", []), start=1):
        author = review.get("authorAttribution", {}).get("displayName", "Anonymous")
        review_rating = review.get("rating")
        review_text = review.get("text", {}).get("text", "No text provided")
        time_desc = review.get("relativePublishTimeDescription", "")

        print(f"\n{i}. {author} ({review_rating}★) - {time_desc}")
        print(f'   "{review_text[:150]}..."')