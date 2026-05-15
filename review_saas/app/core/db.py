# filename: app/core/db.py

import os
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from sqlalchemy import text

# ==========================================================
# BASE + MODELS IMPORT
# ==========================================================

from app.core.base import Base

# VERY IMPORTANT
# This forces SQLAlchemy to load ALL models
from app.core.models import *

# ==========================================================
# SCHEMA VERSION
# ==========================================================

CURRENT_SCHEMA_VERSION = "2026-05-15-V1"

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(
    "app.core.db"
)

# ==========================================================
# DATABASE URL
# ==========================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

if not DATABASE_URL:

    raise RuntimeError(
        "❌ DATABASE_URL not set"
    )

# ==========================================================
# FIX RAILWAY POSTGRES URL
# ==========================================================

if DATABASE_URL.startswith(
    "postgres://"
):

    DATABASE_URL = DATABASE_URL.replace(

        "postgres://",

        "postgresql+asyncpg://",

        1
    )

# ==========================================================
# ENGINE
# ==========================================================

engine = create_async_engine(

    DATABASE_URL,

    pool_pre_ping=True,

    future=True,

    echo=False
)

# ==========================================================
# SESSION FACTORY
# ==========================================================

AsyncSessionLocal = async_sessionmaker(

    bind=engine,

    class_=AsyncSession,

    expire_on_commit=False
)

# ==========================================================
# BACKWARD COMPATIBILITY
# ==========================================================

SessionLocal = AsyncSessionLocal

# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================

async def init_models():

    """
    SAFE DATABASE INITIALIZATION
    """

    try:

        async with engine.begin() as conn:

            # ==============================================
            # CREATE SCHEMA TRACKER
            # ==============================================

            await conn.execute(

                text(
                    """
                    CREATE TABLE IF NOT EXISTS _schema_tracker (
                        version TEXT
                    )
                    """
                )

            )

            # ==============================================
