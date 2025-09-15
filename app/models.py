# app/models.py
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, JSON, UniqueConstraint, Index, Text
from datetime import datetime, timezone
from typing import Optional
from app.db import Base

class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    price_eur: Mapped[float] = mapped_column(Float)
    unit_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

    price_per_unit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_per_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fees_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ship_estimate_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    margin_estimate_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flip_score: Mapped[Optional[float]] = mapped_column(Float, index=True, nullable=True)

    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external"),
        Index("idx_listings_recent", "created_at"),
    )

class User(Base):
    __tablename__ = "users"
    tg_user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_city: Mapped[str] = mapped_column(String(100), default="Marseille")
    base_lat: Mapped[float] = mapped_column(Float, default=43.2965)
    base_lon: Mapped[float] = mapped_column(Float, default=5.3698)
    radius_km: Mapped[int] = mapped_column(Integer, default=500)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    watches: Mapped[list["Watch"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Watch(Base):
    __tablename__ = "watches"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_user_id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(200))
    radius_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_margin_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_price_eur: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    categories: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    user: Mapped[User] = relationship(back_populates="watches")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserSeen(Base):
    __tablename__ = "user_seen"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    listing_id: Mapped[int] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_user_listing_seen"),)
