# ==========================================================
# FILE: app/main.py
# ==========================================================

import os
import sys
import traceback
import logging

from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    JSONResponse,
)

from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.sessions import SessionMiddleware

from starlette.templating import Jinja2Templates

from starlette.staticfiles import StaticFiles

from loguru import logger

# ==========================================================
# DEBUG STARTUP
# ==========================================================

print("🚀 MAIN.PY STARTING")
print("🐍 PYTHON VERSION:", sys.version)

# ==========================================================
# IMPORT CONFIG
# ==========================================================

try:

    from app.core.config import settings

    print("✅ CONFIG IMPORTED")

except Exception as e:

    print("❌ CONFIG IMPORT FAILED")
    print(e)

    raise

# ==========================================================
# SAFE DB IMPORT
# ==========================================================

try:

    from app.core.db import init_models

    print("✅ DB IMPORTED")

except Exception as e:

    print("❌ DB IMPORT FAILED")
    print(e)

    init_models = None

# ==========================================================
# ROUTE IMPORTS
# ==========================================================

try:

    from app.routes import auth
    from app.routes import companies
    from app.routes import dashboard
    from app.routes import reviews
    from app.routes import chatbot
    from app.routes import reports

    print("✅ ROUTES IMPORTED")

except Exception as e:

    print("❌ ROUTES IMPORT FAILED")
    print(e)

    traceback.print_exc()

    raise

# ==========================================================
# LOGGING
# ==========================================================

logger.remove()

logger.add(
    sys.stdout,
    level="INFO",
    enqueue=True
)

logging.basicConfig(level=logging.INFO)

# ==========================================================
# BASE DIR
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("✅ BASE_DIR:", BASE_DIR)

# ==========================================================
# LIFESPAN
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 STARTUP INITIATED")

    # IMPORTANT:
    # TEMP DISABLE HEAVY INIT

    try:

        if init_models:

            logger.info("📦 INITIALIZING DATABASE")

            await init_models()

            logger.success("✅ DATABASE INITIALIZED")

    except Exception as e:

        logger.error("❌ DATABASE INIT FAILED")
        logger.error(str(e))
        logger.error(traceback.format_exc())

    logger.success("✅ STARTUP COMPLETE")

    yield

    logger.info("🛑 SHUTDOWN COMPLETE")

# ==========================================================
# FASTAPI APP
# ==========================================================

app = FastAPI(

    title="Review Intel AI",

    version="3.0.0",

    lifespan=lifespan
)

print("✅ FASTAPI CREATED")

# ==========================================================
# ERROR HANDLER
# ==========================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    logger.error(f"❌ ERROR: {request.url}")

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

    allow_headers=["*"],
)

print("✅ CORS ENABLED")

# ==========================================================
# SESSION
# ==========================================================

SECRET_KEY = getattr(
    settings,
    "SECRET_KEY",
    "railway-secret"
)

app.add_middleware(

    SessionMiddleware,

    secret_key=SECRET_KEY
)

print("✅ SESSION ENABLED")

# ==========================================================
# TEMPLATES
# ==========================================================

TEMPLATE_DIR = os.path.join(
    BASE_DIR,
    "templates"
)

templates = Jinja2Templates(
    directory=TEMPLATE_DIR
)

print("✅ TEMPLATES READY")

# ==========================================================
# STATIC
# ==========================================================

STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)

if os.path.exists(STATIC_DIR):

    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static"
    )

    print("✅ STATIC MOUNTED")

# ==========================================================
# ROOT
# ==========================================================

@app.get("/")
async def root():

    return {
        "status": "running"
    }

# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
async def health():

    return {

        "status": "healthy",

        "timestamp": datetime.utcnow().isoformat()
    }

# ==========================================================
# ROUTERS
# ==========================================================

try:

    app.include_router(
        auth.router,
        prefix="/api/auth"
    )

    app.include_router(
        companies.router,
        prefix="/api"
    )

    app.include_router(
        dashboard.router,
        prefix="/api"
    )

    app.include_router(
        reviews.router,
        prefix="/api"
    )

    app.include_router(
        chatbot.router,
        prefix="/api"
    )

    app.include_router(
        reports.router
    )

    print("✅ ROUTERS REGISTERED")

except Exception as e:

    print("❌ ROUTER ERROR")
    print(e)

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

        reload=False
    )
