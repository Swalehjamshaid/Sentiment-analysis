# =========================================================
# FILE: app/services/scraper.py
# TRUSTLYTICS AI - ENTERPRISE MULTI-LAYER GOOGLE SCRAPER
# HUMAN-LIKE + MULTI PROVIDER + FRONTEND SAFE VERSION
# =========================================================
from __future__ import annotations
print("🔥 SCRAPER.PY LOADED")
# =========================================================
# STANDARD LIBRARIES
# =========================================================
import os
import re
import json
import time
import random
import asyncio
import hashlib
import traceback
import logging
from datetime import datetime
from typing import (
    List,
    Dict,
    Any,
    Optional
)
print("✅ STANDARD LIBRARIES IMPORTED")
# =========================================================
# REQUESTS
# =========================================================
import requests
print("✅ REQUESTS IMPORTED")
# =========================================================
# CURL CFFI
# =========================================================
CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
    print("✅ CURL_CFFI IMPORTED")
except Exception as e:
    print(f"❌ CURL_CFFI IMPORT ERROR => {e}")
# =========================================================
# TENACITY
# =========================================================
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential
)
print("✅ TENACITY IMPORTED")
# =========================================================
# BACKOFF
# =========================================================
import backoff
print("✅ BACKOFF IMPORTED")
# =========================================================
# BS4
# =========================================================
BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
    print("✅ BS4 IMPORTED")
except Exception as e:
    print(f"❌ BS4 IMPORT ERROR => {e}")
# =========================================================
# SELECTOLAX
# =========================================================
SELECTOLAX_AVAILABLE = False
try:
    from selectolax.parser import HTMLParser
    SELECTOLAX_AVAILABLE = True
    print("✅ SELECTOLAX IMPORTED")
except Exception as e:
    print(f"❌ SELECTOLAX IMPORT ERROR => {e}")
# =========================================================
# LXML
# =========================================================
LXML_AVAILABLE = False
try:
    from lxml import html
    LXML_AVAILABLE = True
    print("✅ LXML IMPORTED")
except Exception as e:
    print(f"❌ LXML IMPORT ERROR => {e}")
# =========================================================
# PLAYWRIGHT
# =========================================================
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import (
        async_playwright
    )
    PLAYWRIGHT_AVAILABLE = True
    print("✅ PLAYWRIGHT IMPORTED")
except Exception as e:
    print(f"❌ PLAYWRIGHT IMPORT ERROR => {e}")
# =========================================================
# PLAYWRIGHT STEALTH
# =========================================================
STEALTH_AVAILABLE = False
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
    print("✅ PLAYWRIGHT STEALTH IMPORTED")
except Exception as e:
    print(f"❌ PLAYWRIGHT STEALTH IMPORT ERROR => {e}")
# =========================================================
# FAKE USER AGENT
# =========================================================
FAKE_UA_AVAILABLE = False
try:
    from fake_useragent import UserAgent
    fake_ua = UserAgent()
    FAKE_UA_AVAILABLE = True
    print("✅ FAKE USER AGENT IMPORTED")
except Exception as e:
    print(f"❌ FAKE USER AGENT ERROR => {e}")
    fake_ua = None
# =========================================================
# CRAWL4AI
# =========================================================
CRAWL4AI_AVAILABLE = False
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
    print("✅ CRAWL4AI IMPORTED")
except Exception as e:
    print(f"❌ CRAWL4AI IMPORT ERROR => {e}")
# =========================================================
# REDIS CACHE
# =========================================================
CACHE_AVAILABLE = False
try:
    from cachetools import TTLCache
    provider_cache = TTLCache(
        maxsize=500,
        ttl=3600
    )
    CACHE_AVAILABLE = True
    print("✅ CACHE IMPORTED")
except Exception as e:
    print(f"❌ CACHE IMPORT ERROR => {e}")
