# =========================================================
# FILE: app/services/scraper.py
# TRUSTLYTICS AI - NEXT GEN ENTERPRISE SCRAPER
# MODERN • RESILIENT • MULTI-LAYER • PROXY SAFE
# FULLY ALIGNED WITH review.py
# =========================================================

from __future__ import annotations

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
import logging
import traceback

from datetime import datetime
from typing import (
    Dict,
    List,
    Any,
    Optional
)

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

print("🔥 NEXT GEN SCRAPER BOOTING")

# =========================================================
# REQUESTS
# =========================================================

import requests

# =========================================================
# CURL CFFI
# =========================================================

CURL_CFFI_AVAILABLE = False

try:

    from curl_cffi import requests as curl_requests

    CURL_CFFI_AVAILABLE = True

    logger.info("✅ CURL_CFFI READY")

except Exception as e:

    logger.error(f"❌ CURL_CFFI ERROR => {e}")

# =========================================================
# TENACITY
# =========================================================

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential
)

# =========================================================
# BACKOFF
# =========================================================

import backoff

# =========================================================
# SELECTOLAX
# =========================================================

SELECTOLAX_AVAILABLE = False

try:

    from selectolax.parser import HTMLParser

    SELECTOLAX_AVAILABLE = True

    logger.info("✅ SELECTOLAX READY")

except Exception as e:

    logger.error(f"❌ SELECTOLAX ERROR => {e}")

# =========================================================
# BS4 FALLBACK
# =========================================================

BS4_AVAILABLE = False

try:

    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True

    logger.info("✅ BS4 READY")

except Exception as e:

    logger.error(f"❌ BS4 ERROR => {e}")

# =========================================================
# PLAYWRIGHT
# =========================================================

PLAYWRIGHT_AVAILABLE = False

try:

    from playwright.async_api import (
        async_playwright,
        TimeoutError as PlaywrightTimeoutError
    )

    PLAYWRIGHT_AVAILABLE = True

    logger.info("✅ PLAYWRIGHT READY")

except Exception as e:

    logger.error(f"❌ PLAYWRIGHT ERROR => {e}")

# =========================================================
# PLAYWRIGHT STEALTH
# =========================================================

STEALTH_AVAILABLE = False

try:

    from playwright_stealth import stealth_async

    STEALTH_AVAILABLE = True

    logger.info("✅ STEALTH READY")

except Exception as e:

    logger.error(f"❌ STEALTH ERROR => {e}")

# =========================================================
# FAKE USER AGENT
# =========================================================

FAKE_UA_AVAILABLE = False

try:

    from fake_useragent import UserAgent

    fake_ua = UserAgent()

    FAKE_UA_AVAILABLE = True

    logger.info("✅ FAKE UA READY")

except Exception as e:

    logger.error(f"❌ FAKE UA ERROR => {e}")

    fake_ua = None

# =========================================================
# CACHE
# =========================================================

from cachetools import TTLCache

review_cache = TTLCache(
    maxsize=1000,
    ttl=3600
)

# =========================================================
# ENVIRONMENT
# =========================================================

SERPAPI_KEY = os.getenv(
    "SERPAPI_KEY",
    ""
).strip()

SCRAPER_TIMEOUT = int(
    os.getenv(
        "SCRAPER_TIMEOUT",
        "180"
    )
)

MAX_REVIEWS = int(
    os.getenv(
        "SCRAPER_MAX_REVIEWS",
        "100"
    )
)

HEADLESS_MODE = os.getenv(
    "SCRAPER_HEADLESS",
    "true"
).lower() == "true"

# =========================================================
# PROXIES
# =========================================================

