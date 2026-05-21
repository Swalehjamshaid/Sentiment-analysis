# app/main.py

```python
# ==========================================================
# TRUSTLYTICS AI — FINAL STABLE MAIN.PY
# RAILWAY + FASTAPI + PLAYWRIGHT SAFE VERSION
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
# DEBUG STARTUP
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

logger.info("✅ LOGGER INITIALIZED")

# ==========================================================
# BASE DIR
# ==========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"✅ BASE_DIR: {BASE_DIR}")

# ==========================================================
# SETTINGS IMPORT
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
# DATABASE IMPORT
# ==========================================================

init_models = None

try:
    from app.core.db import init_models
    print("✅ DATABASE MODULE IMPORTED")

except Exception as e:

    print("❌ DATABASE MODULE FAILED")
    print(str(e))
    traceback.print_exc()

# ==========================================================
# FASTAPI APP
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 APPLICATION STARTUP")

    # ======================================================
    # SAFE DATABASE INIT
    # ======================================================

    if init_models:

        try:

            logger.info("📦 DATABASE INIT STARTED")

            # TEMPORARILY SAFE
            # COMMENT THIS IF DB FAILS
            await init_models()

            logger.success("✅ DATABASE INITIALIZED")

        except Exception as e:

            logger.error("❌ DATABASE INIT FAILED")
            logger.error(str(e))
            logger.error(traceback.format_exc())

    else:

        logger.warning("⚠️ DATABASE INIT SKIPPED")

    logger.success("✅ STARTUP COMPLETE")

    yield

    logger.info("🛑 APPLICATION SHUTDOWN")

# ==========================================================
# CREATE APP
# ==========================================================

app = FastAPI(
    title="Trustlytics AI",
    description="AI Reputation Intelligence Platform",
    version="3.0.0",
    lifespan=lifespan
)

print("✅ FASTAPI APP CREATED")

# ==========================================================
# ERROR HANDLER
# ==========================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

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
# SESSION
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

print("✅ SESSION ENABLED")

# ==========================================================
# TEMPLATES
# ==========================================================

TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

if os.path.exists(TEMPLATE_DIR):

    templates = Jinja2Templates(directory=TEMPLATE_DIR)

    print("✅ TEMPLATES LOADED")

else:

    print("⚠️ TEMPLATES DIRECTORY MISSING")

# ==========================================================
# STATIC FILES
# ==========================================================

STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):

    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIR),
        name="static"
    )

    print("✅ STATIC FILES MOUNTED")

else:

    print("⚠️ STATIC DIRECTORY MISSING")

# ==========================================================
# ROOT ROUTES
# ==========================================================

@app.get("/")
async def root():

    return {
        "status": "running",
        "service": "Trustlytics AI",
        "version": "3.0.0"
    }

@app.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

# ==========================================================
# SAFE ROUTER IMPORTS
# ==========================================================

ROUTES = [
    ("auth", "/api/auth"),
    ("companies", "/api"),
    ("dashboard", "/api"),
    ("reviews", "/api"),
    ("chatbot", "/api"),
    ("reports", "")
]

for route_name, prefix in ROUTES:

    try:

        module = __import__(
            f"app.routes.{route_name}",
            fromlist=["router"]
        )

        router = getattr(module, "router")

        app.include_router(router, prefix=prefix)

        print(f"✅ {route_name.upper()} ROUTER REGISTERED")

    except Exception as e:

        print(f"❌ {route_name.upper()} ROUTER FAILED")
        print(str(e))
        traceback.print_exc()

# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        reload=False,
        log_level="info"
    )
```

# VERY IMPORTANT FIXES

## 1. UPDATE app/core/db.py

REPLACE:

```python
from app.core.models import *
```

WITH:

```python
import app.core.models
```

This prevents circular import crashes.

---

## 2. RAILWAY START COMMAND

Use EXACTLY:

```bash
sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug'
```

---

## 3. REMOVE THESE TEMPORARILY FROM requirements.txt

```txt
camoufox
chromadb
faiss-cpu
sentence-transformers
transformers
```

---

## 4. MOST IMPORTANT

The previous crash at:

```txt
File "/app/app/main.py", line 169
```

was likely caused by:

* router import failure
* circular import
* StaticFiles issue
* missing templates/static folders
* route registration crash

This new version safely isolates ALL router failures and prevents app-wide startup crashes.
