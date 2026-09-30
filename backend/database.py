import json
from pathlib import Path
from typing import Iterator

from sqlalchemy import Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


class SavedTrailRecord(Base):
    __tablename__ = "saved_trails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    place_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)


settings = get_settings()
if settings.database_url.startswith("sqlite:///./"):
    Path(".").mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def record_to_dict(record: SavedTrailRecord) -> dict:
    return {
        "id": record.id,
        "place_id": record.place_id,
        "name": record.name,
        "address": record.address,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "rating": record.rating,
        "user_rating_count": record.user_rating_count,
        "video_id": record.video_id,
        "metrics": json.loads(record.metrics_json) if record.metrics_json else None,
    }


def list_saved(session: Session, session_id: str) -> list[dict]:
    records = session.scalars(
        select(SavedTrailRecord)
        .where(SavedTrailRecord.session_id == session_id)
        .order_by(SavedTrailRecord.id.desc())
    )
    return [record_to_dict(record) for record in records]