PROXY_SERVER = os.getenv(
    "PROXY_SERVER",
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

PROXY_POOL = []

FAILED_PROXIES = set()

if PROXY_SERVER:

    PROXY_POOL.append({

        "server":
            f"http://{PROXY_SERVER}",

        "username":
            PROXY_USERNAME,

        "password":
            PROXY_PASSWORD
    })

logger.info(
    f"✅ PROXY COUNT => {len(PROXY_POOL)}"
)

# =========================================================
# CONCURRENCY CONTROL
# =========================================================

SCRAPER_SEMAPHORE = asyncio.Semaphore(2)

# =========================================================
# HELPERS
# =========================================================

def utc_now():

    return datetime.utcnow()


def maps_url(
    place_id: str
):

    return (
        "https://www.google.com/maps/place/"
        f"?q=place_id:{place_id}"
    )


def get_user_agent():

    static_agents = [

        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),

        (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),

        (
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    ]

    if FAKE_UA_AVAILABLE and fake_ua:

        try:

            return fake_ua.random

        except Exception:
            pass

    return random.choice(
        static_agents
    )


def get_proxy():

    try:

        available = [

            p for p in PROXY_POOL
            if p["server"] not in FAILED_PROXIES
        ]

        if not available:

            return None

        return random.choice(
            available
        )

    except Exception:

        return None


async def human_delay(
    minimum=1,
    maximum=4
):

    await asyncio.sleep(
        random.uniform(
            minimum,
            maximum
        )
    )

# =========================================================
# REVIEW ID
# =========================================================

def generate_review_id(
    place_id: str,
    author: str,
    text: str
):

    raw = f"{place_id}:{author}:{text}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

# =========================================================
# NORMALIZATION
# =========================================================

def normalize_review(
    review: Dict[str, Any],
    place_id: str
):

    try:

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

                review.get(
                    "author_name",
                    "Anonymous"
                )
            )

        ).strip()

        if not author:

            author = "Anonymous"

        rating = review.get(
            "rating",
            5
        )

        try:

            rating = int(float(rating))

        except Exception:

            rating = 5

        rating = max(
            1,
            min(rating, 5)
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
                0.5,

            "google_review_time":
                utc_now(),

            "scraped_at":
                utc_now()
        }

    except Exception as e:

        logger.error(
            f"❌ NORMALIZE ERROR => {e}"
        )

        return None

# =========================================================
# DEDUPLICATION
# =========================================================

def deduplicate_reviews(
    reviews: List[Dict]
):

    seen = set()

    unique_reviews = []

    for review in reviews:

        review_id = review.get(
            "google_review_id",
            ""
        )

        if not review_id:
            continue

        if review_id in seen:
            continue

        seen.add(review_id)

        unique_reviews.append(
            review
        )

    return unique_reviews

# =========================================================
# CAPTCHA DETECTION
# =========================================================

def detect_captcha(
    html: str
):

    lower = html.lower()

    patterns = [

        "captcha",
        "unusual traffic",
        "sorry",
        "not a robot"
    ]

    return any(
        p in lower
        for p in patterns
    )

# =========================================================
# SERPAPI PROVIDER
# =========================================================

@retry(
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(
        min=2,
        max=20
    ),
    reraise=True
)
def serpapi_reviews(
    place_id: str
):

    reviews = []

    if not SERPAPI_KEY:

        logger.warning(
            "⚠️ SERPAPI KEY MISSING"
        )

        return reviews

    for attempt in range(3):

        try:

            logger.info(
                f"🔥 SERPAPI ATTEMPT => {attempt+1}"
            )

            proxies = None

            proxy = get_proxy()

            if proxy:

                proxy_url = (
                    f"http://"
                    f"{proxy['username']}:"
                    f"{proxy['password']}@"
                    f"{proxy['server'].replace('http://','')}"
                )

                proxies = {

                    "http": proxy_url,
                    "https": proxy_url
                }

            response = requests.get(

                "https://serpapi.com/search.json",

                params={

                    "engine":
                        "google_maps_reviews",

                    "place_id":
                        place_id,

                    "api_key":
                        SERPAPI_KEY,

                    "hl":
                        "en"
                },

                proxies=proxies,

                timeout=SCRAPER_TIMEOUT
            )

            if response.status_code != 200:

                continue

            data = response.json()

            raw_reviews = data.get(
                "reviews",
                []
            )

            if not isinstance(
                raw_reviews,
                list
            ):

                raw_reviews = []

            for item in raw_reviews:

                normalized = normalize_review({

                    "author":
                        item.get(
                            "user",
                            "Google User"
                        ),

                    "rating":
                        item.get(
                            "rating",
                            5
                        ),

                    "review_text":
                        item.get(
                            "snippet",
                            ""
                        )

                }, place_id)

                if normalized:

                    reviews.append(
                        normalized
                    )

            if reviews:

                break

        except Exception as e:

            logger.error(
                f"❌ SERPAPI ERROR => {e}"
            )

            await_sleep = random.uniform(2, 8)

            time.sleep(await_sleep)

    return reviews