# =========================================================
# LOGGER
# =========================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
print("✅ LOGGER READY")
# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================
SERPAPI_KEY = os.getenv(
    "SERPAPI_KEY",
    ""
).strip()
PROXY_USERNAME = os.getenv(
    "PROXY_USERNAME",
    ""
).strip()
PROXY_PASSWORD = os.getenv(
    "PROXY_PASSWORD",
    ""
).strip()
PROXY_SERVER = os.getenv(
    "PROXY_SERVER",
    ""
).strip()
SCRAPER_TIMEOUT = int(
    os.getenv(
        "SCRAPER_TIMEOUT",
        "300"
    )
)
MAX_REVIEWS = int(
    os.getenv(
        "SCRAPER_MAX_REVIEWS",
        "100"
    )
)
ENABLE_SERPAPI = os.getenv(
    "ENABLE_SERPAPI_SCRAPER",
    "true"
).lower() == "true"
ENABLE_PLAYWRIGHT = os.getenv(
    "ENABLE_PLAYWRIGHT_FALLBACK",
    "true"
).lower() == "true"
ENABLE_CURL_CFFI = True
ENABLE_CRAWL4AI = True
print("✅ ENVIRONMENT VARIABLES LOADED")
# =========================================================
# PROXY POOL
# =========================================================
PROXY_POOL = [
    {
        "server":
            f"http://{PROXY_SERVER}",
        "username":
            PROXY_USERNAME,
        "password":
            PROXY_PASSWORD
    }
] if PROXY_SERVER else []
print("✅ PROXY POOL READY")
# =========================================================
# HELPERS
# =========================================================
def utc_now():
    return datetime.utcnow()
# =========================================================
# FRONTEND SAFE RESPONSE
# =========================================================
def build_response(
    success: bool,
    reviews: Optional[List[Dict]] = None,
    errors: Optional[List[str]] = None,
    provider_results: Optional[Dict] = None
):
    reviews = reviews or []
    errors = errors or []
    provider_results = provider_results or {}
    return {
        "success": success,
        "reviews": reviews,
        "total_reviews": len(reviews),
        "provider_results": provider_results,
        "errors": errors,
        "timestamp": utc_now().isoformat()
    }
# =========================================================
# USER AGENT
# =========================================================
def get_user_agent():
    if FAKE_UA_AVAILABLE and fake_ua:
        try:
            return fake_ua.random
        except Exception:
            pass
    return (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
# =========================================================
# RANDOM HUMAN DELAY
# =========================================================
async def human_delay():
    await asyncio.sleep(
        random.uniform(2, 8)
    )
# =========================================================
# MAPS URL
# =========================================================
def maps_url(
    place_id: str
):
    return (
        "https://www.google.com/maps/place/"
        f"?q=place_id:{place_id}"
    )
# =========================================================
# REVIEW ID
# =========================================================
def generate_review_id(
    place_id: str,
    author: str,
    text: str
):
    raw = f"{place_id}_{author}_{text}"
    return hashlib.sha256(
        raw.encode()
    ).hexdigest()
# =========================================================
# NORMALIZER
# =========================================================
def normalize_review(
    review: Dict[str, Any],
    place_id: str
):
    review_text = str(
        review.get(
            "review_text",
            review.get(
                "text",
                review.get(
                    "content",
                    ""
                )
            )
        )
    ).strip()
    if not review_text:
        return None
    author = str(
        review.get(
            "author",
            "Anonymous"
        )
    ).strip()
    rating = int(
        review.get(
            "rating",
            5
        ) or 5
    )
    return {
        "google_review_id":
            generate_review_id(
                place_id,
                author,
                review_text
            ),
        "author":
            author,
        "author_name":
            author,
        "rating":
            rating,
        "review_text":
            review_text,
        "content":
            review_text,
        "text":
            review_text,
        "sentiment_score":
            0.50,
        "google_review_time":
            utc_now(),
        "scraped_at":
            utc_now()
    }
# =========================================================
# DEDUPLICATION
# =========================================================
def deduplicate_reviews(
    reviews: List[Dict]
):
    unique_reviews = []
    seen = set()
    for review in reviews:
        review_id = review.get(
            "google_review_id",
            ""
        )
        if review_id in seen:
            continue
        seen.add(review_id)
        unique_reviews.append(review)
    return unique_reviews
# =========================================================
# SERPAPI PROVIDER - 5+ RETRIES
# =========================================================
@retry(
    stop=stop_after_attempt(7),
    wait=wait_random_exponential(min=3, max=25),
    reraise=True
)
def serpapi_reviews(
    place_id: str
):
    print("🔥 SERPAPI STARTED")
    reviews = []
    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_maps_reviews",
                "place_id": place_id,
                "api_key": SERPAPI_KEY,
                "hl": "en"
            },
            timeout=SCRAPER_TIMEOUT
        )
        print(f"🔥 SERPAPI STATUS => {response.status_code}")
        data = response.json()
        raw_reviews = data.get("reviews", [])
        print(f"🔥 SERPAPI RAW REVIEWS => {len(raw_reviews)}")
        for item in raw_reviews:
            normalized = normalize_review({
                "author": item.get("user", "Google User"),
                "rating": item.get("rating", 5),
                "review_text": item.get("snippet", "")
            }, place_id)
            if normalized:
                reviews.append(normalized)
    except Exception as e:
        print(f"❌ SERPAPI ERROR => {e}")
    print(f"✅ SERPAPI REVIEWS => {len(reviews)}")
    return reviews
