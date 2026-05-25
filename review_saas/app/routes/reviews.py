# ==========================================================
# FILE: app/services/scraper.py
# ==========================================================
# ULTRA SAFE ENTERPRISE SCRAPER
# FIXED VERSION
#
# ✔ NO ROUTE BREAKING
# ✔ NO FASTAPI IMPORT CRASH
# ✔ NO GLOBAL RISKY IMPORTS
# ✔ LAZY IMPORT SYSTEM
# ✔ PROXY SUPPORT
# ✔ CRAWL4AI FIRST
# ✔ PLAYWRIGHT FALLBACK
# ✔ SUPERAPI FALLBACK
# ✔ DUPLICATE SAFE
# ✔ ASYNC SAFE
# ✔ RAILWAY SAFE
# ✔ ENTERPRISE SAFE
# ==========================================================

import os
import re
import asyncio
import logging
import traceback

from datetime import datetime

import aiohttp
import aiosqlite

from bs4 import BeautifulSoup

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential
)

# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("app.services.scraper")

# ==========================================================
# ENV
# ==========================================================

SUPERAPI_KEY = os.getenv("SUPERAPI_KEY", "")

# ==========================================================
# PROXIES
# ==========================================================

PROXIES = [

    os.getenv("PROXY_1"),
    os.getenv("PROXY_2"),
    os.getenv("PROXY_3"),
    os.getenv("PROXY_4"),

]

PROXIES = [p for p in PROXIES if p]

# ==========================================================
# SAFE USER AGENT
# ==========================================================

def get_user_agent():

    try:

        from fake_useragent import UserAgent

        ua = UserAgent()

        return ua.random

    except Exception:

        return (

            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

# ==========================================================
# HELPERS
# ==========================================================

def clean_text(text):

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(text)
    ).strip()

# ==========================================================

def safe_int(value):

    try:
        return int(value)
    except:
        return 0

# ==========================================================

def build_google_url(place_id):

    return (
        f"https://www.google.com/maps/place/?q=place_id:{place_id}"
    )

# ==========================================================
# EXISTING REVIEW IDS
# ==========================================================

async def load_existing_review_ids(company_id):

    try:

        existing_ids = set()

        db_path = "reviews_cache.db"

        async with aiosqlite.connect(db_path) as db:

            await db.execute("""

                CREATE TABLE IF NOT EXISTS existing_reviews (

                    company_id INTEGER,
                    review_id TEXT

                )

            """)

            cursor = await db.execute(

                """

                SELECT review_id
                FROM existing_reviews
                WHERE company_id = ?

                """,

                (company_id,)
            )

            rows = await cursor.fetchall()

            for row in rows:

                existing_ids.add(row[0])

        return existing_ids

    except Exception as e:

        logger.exception(
            f"❌ load_existing_review_ids => {e}"
        )

        return set()

# ==========================================================
# SAVE REVIEW ID
# ==========================================================

async def save_review_id(company_id, review_id):

    try:

        db_path = "reviews_cache.db"

        async with aiosqlite.connect(db_path) as db:

            await db.execute("""

                CREATE TABLE IF NOT EXISTS existing_reviews (

                    company_id INTEGER,
                    review_id TEXT

                )

            """)

            await db.execute(

                """

                INSERT INTO existing_reviews (

                    company_id,
                    review_id

                )

                VALUES (?, ?)

                """,

                (

                    company_id,
                    review_id
                )
            )

            await db.commit()

    except Exception as e:

        logger.exception(
            f"❌ save_review_id => {e}"
        )

# ==========================================================
# NORMALIZER
# ==========================================================

def normalize_review(data):

    try:

        text = clean_text(
            data.get("text", "")
        )

        if not text:
            return None

        review_id = clean_text(

            data.get("review_id")
            or str(hash(text))
        )

        return {

            "review_id":
                review_id,

            "author_name":
                clean_text(
                    data.get(
                        "author_name",
                        "Google User"
                    )
                ),

            "rating":
                max(
                    1,
                    min(
                        safe_int(
                            data.get("rating", 5)
                        ),
                        5
                    )
                ),

            "text":
                text,

            "review_date":
                clean_text(
                    data.get(
                        "review_date",
                        ""
                    )
                ),

            "google_review_time":
                str(datetime.utcnow()),

            "likes":
                safe_int(
                    data.get("likes", 0)
                )
        }

    except Exception:

        return None

# ==========================================================
# CRAWL4AI SCRAPER
# ==========================================================

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2)
)

async def crawl4ai_scraper(

    place_id,
    target_limit

):

    logger.info(
        "🚀 CRAWL4AI STARTED"
    )

    try:

        try:

            from crawl4ai import AsyncWebCrawler

        except Exception as e:

            logger.warning(
                f"⚠️ Crawl4AI unavailable => {e}"
            )

            return []

        reviews = []

        url = build_google_url(place_id)

        async with AsyncWebCrawler() as crawler:

            result = await crawler.arun(

                url=url,

                bypass_cache=True
            )

            html = result.html

            soup = BeautifulSoup(
                html,
                "lxml"
            )

            divs = soup.find_all("div")

            for div in divs:

                text = clean_text(
                    div.get_text()
                )

                if len(text) < 40:
                    continue

                review = normalize_review({

                    "text": text,

                    "rating": 5,

                    "author_name":
                        "Google User",

                    "review_date":
                        str(datetime.utcnow())
                })

                if review:

                    reviews.append(review)

                if len(reviews) >= target_limit:
                    break

        logger.info(
            f"✅ CRAWL4AI => {len(reviews)}"
        )

        return reviews

    except Exception as e:

        logger.exception(
            f"❌ crawl4ai_scraper => {e}"
        )

        return []

