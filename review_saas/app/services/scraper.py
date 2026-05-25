# ==========================================================
# FILE: app/services/scraper.py
# TRUSTLYTICS AI — ULTIMATE MULTI-LAYER GOOGLE REVIEWS SCRAPER
# WORLD-CLASS PRODUCTION ENGINE - MAY 2026
# ==========================================================

import os
import re
import gc
import time
import random
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential
from fake_useragent import UserAgent

# Layer 1 & 2
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# Layer 3
try:
    from curl_cffi import requests as curl_requests
    from browserforge import fingerprints
except ImportError:
    curl_requests = None
    fingerprints = None

# Layer 4
from bs4 import BeautifulSoup
import lxml

from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.models import Review

# ==========================================================
# LOGGER
# ==========================================================
logger = logging.getLogger("app.services.scraper")
logger.setLevel(logging.INFO)

# ==========================================================
# ENV VARIABLES
# ==========================================================
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

# ==========================================================
# CONFIG
# ==========================================================
REQUEST_TIMEOUT = 90
PLAYWRIGHT_TIMEOUT = 75000
HEADLESS = True
MAX_SCROLLS = 30
TARGET_LIMIT = 150

# ==========================================================
# HELPERS
# ==========================================================
def clean_text(text):
    try:
        if not text:
            return ""
        text = str(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:5000]
    except:
        return ""


def generate_hash(author: str, text: str) -> str:
    raw = f"{author}_{text}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_user_agent():
    try:
        return UserAgent().random
    except:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def parse_relative_date(relative_text):
    try:
        if not relative_text:
            return datetime.utcnow()
        text = str(relative_text).lower()
        now = datetime.utcnow()
        num = int(re.search(r"(\d+)", text).group(1)) if re.search(r"(\d+)", text) else 1

        if "day" in text: return now - timedelta(days=num)
        if "week" in text: return now - timedelta(weeks=num)
        if "month" in text: return now - timedelta(days=num * 30)
        if "year" in text: return now - timedelta(days=num * 365)
        return now
    except:
        return datetime.utcnow()


def get_proxy_dict():
    if not PROXY_SERVER:
        return None
    return {
        "server": f"http://{PROXY_SERVER}",
        "username": f"{PROXY_USERNAME}-session-{int(time.time())}",
        "password": PROXY_PASSWORD
    }


# ==========================================================
# LOAD EXISTING REVIEWS
# ==========================================================
async def load_existing_review_ids(company_id: int):
    existing = set()
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Review.google_review_id).where(Review.company_id == company_id)
            result = await db.execute(stmt)
            for row in result.fetchall():
                if row[0]:
                    existing.add(row[0])
        logger.info(f"✅ EXISTING IDS LOADED: {len(existing)}")
        return existing
    except Exception as e:
        logger.warning(f"⚠️ Failed to load existing IDs: {e}")
        return set()


# ==========================================================
# LAYER 1: SERPAPI (Fastest)
# ==========================================================
@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=1.5, max=10))
async def layer1_serpapi(place_id: str, existing_ids: set, target_limit: int = 100):
    if not SERPAPI_KEY:
        logger.warning("⚠️ SERPAPI KEY MISSING")
        return []

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            params = {
                "engine": "google_maps_reviews",
                "place_id": place_id,
                "api_key": SERPAPI_KEY,
                "sort_by": "newestFirst"
            }

            response = await client.get("https://serpapi.com/search.json", params=params)
            data = response.json()
            raw_reviews = data.get("reviews", [])

            reviews = []
            seen = set()

            for review in raw_reviews:
                try:
                    author = clean_text(review.get("user", {}).get("name", ""))
                    text = clean_text(review.get("snippet", ""))
                    if not text: continue

                    review_id = generate_hash(author, text)
                    if review_id in seen or review_id in existing_ids:
                        continue

                    seen.add(review_id)
                    existing_ids.add(review_id)

                    reviews.append({
                        "review_id": review_id,
                        "author_name": author,
                        "rating": int(review.get("rating", 5)),
                        "review_date": clean_text(review.get("date", "")),
                        "google_review_time": parse_relative_date(review.get("date")).isoformat(),
                        "text": text,
                        "likes": 0,
                        "sentiment": "positive" if int(review.get("rating", 5)) >= 4 else "negative"
                    })

                    if len(reviews) >= target_limit:
                        break
                except:
                    continue

            logger.info(f"✅ LAYER 1 (SERPAPI) → {len(reviews)} reviews")
            return reviews
    except Exception as e:
        logger.warning(f"❌ LAYER 1 FAILED: {e}")
        return []


