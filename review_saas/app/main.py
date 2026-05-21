# ==========================================================
# FILE: app/main.py
# TRUSTLYTICS AI — FINAL RAILWAY STABLE MAIN.PY
# MAY 2026 ENTERPRISE VERSION
# ==========================================================

import os
import sys
import traceback
import logging

from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from loguru import logger

# ==========================================================
# STARTUP DEBUG
# ==========================================================

print("🚀 TRUSTLYTICS STARTING")
print("🐍 PYTHON VERSION:", sys.version)

# ==========================================================
# LOGGING
# ==========================================================

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    enqueue=True,
    backtrace=True,
    diagnose=False
)

logging.basicConfig(level=logging.INFO)

logger.info("✅ Logger Initialized")

# ==========================================================
# BASE DIRECTORY
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

print(f"✅ BASE_DIR: {BASE_DIR}")

# ==========================================================
# SETTINGS
# ==========================================================

try:

    from app.core.config import settings

    print("✅ SETTINGS IMPORTED")

except Exception as e:

    print("❌ SETTINGS IMPORT FAILED")
    print(str(e))

    traceback.print_exc()

    class DummySettings:
        SECRET_KEY = "railway-secret"

    settings = DummySettings()

# ==========================================================
# DATABASE
# ==========================================================

try:

    from app.core.db import init_models

    print("✅ DATABASE MODULE IMPORTED")

except Exception as e:

    print("❌ DATABASE IMPORT FAILED")
    print(str(e))

    traceback.print_exc()

    init_models = None

# ==========================================================
# ROUTER PLACEHOLDERS
# ==========================================================

auth_router = None
companies_router = None
dashboard_router = None
reviews_router = None
chatbot_router = None
reports_router = None

# ==========================================================
# AUTH ROUTE
# ==========================================================

try:

    from app.routes.auth import router as auth_router

    print("✅ AUTH ROUTE IMPORTED")

except Exception as e:

    print("❌ AUTH ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# COMPANIES ROUTE
# ==========================================================

try:

    from app.routes.companies import router as companies_router

    print("✅ COMPANIES ROUTE IMPORTED")

except Exception as e:

    print("❌ COMPANIES ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# DASHBOARD ROUTE
# ==========================================================

try:

    from app.routes.dashboard import router as dashboard_router

    print("✅ DASHBOARD ROUTE IMPORTED")

except Exception as e:

    print("❌ DASHBOARD ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# REVIEWS ROUTE
# ==========================================================

try:

    from app.routes.reviews import router as reviews_router

    print("✅ REVIEWS ROUTE IMPORTED")

except Exception as e:

    print("❌ REVIEWS ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# CHATBOT ROUTE
# ==========================================================

try:

    from app.routes.chatbot import router as chatbot_router

    print("✅ CHATBOT ROUTE IMPORTED")

except Exception as e:

    print("❌ CHATBOT ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# REPORTS ROUTE
# ==========================================================

try:

    from app.routes.reports import router as reports_router

    print("✅ REPORTS ROUTE IMPORTED")

except Exception as e:

    print("❌ REPORTS ROUTE FAILED")
    print(str(e))

    traceback.print_exc()

# ==========================================================
# APPLICATION LIFESPAN
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 APPLICATION STARTUP INITIATED")

    # ======================================================
    # TEMP SAFE DATABASE INIT
    # ======================================================

    try:

        if init_models:

            logger.info("📦 DATABASE INIT STARTED")

            # TEMPORARILY SAFE
            # COMMENT THIS AGAIN IF STARTUP FREEZES

            await init_models()

            logger.success("✅ DATABASE INITIALIZED")

        else:

            logger.warning("⚠️ DATABASE INIT SKIPPED")

    except Exception as e:

        logger.error("❌ DATABASE INIT FAILED")

        logger.error(str(e))

        logger.error(traceback.format_exc())

    logger.success("✅ APPLICATION STARTUP COMPLETE")

    yield

    logger.info("🛑 APPLICATION SHUTDOWN COMPLETE")

# ==========================================================
# FASTAPI APPLICATION
# ==========================================================

app = FastAPI(

    title="Trustlytics AI",

    description="AI Reputation Intelligence SaaS Platform",

    version="3.0.0",

    lifespan=lifespan
)

print("✅ FASTAPI APP CREATED")

# ==========================================================
# GLOBAL ERROR HANDLER
# ==========================================================

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.error(f"❌ GLOBAL ERROR: {request.url}")

    logger.error(traceback.format_exc())

    return JSONResponse(

        status_code=500,

        content={

            "status": "error",

            "message": str(exc)
        }
    )

# ==========================================================
# CORS
# ==========================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)

print("✅ CORS ENABLED")

# ==========================================================
# SESSION MIDDLEWARE
# ==========================================================

SECRET_KEY = getattr(
    settings,
    "SECRET_KEY",
    "railway-secret"
)

app.add_middleware(

    SessionMiddleware,

    secret_key=SECRET_KEY,

    session_cookie="trustlytics_session",

    max_age=86400,

    same_site="lax",

    https_only=False
)

print("✅ SESSION MIDDLEWARE ENABLED")

# ==========================================================
# TEMPLATES
# ==========================================================

TEMPLATE_DIR = os.path.join(
    BASE_DIR,
    "templates"
)

if os.path.exists(TEMPLATE_DIR):

    templates = Jinja2Templates(
        directory=TEMPLATE_DIR
    )

    print("✅ TEMPLATES LOADED")

else:

    print("⚠️ TEMPLATES DIRECTORY MISSING")

# ==========================================================
# STATIC FILES
# ==========================================================

STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)

if os.path.exists(STATIC_DIR):

    app.mount(

        "/static",

        StaticFiles(
            directory=STATIC_DIR
        ),

        name="static"
    )

    print("✅ STATIC FILES MOUNTED")

else:

    print("⚠️ STATIC DIRECTORY MISSING")

# ==========================================================
# ROOT ROUTE
# ==========================================================

@app.get("/")
async def root():

    return {

        "status": "running",

        "service": "Trustlytics AI",

        "version": "3.0.0"
    }

# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/health")
async def health_check():

    return {

        "status": "healthy",

        "timestamp": datetime.utcnow().isoformat()
    }

# ==========================================================
# ROUTER REGISTRATION
# ==========================================================

if auth_router:

    app.include_router(
        auth_router
    )

    print("✅ AUTH ROUTER REGISTERED")

if companies_router:

    app.include_router(
        companies_router
    )

    print("✅ COMPANIES ROUTER REGISTERED")

if dashboard_router:

    app.include_router(
        dashboard_router
    )

    print("✅ DASHBOARD ROUTER REGISTERED")

if reviews_router:

    app.include_router(
        reviews_router
    )

    print("✅ REVIEWS ROUTER REGISTERED")

if chatbot_router:

    app.include_router(
        chatbot_router
    )

    print("✅ CHATBOT ROUTER REGISTERED")

if reports_router:

    app.include_router(
        reports_router
    )

    print("✅ REPORTS ROUTER REGISTERED")

print("✅ ALL ROUTERS PROCESSED")

# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "app.main:app",

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                8080
            )
        ),

        reload=False,

        log_level="info"
    )