# =========================================================
# PLAYWRIGHT PROVIDER
# =========================================================

@backoff.on_exception(
    backoff.expo,
    Exception,
    max_time=300
)
async def playwright_reviews(
    place_id: str
):

    reviews = []

    if not PLAYWRIGHT_AVAILABLE:

        return reviews

    async with SCRAPER_SEMAPHORE:

        browser = None

        for browser_attempt in range(3):

            try:

                proxy = get_proxy()

                async with async_playwright() as p:

                    browser = await p.chromium.launch(

                        headless=HEADLESS_MODE,

                        proxy=proxy,

                        args=[

                            "--disable-blink-features=AutomationControlled",

                            "--no-sandbox",

                            "--disable-dev-shm-usage",

                            "--disable-gpu",

                            "--window-size=1920,1080"
                        ]
                    )

                    context = await browser.new_context(

                        user_agent=get_user_agent(),

                        locale="en-US",

                        viewport={

                            "width":
                                random.randint(
                                    1280,
                                    1920
                                ),

                            "height":
                                random.randint(
                                    720,
                                    1080
                                )
                        }
                    )

                    page = await context.new_page()

                    if STEALTH_AVAILABLE:

                        try:

                            await stealth_async(page)

                        except Exception:
                            pass

                    await page.goto(

                        maps_url(place_id),

                        wait_until="domcontentloaded",

                        timeout=120000
                    )

                    await human_delay(
                        2,
                        5
                    )

                    review_selectors = [

                        'button[jsaction*="pane.reviewChart.moreReviews"]',

                        'button[aria-label*="reviews"]',

                        'button[aria-label*="Reviews"]'
                    ]

                    for selector in review_selectors:

                        try:

                            locator = page.locator(
                                selector
                            ).first

                            if await locator.count() > 0:

                                await locator.click()

                                break

                        except Exception:
                            continue

                    await page.wait_for_timeout(
                        5000
                    )

                    review_panel = page.locator(
                        "div.m6QErb"
                    ).nth(1)

                    previous_count = 0
                    no_growth = 0

                    while no_growth < 3:

                        try:

                            await review_panel.hover()

                            await review_panel.evaluate(
                                "(el) => el.scrollTop += 1500"
                            )

                            await page.mouse.move(

                                random.randint(100, 1200),

                                random.randint(100, 700)
                            )

                            await human_delay(
                                1,
                                3
                            )

                            current_count = await page.locator(
                                "div.jftiEf"
                            ).count()

                            if current_count == previous_count:

                                no_growth += 1

                            else:

                                no_growth = 0

                            previous_count = current_count

                            if current_count >= MAX_REVIEWS:

                                break

                        except Exception:
                            break

                    html = await page.content()

                    if detect_captcha(html):

                        logger.warning(
                            "⚠️ CAPTCHA DETECTED"
                        )

                        raise Exception(
                            "Captcha detected"
                        )

                    review_cards = page.locator(
                        "div.jftiEf"
                    )

                    total_cards = await review_cards.count()

                    total_cards = min(
                        total_cards,
                        MAX_REVIEWS
                    )

                    for index in range(total_cards):

                        try:

                            card = review_cards.nth(index)

                            author = "Anonymous"
                            text = ""
                            rating = 5

                            try:

                                author_locator = card.locator(
                                    ".d4r55"
                                )

                                if await author_locator.count() > 0:

                                    author = (
                                        await author_locator
                                        .inner_text()
                                    ).strip()

                            except Exception:
                                pass

                            try:

                                text_locator = card.locator(
                                    ".wiI7pd"
                                )

                                if await text_locator.count() > 0:

                                    text = (
                                        await text_locator
                                        .inner_text()
                                    ).strip()

                            except Exception:
                                pass

                            try:

                                rating_locator = card.locator(
                                    "span.kvMYJc"
                                )

                                if await rating_locator.count() > 0:

                                    aria = await rating_locator.get_attribute(
                                        "aria-label"
                                    )

                                    if aria:

                                        match = re.search(
                                            r"(\d)",
                                            aria
                                        )

                                        if match:

                                            rating = int(
                                                match.group(1)
                                            )

                            except Exception:
                                pass

                            normalized = normalize_review({

                                "author":
                                    author,

                                "rating":
                                    rating,

                                "review_text":
                                    text

                            }, place_id)

                            if normalized:

                                reviews.append(
                                    normalized
                                )

                        except Exception:
                            continue

                    if reviews:

                        break

            except Exception as e:

                logger.error(
                    f"❌ PLAYWRIGHT ATTEMPT FAILED => {e}"
                )

                await asyncio.sleep(
                    random.uniform(3, 8)
                )

            finally:

                try:

                    if browser:

                        await browser.close()

                except Exception:
                    pass

    return reviews

