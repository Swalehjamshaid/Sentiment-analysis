# =========================================================
# FILE: app/scraper.py
# TRUSTLYTICS AI - ENTERPRISE GOOGLE REVIEW SCRAPER
# FULLY DEBUGGED + FULL VISIBILITY VERSION
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
from typing import List, Dict, Any

print("✅ STANDARD LIBRARIES IMPORTED")

# =========================================================
# REQUESTS
# =========================================================

import requests

print("✅ REQUESTS IMPORTED")

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
        "180"
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

print("✅ ENVIRONMENT VARIABLES LOADED")

# =========================================================
# HELPERS
# =========================================================

def utc_now():

    return datetime.utcnow()

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
# HUMAN DELAY
# =========================================================

async def human_delay(
    minimum=5,
    maximum=10
):

    await asyncio.sleep(
        random.uniform(minimum, maximum)
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
# REVIEW HASH
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
# NORMALIZE REVIEW
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

        return {}

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
            utc_now(),
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
# SERPAPI SCRAPER
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

    print("🔥 SERPAPI STARTED")

    reviews = []

    if not ENABLE_SERPAPI:

        print("⚠️ SERPAPI DISABLED")

        return reviews

    try:

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

            timeout=SCRAPER_TIMEOUT
        )

        print(
            f"🔥 SERPAPI STATUS => {response.status_code}"
        )

        data = response.json()

        raw_reviews = data.get(
            "reviews",
            []
        )

        print(
            f"🔥 SERPAPI RAW REVIEWS => {len(raw_reviews)}"
        )

        for item in raw_reviews:

            review = normalize_review({

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

            if review:

                reviews.append(review)

    except Exception as e:

        print(f"❌ SERPAPI ERROR => {e}")

        print(traceback.format_exc())

    print(
        f"✅ SERPAPI REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# PLAYWRIGHT SCRAPER
# =========================================================

@backoff.on_exception(
    backoff.expo,
    Exception,
    max_time=120
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

        async with async_playwright() as p:

            browser = await p.chromium.launch(

                headless=True,

                proxy={

                    "server":
                        f"http://{PROXY_SERVER}",

                    "username":
                        PROXY_USERNAME,

                    "password":
                        PROXY_PASSWORD
                },

                args=[

                    "--no-sandbox",

                    "--disable-setuid-sandbox",

                    "--disable-dev-shm-usage",

                    "--disable-gpu",

                    "--single-process",

                    "--window-size=1920,1080"
                ]
            )

            print("✅ CHROMIUM STARTED")

            context = await browser.new_context(

                user_agent=get_user_agent(),

                locale="en-US",

                viewport={
                    "width": 1920,
                    "height": 1080
                }
            )

            page = await context.new_page()

            if STEALTH_AVAILABLE:

                await stealth_async(page)

                print("✅ STEALTH ENABLED")

            target_url = maps_url(
                place_id
            )

            print(
                f"🔥 TARGET URL => {target_url}"
            )

            await page.goto(

                target_url,

                wait_until="domcontentloaded",

                timeout=180000
            )

            print(
                f"🔥 PAGE URL => {page.url}"
            )

            await human_delay(
                10,
                20
            )

            review_button_selectors = [

                'button[jsaction*="pane.reviewChart.moreReviews"]',

                'button[aria-label*="reviews"]',

                'button[aria-label*="Reviews"]'
            ]

            clicked = False

            for selector in review_button_selectors:

                try:

                    button = page.locator(
                        selector
                    ).first

                    await button.click()

                    clicked = True

                    print(
                        f"✅ REVIEW BUTTON CLICKED => {selector}"
                    )

                    break

                except Exception:

                    continue

            if not clicked:

                print(
                    "⚠️ REVIEW BUTTON NOT FOUND"
                )

            await human_delay(
                10,
                20
            )

            stable_rounds = 0

            last_review_count = 0

            all_review_blocks = []

            start_time = time.time()

            while True:

                elapsed = time.time() - start_time

                if elapsed > 120:

                    print(
                        "⏰ MAX TIME REACHED"
                    )

                    break

                scroll_amount = random.randint(
                    5000,
                    15000
                )

                await page.mouse.wheel(
                    0,
                    scroll_amount
                )

                print(
                    f"🖱️ SCROLL => {scroll_amount}"
                )

                await human_delay(
                    5,
                    10
                )

                html = await page.content()

                print(
                    f"🔥 HTML LENGTH => {len(html)}"
                )

                soup = BeautifulSoup(
                    html,
                    "html.parser"
                )

                selectors = [

                    "div.jftiEf",

                    "div[data-review-id]",

                    ".wiI7pd",

                    ".MyEned"
                ]

                current_blocks = []

                for selector in selectors:

                    try:

                        blocks = soup.select(
                            selector
                        )

                        if blocks:

                            print(
                                f"✅ SELECTOR WORKED => {selector}"
                            )

                            current_blocks.extend(
                                blocks
                            )

                    except Exception as selector_error:

                        print(
                            f"❌ SELECTOR ERROR => {selector_error}"
                        )

                current_count = len(
                    current_blocks
                )

                print(
                    f"🔥 LIVE REVIEW BLOCKS => {current_count}"
                )

                if current_count == last_review_count:

                    stable_rounds += 1

                else:

                    stable_rounds = 0

                last_review_count = current_count

                all_review_blocks = current_blocks

                if stable_rounds >= 15:

                    print(
                        "🛑 REVIEW COUNT STABLE"
                    )

                    break

                if current_count >= MAX_REVIEWS:

                    print(
                        "🎯 MAX REVIEWS REACHED"
                    )

                    break

            print(
                f"🔥 FINAL BLOCKS => {len(all_review_blocks)}"
            )

            for block in all_review_blocks:

                try:

                    author = "Anonymous"

                    rating = 5

                    review_text = ""

                    author_element = block.select_one(
                        ".d4r55"
                    )

                    if author_element:

                        author = author_element.text.strip()

                    review_element = block.select_one(
                        ".wiI7pd"
                    )

                    if review_element:

                        review_text = review_element.text.strip()

                    rating_element = block.select_one(
                        "span.kvMYJc"
                    )

                    if rating_element:

                        aria = rating_element.get(
                            "aria-label",
                            ""
                        )

                        match = re.search(
                            r"(\d)",
                            aria
                        )

                        if match:

                            rating = int(
                                match.group(1)
                            )

                    review = normalize_review({

                        "author":
                            author,

                        "rating":
                            rating,

                        "review_text":
                            review_text

                    }, place_id)

                    if review:

                        reviews.append(review)

                except Exception as parse_error:

                    print(
                        f"❌ PARSE ERROR => {parse_error}"
                    )

    except Exception as e:

        print(
            f"❌ PLAYWRIGHT ERROR => {e}"
        )

        print(
            traceback.format_exc()
        )

    finally:

        try:

            if browser:

                await browser.close()

                print("✅ BROWSER CLOSED")

        except Exception:

            pass

    print(
        f"✅ PLAYWRIGHT REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# MASTER SCRAPER
# =========================================================

async def scrape_google_reviews(
    place_id: str
):

    print(
        f"🔥 MASTER SCRAPER STARTED => {place_id}"
    )

    if not place_id:

        print("❌ INVALID PLACE ID")

        return []

    all_reviews = []

    try:

        tasks = [

            asyncio.to_thread(
                serpapi_reviews,
                place_id
            ),

            playwright_reviews(
                place_id
            )
        ]

        results = await asyncio.gather(

            *tasks,

            return_exceptions=True
        )

        print(
            f"🔥 PROVIDER RESULTS => {results}"
        )

        for result in results:

            if isinstance(result, Exception):

                print(
                    f"❌ PROVIDER FAILED => {result}"
                )

                continue

            if not result:

                continue

            all_reviews.extend(result)

        all_reviews = deduplicate_reviews(
            all_reviews
        )

        all_reviews = all_reviews[:MAX_REVIEWS]

        print(
            f"✅ FINAL UNIQUE REVIEWS => {len(all_reviews)}"
        )

        return all_reviews

    except Exception as e:

        print(
            f"❌ MASTER SCRAPER ERROR => {e}"
        )

        print(
            traceback.format_exc()
        )

        return []

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
# FINAL LOADED
# =========================================================

print("✅ SCRAPER.PY FULLY LOADED")
