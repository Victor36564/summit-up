from datetime import date
from typing import Any, Literal
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    place_id: str | None = None
    catalog_hike_id: str | None = None
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    metrics: TrailMetrics | None = None
    video_id: str | None = None

    @model_validator(mode="after")
    def require_identity(self):
        if not self.place_id and not self.catalog_hike_id:
            raise ValueError("place_id or catalog_hike_id is required")
        return self


class SaveToggleRequest(SavedTrail):
    saved: bool = True


class SaveToggleResponse(BaseModel):
    saved: bool
    trail: SavedTrail


FEATURE_TAGS = {"forest", "mountain_alpine", "lake", "waterfall", "coastal", "river", "glacier", "views"}
CONDITION_TARGETS = {"overall_good", "bugs", "mud", "snow", "ice", "scenic_positive", "crowded", "trail_quality_good"}


class RecommendationRequest(BaseModel):
    travel_date: date
    as_of: date = Field(default_factory=date.today)
    region: str | None = None
    difficulty: str | None = None
    max_distance_km: float | None = Field(default=None, ge=0)
    max_elevation_gain_m: float | None = Field(default=None, ge=0)
    max_time_hours: float | None = Field(default=None, ge=0)
    preferences_text: str = ""
    desired_features: list[str] = Field(default_factory=list)
    condition_weights: dict[str, float] = Field(default_factory=dict)
    allow_experimental: Literal[True] = True
    top_k: int = Field(default=10, ge=1, le=500)

    @field_validator("max_distance_km", "max_elevation_gain_m", "max_time_hours")
    @classmethod
    def finite_limit(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("limits must be finite and nonnegative")
        return value

    @field_validator("desired_features")
    @classmethod
    def supported_features(cls, value: list[str]) -> list[str]:
        unknown = set(value) - FEATURE_TAGS
        if unknown:
            raise ValueError(f"unsupported desired_features: {', '.join(sorted(unknown))}")
        return value

    @field_validator("condition_weights")
    @classmethod
    def supported_weights(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = set(value) - CONDITION_TARGETS
        if unknown:
            raise ValueError(f"unknown condition_weights targets: {', '.join(sorted(unknown))}")
        if any(not math.isfinite(weight) or weight < 0 for weight in value.values()):
            raise ValueError("condition weights must be finite and nonnegative")
        return value

    def to_recommender_request(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ConditionResult(BaseModel):
    model_score: float | None = None
    status: str
    used_in_ranking: bool


class RecommendationResult(BaseModel):
    hike_id: str
    name: str
    region: str
    distance_km: float | None = None
    elevation_gain_m: float | None = None
    estimated_time_hours: str | None = None
    difficulty: str | None = None
    ranking_score: float | None = None
    seasonal_suitability_score: float | None = None
    text_similarity: float | None = None
    conditions: dict[str, ConditionResult]
    unsupported_weighted_targets: list[str] = Field(default_factory=list)
    unknown_requested_features: list[str] = Field(default_factory=list)
    same_hike_month_observations: int | None = None
    climate_scope: str | None = None
    source_url: str | None = None
    reasons: list[str] = Field(default_factory=list)
    rank: int | None = None


class RecommendationResponse(BaseModel):
    status: Literal["experimental", "limited_evidence"]
    travel_date: date
    as_of: date
    text_backend: str
    candidates: int
    prediction_meaning: str
    ranking_validated: bool
    results: list[RecommendationResult]


class NoMatchResponse(BaseModel):
    status: Literal["no_matches"]
    results: list[Any] = Field(default_factory=list)
    request: dict[str, Any]
