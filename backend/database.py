import json
from pathlib import Path
from typing import Iterator

from sqlalchemy import Float, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


class SavedTrailRecord(Base):
    __tablename__ = "saved_trails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    catalog_hike_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavedCatalogRecord(Base):
    __tablename__ = "saved_catalog_hikes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    catalog_hike_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)


settings = get_settings()
if settings.database_url.startswith("sqlite:///./"):
    Path(".").mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database() -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("saved_trails")}
        if "catalog_hike_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE saved_trails ADD COLUMN catalog_hike_id VARCHAR(64)"))


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
        "catalog_hike_id": record.catalog_hike_id,
        "name": record.name,
        "address": record.address,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "rating": record.rating,
        "user_rating_count": record.user_rating_count,
        "video_id": record.video_id,
        "metrics": json.loads(record.metrics_json) if record.metrics_json else None,
    }


def catalog_record_to_dict(record: SavedCatalogRecord) -> dict:
    return {
        "id": record.id,
        "place_id": None,
        "catalog_hike_id": record.catalog_hike_id,
        "name": record.name,
        "address": record.address,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "rating": None,
        "user_rating_count": None,
        "video_id": None,
        "metrics": json.loads(record.metrics_json) if record.metrics_json else None,
    }


def list_saved(session: Session, session_id: str) -> list[dict]:
    records = session.scalars(
        select(SavedTrailRecord)
        .where(SavedTrailRecord.session_id == session_id)
        .order_by(SavedTrailRecord.id.desc())
    )
    catalog_records = session.scalars(
        select(SavedCatalogRecord)
        .where(SavedCatalogRecord.session_id == session_id)
        .order_by(SavedCatalogRecord.id.desc())
    )
    return [record_to_dict(record) for record in records] + [catalog_record_to_dict(record) for record in catalog_records]