# =========================================================
# CURL CFFI PROVIDER - 5+ RETRIES
# =========================================================
@retry(
    stop=stop_after_attempt(6),
    wait=wait_random_exponential(min=2, max=18),
    reraise=True
)
async def curl_cffi_reviews(
    place_id: str
):
    print("🔥 CURL_CFFI STARTED")
    reviews = []
    if not CURL_CFFI_AVAILABLE:
        return reviews
    try:
        response = curl_requests.get(
            maps_url(place_id),
            impersonate="chrome124",
            timeout=90
        )
        print(f"🔥 CURL_CFFI STATUS => {response.status_code}")
        html_content = response.text
        print(f"🔥 CURL HTML LENGTH => {len(html_content)}")
        
        if SELECTOLAX_AVAILABLE:
            tree = HTMLParser(html_content)
            nodes = tree.css("div.jftiEf, .wiI7pd")
            for node in nodes:
                normalized = normalize_review({
                    "author": "Google User",
                    "rating": 5,
                    "review_text": node.text()
                }, place_id)
                if normalized:
                    reviews.append(normalized)
    except Exception as e:
        print(f"❌ CURL_CFFI ERROR => {e}")
    print(f"✅ CURL_CFFI REVIEWS => {len(reviews)}")
    return reviews
# =========================================================
# PLAYWRIGHT PROVIDER - 5+ RETRIES
# =========================================================
@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=7,
    max_time=300
)
async def playwright_reviews(
    place_id: str
):
    print("🔥 PLAYWRIGHT STARTED")
    reviews = []
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ PLAYWRIGHT NOT AVAILABLE")
        return reviews
    browser = None
    try:
        proxy = random.choice(PROXY_POOL) if PROXY_POOL else None
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1920,1080"
                ]
            )
            print("✅ CHROMIUM STARTED")
            context = await browser.new_context(
                user_agent=get_user_agent(),
                locale="en-US",
                viewport={"width": random.randint(1300, 1920), "height": random.randint(800, 1080)}
            )
            page = await context.new_page()
            if STEALTH_AVAILABLE:
                await stealth_async(page)
                print("✅ STEALTH ENABLED")
            await human_delay()
            await page.goto(
                maps_url(place_id),
                wait_until="domcontentloaded",
                timeout=180000
            )
            print(f"🔥 PAGE URL => {page.url}")
            await human_delay()
            # Enhanced human-like scrolling
            for _ in range(45):
                scroll = random.randint(1800, 4500)
                await page.mouse.wheel(0, scroll)
                await human_delay()
            html_content = await page.content()
            print(f"🔥 HTML LENGTH => {len(html_content)}")
            # Multiple parsers + better selectors
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html_content, "html.parser")
                blocks = soup.select("div.jftiEf, div[data-review-id], .MyEned")
                print(f"🔥 BS4 BLOCKS => {len(blocks)}")
                for block in blocks:
                    try:
                        author_el = block.select_one(".d4r55, .fontTitleMedium")
                        text_el = block.select_one(".wiI7pd, .fontBodyMedium")
                        rating_el = block.select_one("span.kvMYJc")
                        author = author_el.text.strip() if author_el else "Anonymous"
                        text = text_el.text.strip() if text_el else ""
                        rating = 5
                        if rating_el and rating_el.get("aria-label"):
                            match = re.search(r"(\d)", rating_el["aria-label"])
                            if match:
                                rating = int(match.group(1))
                        normalized = normalize_review({
                            "author": author,
                            "rating": rating,
                            "review_text": text
                        }, place_id)
                        if normalized:
                            reviews.append(normalized)
                    except Exception:
                        continue
    except Exception as e:
        print(f"❌ PLAYWRIGHT ERROR => {e}")
    finally:
        if browser:
            await browser.close()
            print("✅ BROWSER CLOSED")
    print(f"✅ PLAYWRIGHT REVIEWS => {len(reviews)}")
    return reviews
