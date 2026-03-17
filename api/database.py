import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_raw_url = os.getenv("DATABASE_URL", "")

if not _raw_url:
    raise RuntimeError("DATABASE_URL environment variable is not set.")


def _build_asyncpg_url(raw: str) -> str:
    """Convert any postgres:// URL into postgresql+asyncpg:// and strip params
    that asyncpg doesn't understand (sslmode, channel_binding)."""
    # Swap scheme
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Strip unsupported query params
    parsed = urlparse(raw)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    for key in ("sslmode", "channel_binding"):
        params.pop(key, None)
    clean = urlunparse(parsed._replace(query=urlencode(params)))
    return clean


DATABASE_URL = _build_asyncpg_url(_raw_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": "require"},  # NeonDB requires SSL; handled separately from URL params
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