# =========================================================
# MASTER SCRAPER
# =========================================================

async def scrape_google_reviews(
    place_id: str
):

    logger.info(
        f"🚀 MASTER SCRAPER => {place_id}"
    )

    if not place_id:

        return []

    cache_key = f"reviews:{place_id}"

    try:

        cached = review_cache.get(
            cache_key
        )

        if cached:

            logger.info(
                "⚡ CACHE HIT"
            )

            return cached

    except Exception:
        pass

    all_reviews = []

    providers = [

        (
            "serpapi",
            lambda: asyncio.to_thread(
                serpapi_reviews,
                place_id
            )
        ),

        (
            "playwright",
            lambda: playwright_reviews(
                place_id
            )
        )
    ]

    for provider_name, provider in providers:

        try:

            logger.info(
                f"🔥 PROVIDER => {provider_name}"
            )

            result = await asyncio.wait_for(

                provider(),

                timeout=240
            )

            if not isinstance(
                result,
                list
            ):

                continue

            if result:

                all_reviews.extend(
                    result
                )

            logger.info(
                f"✅ {provider_name} => {len(result)}"
            )

            if len(all_reviews) >= MAX_REVIEWS:

                break

        except Exception as provider_error:

            logger.error(
                f"❌ PROVIDER FAILED => {provider_name}"
            )

            logger.error(
                str(provider_error)
            )

    all_reviews = deduplicate_reviews(
        all_reviews
    )

    all_reviews = all_reviews[:MAX_REVIEWS]

    try:

        review_cache[
            cache_key
        ] = all_reviews

    except Exception:
        pass

    logger.info(
        f"✅ FINAL REVIEWS => {len(all_reviews)}"
    )

    return all_reviews

# =========================================================
# ALIAS
# =========================================================

async def run_scraper(
    place_id: str
):

    return await scrape_google_reviews(
        place_id
    )

# =========================================================
# READY
# =========================================================

logger.info(
    "✅ NEXT GEN ENTERPRISE SCRAPER READY"
)