# ==========================================================
# LAYER 2: PLAYWRIGHT + STEALTH (Most Reliable)
# ==========================================================
@retry(stop=stop_after_attempt(2), wait=wait_random_exponential(multiplier=2, max=12))
async def layer2_playwright(place_id: str, existing_ids: set, target_limit: int = 80):
    reviews = []
    browser = None
    try:
        async with async_playwright() as p:
            proxy = get_proxy_dict()
            browser = await p.chromium.launch(
                headless=HEADLESS,
                proxy=proxy,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )

            context = await browser.new_context(user_agent=get_user_agent())
            page = await context.new_page()
            await stealth_async(page)

            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            await page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)

            await asyncio.sleep(random.uniform(4, 7))

            # Click "More Reviews"
            try:
                await page.locator('button[jsaction*="pane.reviewChart.moreReviews"]').first.click()
                await asyncio.sleep(5)
            except:
                pass

            # Scroll
            for _ in range(MAX_SCROLLS):
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(random.uniform(1.2, 2.8))

            cards = page.locator("div.jftiEf")
            count = await cards.count()

            seen = set()
            for i in range(min(count, target_limit * 2)):
                try:
                    card = cards.nth(i)
                    author = clean_text(await card.locator(".d4r55").inner_text())
                    text = clean_text(await card.locator(".wiI7pd").inner_text())
                    if not text: continue

                    review_date = clean_text(await card.locator(".rsqaWe").inner_text())
                    rating = 5
                    try:
                        aria = await card.locator(".kvMYJc").get_attribute("aria-label")
                        match = re.search(r"(\d)", str(aria))
                        if match: rating = int(match.group(1))
                    except:
                        pass

                    review_id = generate_hash(author, text)
                    if review_id in seen or review_id in existing_ids:
                        continue

                    seen.add(review_id)
                    existing_ids.add(review_id)

                    reviews.append({
                        "review_id": review_id,
                        "author_name": author,
                        "rating": rating,
                        "review_date": review_date,
                        "google_review_time": parse_relative_date(review_date).isoformat(),
                        "text": text,
                        "likes": 0,
                        "sentiment": "positive" if rating >= 4 else "negative"
                    })

                    if len(reviews) >= target_limit:
                        break
                except:
                    continue

        logger.info(f"✅ LAYER 2 (PLAYWRIGHT) → {len(reviews)} reviews")
        return reviews

    except Exception as e:
        logger.warning(f"❌ LAYER 2 FAILED: {e}")
        return []
    finally:
        if browser:
            await browser.close()


# ==========================================================
# LAYER 3: CURL_CFFI + BROWSERFORGE (Advanced Anti-Detection)
# ==========================================================
async def layer3_curl_cffi(place_id: str, existing_ids: set, target_limit: int = 50):
    if not curl_requests:
        return []
    try:
        # This layer is complex and requires full HTML parsing.
        # For now, we return empty as it's very advanced and needs custom implementation.
        logger.info("⚠️ LAYER 3 (CURL_CFFI) - Not fully implemented yet")
        return []
    except:
        return []


# ==========================================================
# MAIN MULTI-LAYER SCRAPER
# ==========================================================
async def scrape_google_reviews(
    place_id: str,
    company_id: int = None,
    target_limit: int = 120
):
    logger.info(f"🚀 STARTING MULTI-LAYER SCRAPER → {place_id}")

    try:
        existing_ids = await load_existing_review_ids(company_id) if company_id else set()

        # ==================== LAYER 1 ====================
        reviews = await layer1_serpapi(place_id, existing_ids, target_limit)

        # ==================== LAYER 2 ====================
        if len(reviews) < target_limit * 0.6:
            remaining = target_limit - len(reviews)
            pw_reviews = await layer2_playwright(place_id, existing_ids, remaining)
            reviews.extend(pw_reviews)

        # ==================== LAYER 3 (Future) ====================
        if len(reviews) < 30:
            cf_reviews = await layer3_curl_cffi(place_id, existing_ids, target_limit - len(reviews))
            reviews.extend(cf_reviews)

        # Final Deduplication
        final = []
        seen = set()
        for r in reviews:
            rid = r.get("review_id")
            if rid and rid not in seen:
                seen.add(rid)
                final.append(r)

        logger.info(f"🎯 FINAL REVIEWS EXTRACTED: {len(final)}")
        return final

    except Exception as e:
        logger.exception(f"❌ ULTIMATE SCRAPER FAILED: {e}")
        return []
    finally:
        gc.collect()
