# ==========================================================
# TRUSTLYTICS AI — ULTRA STABLE RAILWAY DOCKERFILE
# MAY 2026 PRODUCTION SAFE VERSION
#
# GOALS:
# ✅ Railway Stable
# ✅ No Memory Crash
# ✅ FastAPI
# ✅ Playwright
# ✅ Google Maps Scraping
# ✅ AI Chatbot
# ✅ PDF Reporting
# ✅ Lightweight Chromium
# ✅ Production Optimized
# ==========================================================

FROM python:3.11-slim

# ==========================================================
# ENVIRONMENT VARIABLES
# ==========================================================

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive

# ==========================================================
# WORK DIRECTORY
# ==========================================================

WORKDIR /app

# ==========================================================
# INSTALL ONLY ESSENTIAL SYSTEM PACKAGES
# ==========================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    gcc \
    g++ \
    build-essential \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libxshmfence1 \
    libu2f-udev \
    libvulkan1 \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    fonts-liberation \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ==========================================================
# UPGRADE PIP
# ==========================================================

RUN python -m pip install --upgrade pip setuptools wheel

# ==========================================================
# COPY REQUIREMENTS FIRST
# ==========================================================

COPY requirements.txt .

# ==========================================================
# INSTALL PYTHON REQUIREMENTS
# ==========================================================

RUN pip install --no-cache-dir -r requirements.txt

# ==========================================================
# INSTALL PLAYWRIGHT ONLY
# ==========================================================

RUN playwright install chromium

# ==========================================================
# CREATE REQUIRED DIRECTORIES
# ==========================================================

RUN mkdir -p /tmp /app/logs /app/uploads

# ==========================================================
# COPY APPLICATION
# ==========================================================

COPY . .

# ==========================================================
# EXPOSE PORT
# ==========================================================

EXPOSE 8080

# ==========================================================
# HEALTHCHECK
# ==========================================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
CMD curl --fail http://localhost:8080/ || exit 1

# ==========================================================
# GUNICORN CONFIGURATION
# ==========================================================

ENV GUNICORN_CMD_ARGS="\
--workers=1 \
--worker-class=uvicorn.workers.UvicornWorker \
--bind=0.0.0.0:8080 \
--timeout=300 \
--keep-alive=5"

# ==========================================================
# START APPLICATION
# ==========================================================

CMD ["gunicorn", "app.main:app"]
