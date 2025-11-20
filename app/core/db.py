from typing import AsyncGenerator
import urllib.parse
import os
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from app.core.config import settings

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """
    Initialize the async database engine.
    Alembic handles migrations — this only verifies connectivity.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(lambda _: None)  # no-op to test connection
    print("✅ Database engine initialized (Alembic-managed)")


async def close_db():
    """
    Close all database connections on application shutdown.
    """
    await async_engine.dispose()
    print("🧹 Database connections closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session