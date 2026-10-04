import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import SavedCatalogRecord, SavedTrailRecord, catalog_record_to_dict, get_db, list_saved, record_to_dict
from models.model import catalog_options, recommend
from schemas import NoMatchResponse, RecommendationRequest, RecommendationResponse, SaveToggleRequest, SaveToggleResponse, SavedTrail
from services.alltrails import get_metrics
from services.google_places import get_place_details, search_places
from services.youtube import search_shorts

router = APIRouter(prefix="/api")


@router.post("/recommendations", response_model=RecommendationResponse | NoMatchResponse)
def recommendations(
    payload: RecommendationRequest,
    request: Request,
    x_session_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    session_id = session_id_dependency(x_session_id)
    recommender = getattr(request.app.state, "recommender", None)
    if recommender is None:
        raise HTTPException(status_code=503, detail="Recommendation models are unavailable")
    try:
        model_request = payload.to_recommender_request()
        # Histories are read from storage, never supplied by the caller.
        saves = list_saved(db, session_id) if session_id != "anonymous" else []
        model_request["saved_hikes"] = [
            {**record, "hike_id": record.get("catalog_hike_id")} for record in saves
        ]
        result = recommend(recommender, model_request)
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Recommendation inference failed") from error


@router.get("/recommendations/options")
def recommendation_options(request: Request):
    recommender = getattr(request.app.state, "recommender", None)
    if recommender is None:
        raise HTTPException(status_code=503, detail="Recommendation models are unavailable")
    return catalog_options(recommender)


def settings_dependency() -> Settings:
    return get_settings()


def session_id_dependency(x_session_id: str | None) -> str:
    value = x_session_id or "anonymous"
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise HTTPException(status_code=400, detail="Invalid X-Session-ID")
    return value


@router.get("/feed/shorts")
def feed_shorts(
    query: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=30)] = 20,
    settings: Settings = Depends(settings_dependency),
):
    try:
        return {"items": search_shorts(settings, query, limit)}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="YouTube request failed") from error


@router.get("/trails/search")
def trail_search(
    query: Annotated[str, Query(min_length=2, max_length=200)],
    settings: Settings = Depends(settings_dependency),
):
    try:
        return {"items": search_places(settings, query)}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Google Places request failed") from error


@router.get("/trails/details/{place_id}")
def trail_details(place_id: str, settings: Settings = Depends(settings_dependency)):
    try:
        return get_place_details(settings, place_id)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Google Places details request failed") from error


@router.get("/trails/metrics")
def trail_metrics(
    name: Annotated[str, Query(min_length=2, max_length=200)],
    settings: Settings = Depends(settings_dependency),
):
    try:
        return get_metrics(settings, name)
    except Exception as error:
        raise HTTPException(status_code=502, detail="AllTrails metrics request failed") from error


@router.get("/saved", response_model=list[SavedTrail])
def saved_trails(
    x_session_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return list_saved(db, session_id_dependency(x_session_id))


@router.post("/saved", response_model=SaveToggleResponse)
def toggle_saved(
    payload: SaveToggleRequest,
    x_session_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    session_id = session_id_dependency(x_session_id)
    if payload.catalog_hike_id and not payload.place_id:
        existing_catalog = db.scalar(
            select(SavedCatalogRecord).where(
                SavedCatalogRecord.session_id == session_id,
                SavedCatalogRecord.catalog_hike_id == payload.catalog_hike_id,
            )
        )
        if payload.saved and existing_catalog is None:
            existing_catalog = SavedCatalogRecord(
                session_id=session_id,
                catalog_hike_id=payload.catalog_hike_id,
                name=payload.name,
                address=payload.address,
                latitude=payload.latitude,
                longitude=payload.longitude,
                metrics_json=payload.metrics.model_dump_json() if payload.metrics else None,
            )
            db.add(existing_catalog)
        elif not payload.saved and existing_catalog is not None:
            db.delete(existing_catalog)
        db.commit()
        return {"saved": bool(payload.saved), "trail": catalog_record_to_dict(existing_catalog) if payload.saved and existing_catalog else payload}
    existing = db.scalar(
        select(SavedTrailRecord).where(
            SavedTrailRecord.session_id == session_id,
            SavedTrailRecord.place_id == payload.place_id if payload.place_id else SavedTrailRecord.catalog_hike_id == payload.catalog_hike_id,
        )
    )
    if payload.saved and existing is None:
        existing = SavedTrailRecord(
            session_id=session_id,
            place_id=payload.place_id,
            catalog_hike_id=payload.catalog_hike_id,
            name=payload.name,
            address=payload.address,
            latitude=payload.latitude,
            longitude=payload.longitude,
            rating=payload.rating,
            user_rating_count=payload.user_rating_count,
            video_id=payload.video_id,
            metrics_json=payload.metrics.model_dump_json() if payload.metrics else None,
        )
        db.add(existing)
    elif not payload.saved and existing is not None:
        db.delete(existing)
    db.commit()
    if existing is None:
        return {"saved": False, "trail": payload}
    if not payload.saved:
        return {"saved": False, "trail": payload}
    db.refresh(existing)
    return {"saved": True, "trail": record_to_dict(existing)}
