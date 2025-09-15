# app/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

# Normalize sync/async URL for SQLite if needed
def to_async_url(url: str) -> str:
    if url.startswith("sqlite+sqlite///"):
        file_path = url.replace("sqlite+sqlite///", "")
        return f"sqlite+aiosqlite:///{file_path}"
    if url.startswith("sqlite///"):
        return url.replace("sqlite///", "sqlite+aiosqlite///")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    return url

ASYNC_DATABASE_URL = to_async_url(settings.DATABASE_URL)

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    from app.models import Listing, User, Watch, UserSeen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