# ==========================================================
# PLAYWRIGHT SCRAPER
# ==========================================================

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2)
)

async def playwright_scraper(

    place_id,
    target_limit

):

    logger.info(
        "🚀 PLAYWRIGHT STARTED"
    )

    browser = None

    try:

        try:

            from playwright.async_api import (
                async_playwright
            )

        except Exception as e:

            logger.warning(
                f"⚠️ Playwright unavailable => {e}"
            )

            return []

        try:

            from playwright_stealth import (
                stealth_async
            )

        except Exception:

            stealth_async = None

        reviews = []

        url = build_google_url(place_id)

        proxy = None

        if PROXIES:

            proxy = {

                "server": PROXIES[0]
            }

        async with async_playwright() as p:

            browser = await p.chromium.launch(

                headless=True,

                proxy=proxy,

                args=[

                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            context = await browser.new_context(

                user_agent=get_user_agent(),

                locale="en-US"
            )

            page = await context.new_page()

            if stealth_async:

                try:
                    await stealth_async(page)
                except:
                    pass

            await page.goto(

                url,

                timeout=120000,

                wait_until="domcontentloaded"
            )

            await asyncio.sleep(8)

            html = await page.content()

            soup = BeautifulSoup(
                html,
                "lxml"
            )

            spans = soup.find_all("span")

            for span in spans:

                text = clean_text(
                    span.get_text()
                )

                if len(text) < 40:
                    continue

                review = normalize_review({

                    "text": text,

                    "rating": 5,

                    "author_name":
                        "Google User",

                    "review_date":
                        str(datetime.utcnow())
                })

                if review:

                    reviews.append(review)

                if len(reviews) >= target_limit:
                    break

            await browser.close()

        logger.info(
            f"✅ PLAYWRIGHT => {len(reviews)}"
        )

        return reviews

    except Exception as e:

        logger.exception(
            f"❌ playwright_scraper => {e}"
        )

        try:

            if browser:
                await browser.close()
        except:
            pass

        return []

# ==========================================================
# SUPERAPI
# ==========================================================

async def superapi_scraper(

    place_id,
    target_limit

):

    logger.info(
        "🚀 SUPERAPI STARTED"
    )

    try:

        if not SUPERAPI_KEY:

            logger.warning(
                "⚠️ SUPERAPI KEY MISSING"
            )

            return []

        reviews = []

        headers = {

            "Authorization":
                f"Bearer {SUPERAPI_KEY}",

            "Content-Type":
                "application/json"
        }

        payload = {

            "place_id": place_id,

            "limit": target_limit
        }

        async with aiohttp.ClientSession() as session:

            async with session.post(

                "https://api.superapi.ai/google/reviews",

                headers=headers,

                json=payload,

                timeout=120

            ) as response:

                data = await response.json()

                items = data.get(
                    "reviews",
                    []
                )

                for item in items:

                    review = normalize_review(item)

                    if review:
                        reviews.append(review)

        logger.info(
            f"✅ SUPERAPI => {len(reviews)}"
        )

        return reviews

    except Exception as e:

        logger.exception(
            f"❌ superapi_scraper => {e}"
        )

        return []

# ==========================================================
# MASTER FUNCTION
# IMPORTANT:
# KEEP THIS EXACT NAME
# ==========================================================

async def scrape_google_reviews(

    place_id: str,

    company_id: int,

    target_limit: int = 100

):

    logger.info(
        f"🚀 SCRAPE STARTED => {place_id}"
    )

    try:

        existing_ids = await load_existing_review_ids(
            company_id
        )

        logger.info(
            f"✅ EXISTING IDS => {len(existing_ids)}"
        )

        # ==================================================
        # LAYER 1 — CRAWL4AI
        # ==================================================

        reviews = await crawl4ai_scraper(

            place_id,
            target_limit
        )

        # ==================================================
        # LAYER 2 — PLAYWRIGHT
        # ==================================================

        if len(reviews) < 5:

            logger.warning(
                "⚠️ PLAYWRIGHT FALLBACK"
            )

            reviews = await playwright_scraper(

                place_id,
                target_limit
            )

        # ==================================================
        # LAYER 3 — SUPERAPI
        # ==================================================

        if len(reviews) < 5:

            logger.warning(
                "⚠️ SUPERAPI FALLBACK"
            )

            reviews = await superapi_scraper(

                place_id,
                target_limit
            )

        # ==================================================
        # FILTER DUPLICATES
        # ==================================================

        final_reviews = []

        seen = set()

        for review in reviews:

            review_id = review.get(
                "review_id"
            )

            if not review_id:
                continue

            if review_id in seen:
                continue

            if review_id in existing_ids:
                continue

            seen.add(review_id)

            final_reviews.append(review)

            await save_review_id(

                company_id,
                review_id
            )

        logger.info(
            f"✅ FINAL REVIEWS => {len(final_reviews)}"
        )

        return final_reviews

    except Exception as e:

        logger.exception(
            f"❌ scrape_google_reviews => {e}"
        )

        traceback.print_exc()

        return []
