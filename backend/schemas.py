from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoResult(BaseModel):
    video_id: str
    title: str
    duration_sec: float
    dimensions: str
    tags: list[str] = Field(default_factory=list)
    description: str
    url: str
    hike_names: list[str] = Field(default_factory=list)


class TrailSummary(BaseModel):
    place_id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    website_uri: str | None = None


class Review(BaseModel):
    author: str = "Anonymous"
    rating: float | None = None
    relative_time: str | None = None
    text: str = ""


class PlaceDetails(TrailSummary):
    opening_hours: list[str] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)


class TrailMetrics(BaseModel):
    name: str
    area_name: str | None = None
    city: str | None = None
    state: str | None = None
    length_miles: float | None = None
    length_km: float | None = None
    elevation_gain_feet: float | None = None
    elevation_gain_meters: float | None = None
    difficulty: str | None = None
    route_type: str | None = None
    available: bool = True


class SavedTrail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    place_id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    metrics: TrailMetrics | None = None
    video_id: str | None = None


class SaveToggleRequest(SavedTrail):
    saved: bool = True


class SaveToggleResponse(BaseModel):
    saved: bool
    trail: SavedTrail
