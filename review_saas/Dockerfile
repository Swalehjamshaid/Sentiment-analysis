# ==========================================================
# REVIEW INTEL AI — RAILWAY PRODUCTION DOCKERFILE
# MAY 2026 ENTERPRISE VERSION
#
# SUPPORTS:
# ✅ FASTAPI
# ✅ PLAYWRIGHT
# ✅ CAMOUFOX
# ✅ SELENIUMBASE
# ✅ UNDETECTED CHROMEDRIVER
# ✅ GOOGLE MAPS SCRAPING
# ✅ FIREFOX + CHROMIUM
# ✅ STEALTH BROWSERS
# ✅ RAILWAY DEPLOYMENT
# ==========================================================

FROM python:3.11-slim

# ==========================================================
# PYTHON SETTINGS
# ==========================================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ==========================================================
# WORK DIRECTORY
# ==========================================================

WORKDIR /app

# ==========================================================
# INSTALL SYSTEM DEPENDENCIES
# ==========================================================

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    wget \
    curl \
    unzip \
    git \
    xvfb \
    ca-certificates \
    fonts-liberation \
    xdg-utils \
    firefox-esr \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libdbus-glib-1-2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxrender1 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxt6 \
    libxi6 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    libu2f-udev \
    libvulkan1 \
    libglu1-mesa \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ==========================================================
# COPY REQUIREMENTS
# ==========================================================

COPY requirements.txt .

# ==========================================================
# UPGRADE PIP TO LATEST
# ==========================================================

RUN pip install --upgrade pip setuptools wheel

# ==========================================================
# INSTALL PYTHON REQUIREMENTS
# ==========================================================

RUN pip install --no-cache-dir -r requirements.txt

# ==========================================================
# INSTALL PLAYWRIGHT BROWSERS + DEPS
# ==========================================================

RUN playwright install --with-deps chromium firefox

# ==========================================================
# INSTALL CAMOUFOX BROWSER
# ==========================================================

RUN python -m camoufox fetch

# ==========================================================
# CREATE PLAYWRIGHT CACHE DIR
# ==========================================================

RUN mkdir -p /ms-playwright

# ==========================================================
# COPY PROJECT FILES
# ==========================================================

COPY . .

# ==========================================================
# CREATE TMP DEBUG DIRECTORY
# ==========================================================

RUN mkdir -p /tmp

# ==========================================================
# EXPOSE PORT
# ==========================================================

EXPOSE 8080

# ==========================================================
# HEALTHCHECK
# ==========================================================

HEALTHCHECK CMD curl --fail http://localhost:8080 || exit 1

# ==========================================================
# START FASTAPI
# ==========================================================

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