# =========================================================
# CRAWL4AI PROVIDER - 5+ RETRIES
# =========================================================
@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=6,
    max_time=180
)
async def crawl4ai_reviews(
    place_id: str
):
    print("🔥 CRAWL4AI STARTED")
    reviews = []
    if not CRAWL4AI_AVAILABLE:
        return reviews
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=maps_url(place_id))
            print(f"🔥 CRAWL4AI RESULT => {result.success if hasattr(result, 'success') else 'Done'}")
            if BS4_AVAILABLE and hasattr(result, 'html'):
                soup = BeautifulSoup(result.html, "html.parser")
                blocks = soup.select("div.jftiEf, .wiI7pd")
                for block in blocks:
                    normalized = normalize_review({
                        "author": "Google User",
                        "rating": 5,
                        "review_text": block.get_text(strip=True)
                    }, place_id)
                    if normalized:
                        reviews.append(normalized)
    except Exception as e:
        print(f"❌ CRAWL4AI ERROR => {e}")
    print(f"✅ CRAWL4AI REVIEWS => {len(reviews)}")
    return reviews
# =========================================================
# MASTER SCRAPER
# =========================================================
async def scrape_google_reviews(
    place_id: str
):
    print(f"🔥 MASTER SCRAPER STARTED => {place_id}")
    if not place_id:
        return build_response(
            success=False,
            reviews=[],
            errors=["Invalid Place ID"]
        )
    all_reviews = []
    provider_results = {}
    errors = []
    providers = [
        ("serpapi", lambda: asyncio.to_thread(serpapi_reviews, place_id)),
        ("curl_cffi", lambda: curl_cffi_reviews(place_id)),
        ("playwright", lambda: playwright_reviews(place_id)),
        ("crawl4ai", lambda: crawl4ai_reviews(place_id))
    ]
    for provider_name, provider in providers:
        try:
            print(f"🔥 PROVIDER START => {provider_name}")
            result = await provider()
            provider_results[provider_name] = len(result)
            if result:
                all_reviews.extend(result)
            print(f"✅ PROVIDER SUCCESS => {provider_name}")
            print(f"🔥 TOTAL REVIEWS NOW => {len(all_reviews)}")
            if len(all_reviews) >= MAX_REVIEWS:
                break
        except Exception as provider_error:
            error_message = f"{provider_name}: {str(provider_error)}"
            errors.append(error_message)
            print(f"❌ PROVIDER FAILED => {error_message}")
    all_reviews = deduplicate_reviews(all_reviews)
    all_reviews = all_reviews[:MAX_REVIEWS]
    print(f"✅ FINAL UNIQUE REVIEWS => {len(all_reviews)}")
    return build_response(
        success=len(all_reviews) > 0,
        reviews=all_reviews,
        errors=errors,
        provider_results=provider_results
    )
# =========================================================
# ALIAS
# =========================================================
async def run_scraper(
    place_id: str
):
    return await scrape_google_reviews(place_id)
# =========================================================
# FINAL LOADED
# =========================================================
print("✅ SCRAPER.PY FULLY LOADED")
