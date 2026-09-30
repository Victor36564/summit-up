import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config import Settings, get_settings
from database import SavedTrailRecord, get_db, list_saved, record_to_dict
from schemas import SaveToggleRequest, SaveToggleResponse, SavedTrail
from services.alltrails import get_metrics
from services.google_places import get_place_details, search_places
from services.youtube import search_shorts

router = APIRouter(prefix="/api")


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
    limit: Annotated[int, Query(ge=1, le=30)] = 10,
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
    existing = db.scalar(
        select(SavedTrailRecord).where(
            SavedTrailRecord.session_id == session_id,
            SavedTrailRecord.place_id == payload.place_id,
        )
    )
    if payload.saved and existing is None:
        existing = SavedTrailRecord(
            session_id=session_id,
            place_id=payload.place_id,
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
