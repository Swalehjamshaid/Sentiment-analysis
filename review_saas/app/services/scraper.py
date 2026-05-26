# =========================================================
# FILE: app/scraper.py
# TRUSTLYTICS AI - ULTRA ENTERPRISE GOOGLE REVIEW SCRAPER
# =========================================================

from __future__ import annotations

import os
import re
import json
import time
import asyncio
import logging
import traceback
import random
import hashlib

from datetime import datetime
from typing import List, Dict, Any

# =========================================================
# RETRY LIBRARIES
# =========================================================

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential
)

import backoff

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

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
        "120"
    )
)

MAX_REVIEWS = int(
    os.getenv(
        "SCRAPER_MAX_REVIEWS",
        "100"
    )
)

MAX_RETRIES = int(
    os.getenv(
        "SCRAPER_MAX_RETRIES",
        "5"
    )
)

MAX_PROVIDER_RUNTIME = int(
    os.getenv(
        "SCRAPER_PROVIDER_RUNTIME",
        "60"
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

ENABLE_CURL = os.getenv(
    "ENABLE_CURL_SCRAPER",
    "true"
).lower() == "true"

ENABLE_CRAWL4AI = os.getenv(
    "ENABLE_CRAWL4AI_SCRAPER",
    "true"
).lower() == "true"

# =========================================================
# PROXY
# =========================================================

PROXY_URL = ""

if (
    PROXY_USERNAME and
    PROXY_PASSWORD and
    PROXY_SERVER
):

    PROXY_URL = (
        f"http://{PROXY_USERNAME}:"
        f"{PROXY_PASSWORD}@"
        f"{PROXY_SERVER}"
    )

# =========================================================
# OPTIONAL IMPORTS
# =========================================================

REQUESTS_AVAILABLE = False
PLAYWRIGHT_AVAILABLE = False
STEALTH_AVAILABLE = False
BS4_AVAILABLE = False
SELECTOLAX_AVAILABLE = False
CURL_AVAILABLE = False
CRAWL4AI_AVAILABLE = False
FAKE_UA_AVAILABLE = False

# =========================================================
# REQUESTS
# =========================================================

try:

    import requests

    REQUESTS_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"requests unavailable => {e}"
    )

# =========================================================
# BEAUTIFULSOUP
# =========================================================

try:

    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"BeautifulSoup unavailable => {e}"
    )

# =========================================================
# SELECTOLAX
# =========================================================

try:

    from selectolax.parser import HTMLParser

    SELECTOLAX_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"selectolax unavailable => {e}"
    )

# =========================================================
# PLAYWRIGHT
# =========================================================

try:

    from playwright.async_api import (
        async_playwright
    )

    PLAYWRIGHT_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"playwright unavailable => {e}"
    )

# =========================================================
# PLAYWRIGHT STEALTH
# =========================================================

try:

    from playwright_stealth import stealth_async

    STEALTH_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"playwright stealth unavailable => {e}"
    )

# =========================================================
# CURL_CFFI
# =========================================================

try:

    from curl_cffi.requests import (
        Session as CurlSession
    )

    CURL_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"curl_cffi unavailable => {e}"
    )

# =========================================================
# CRAWL4AI
# =========================================================

try:

    from crawl4ai import AsyncWebCrawler

    CRAWL4AI_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"crawl4ai unavailable => {e}"
    )

# =========================================================
# FAKE USER AGENT
# =========================================================

try:

    from fake_useragent import UserAgent

    fake_ua = UserAgent()

    FAKE_UA_AVAILABLE = True

except Exception as e:

    logger.warning(
        f"fake-useragent unavailable => {e}"
    )

    fake_ua = None

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
    minimum=1,
    maximum=3
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
# EMPTY RESULT RETRY VALIDATOR
# =========================================================

def validate_reviews_result(
    reviews,
    provider_name="UNKNOWN"
):

    if not reviews:

        raise Exception(
            f"{provider_name} returned 0 reviews"
        )

    return reviews

# =========================================================
# SIMPLE SENTIMENT
# =========================================================

def simple_sentiment(
    text: str
):

    text = str(text).lower()

    positive_words = [
        "good",
        "great",
        "excellent",
        "awesome",
        "love",
        "perfect",
    ]

    negative_words = [
        "bad",
        "terrible",
        "worst",
        "awful",
        "poor",
    ]

    positive = sum(
        1 for word in positive_words
        if word in text
    )

    negative = sum(
        1 for word in negative_words
        if word in text
    )

    if positive > negative:

        return "positive"

    if negative > positive:

        return "negative"

    return "neutral"

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

    sentiment = simple_sentiment(
        review_text
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

        "sentiment":
            sentiment,

        "sentiment_score":
            0.85 if sentiment == "positive"
            else 0.15 if sentiment == "negative"
            else 0.50,

        "source":
            review.get(
                "source",
                "Google"
            ),

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
# SERPAPI
# =========================================================

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_random_exponential(
        min=2,
        max=15
    ),
    reraise=True
)
def serpapi_reviews(
    place_id: str
):

    logger.info(
        "🚀 SERPAPI STARTED"
    )

    reviews = []

    if not ENABLE_SERPAPI:

        return reviews

    if not SERPAPI_KEY:

        logger.warning(
            "❌ SERPAPI KEY MISSING"
        )

        return reviews

    try:

        params = {

            "engine":
                "google_maps_reviews",

            "place_id":
                place_id,

            "api_key":
                SERPAPI_KEY,

            "hl":
                "en"
        }

        response = requests.get(

            "https://serpapi.com/search.json",

            params=params,

            proxies={

                "http":
                    PROXY_URL,

                "https":
                    PROXY_URL

            } if PROXY_URL else None,

            headers={

                "User-Agent":
                    get_user_agent()
            },

            timeout=SCRAPER_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        raw_reviews = data.get(
            "reviews",
            []
        )

        logger.info(
            f"SERPAPI RAW REVIEWS => {len(raw_reviews)}"
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
                    ),

                "source":
                    "SERPAPI"

            }, place_id)

            if review:

                reviews.append(review)

        validate_reviews_result(
            reviews,
            "SERPAPI"
        )

    except Exception as e:

        logger.error(
            f"❌ SERPAPI ERROR => {e}"
        )

        raise

    logger.info(
        f"✅ SERPAPI REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# PLAYWRIGHT
# =========================================================

@backoff.on_exception(

    backoff.expo,

    Exception,

    max_time=MAX_PROVIDER_RUNTIME
)
async def playwright_reviews(
    place_id: str
):

    logger.info(
        "🚀 PLAYWRIGHT STARTED"
    )

    reviews = []

    if not ENABLE_PLAYWRIGHT:

        return reviews

    if not PLAYWRIGHT_AVAILABLE:

        return reviews

    browser = None

    for attempt in range(3):

        try:

            logger.info(
                f"PLAYWRIGHT ATTEMPT => {attempt + 1}"
            )

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

                        "--disable-extensions",

                        "--disable-background-networking",

                        "--single-process",

                        "--window-size=1920,1080"
                    ]
                )

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

                await page.goto(

                    maps_url(place_id),

                    wait_until="domcontentloaded",

                    timeout=120000
                )

                logger.info(
                    "⌛ WAITING FOR GOOGLE REVIEWS"
                )

                await human_delay(8, 15)

                selectors = [

                    'button[jsaction*="pane.reviewChart.moreReviews"]',

                    'button[aria-label*="reviews"]',

                    'button[aria-label*="Reviews"]'
                ]

                for selector in selectors:

                    try:

                        button = page.locator(
                            selector
                        ).first

                        await button.click()

                        logger.info(
                            f"✅ CLICKED => {selector}"
                        )

                        break

                    except Exception:

                        pass

                start_time = time.time()

                last_review_count = 0

                stable_rounds = 0

                all_review_blocks = []

                while True:

                    elapsed = time.time() - start_time

                    if elapsed > 60:

                        logger.info(
                            "⏰ MAX SCROLL TIME REACHED"
                        )

                        break

                    scroll_amount = random.randint(
                        4000,
                        12000
                    )

                    await page.mouse.wheel(
                        0,
                        scroll_amount
                    )

                    logger.info(
                        f"🖱️ SCROLL => {scroll_amount}"
                    )

                    await human_delay(
                        2,
                        5
                    )

                    html = await page.content()

                    soup = BeautifulSoup(
                        html,
                        "html.parser"
                    )

                    selectors = [

                        "div.jftiEf",

                        "div[data-review-id]",

                        ".wiI7pd",

                        ".MyEned",

                        "div.section-review-content",

                        "div.review-dialog-list"
                    ]

                    current_blocks = []

                    for selector in selectors:

                        try:

                            blocks = soup.select(
                                selector
                            )

                            if blocks:

                                logger.info(
                                    f"✅ SELECTOR => {selector}"
                                )

                                current_blocks.extend(
                                    blocks
                                )

                        except Exception as selector_error:

                            logger.warning(
                                f"⚠️ SELECTOR ERROR => {selector_error}"
                            )

                    unique_html = set()

                    deduped_blocks = []

                    for block in current_blocks:

                        block_html = str(block)

                        if block_html in unique_html:

                            continue

                        unique_html.add(block_html)

                        deduped_blocks.append(block)

                    current_count = len(
                        deduped_blocks
                    )

                    logger.info(
                        f"📊 LIVE REVIEW BLOCKS => {current_count}"
                    )

                    if current_count == last_review_count:

                        stable_rounds += 1

                        logger.info(
                            f"⚠️ NO NEW REVIEWS => {stable_rounds}"
                        )

                    else:

                        stable_rounds = 0

                    last_review_count = current_count

                    all_review_blocks = deduped_blocks

                    if stable_rounds >= 5:

                        logger.info(
                            "🛑 NO MORE REVIEWS LOADING"
                        )

                        break

                    if current_count >= MAX_REVIEWS:

                        logger.info(
                            f"🎯 TARGET REACHED => {current_count}"
                        )

                        break

                review_blocks = all_review_blocks

                logger.info(
                    f"✅ FINAL PLAYWRIGHT BLOCKS => {len(review_blocks)}"
                )

                for block in review_blocks:

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
                                review_text,

                            "source":
                                "PLAYWRIGHT"

                        }, place_id)

                        if review:

                            reviews.append(review)

                    except Exception as parse_error:

                        logger.error(
                            f"❌ PLAYWRIGHT PARSE ERROR => {parse_error}"
                        )

                validate_reviews_result(
                    reviews,
                    "PLAYWRIGHT"
                )

                await browser.close()

                break

        except Exception as e:

            logger.error(
                f"❌ PLAYWRIGHT ERROR => {e}"
            )

            logger.error(
                traceback.format_exc()
            )

            await human_delay(10, 20)

            try:

                if browser:

                    await browser.close()

            except Exception:

                pass

    logger.info(
        f"✅ PLAYWRIGHT REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# MASTER SCRAPER
# =========================================================

async def scrape_google_reviews(
    place_id: str
):

    logger.info(
        f"🚀 MASTER SCRAPER STARTED => {place_id}"
    )

    if not place_id:

        logger.error(
            "❌ INVALID PLACE ID"
        )

        return []

    all_reviews = []

    try:

        tasks = []

        if ENABLE_SERPAPI:

            tasks.append(
                asyncio.to_thread(
                    serpapi_reviews,
                    place_id
                )
            )

        if ENABLE_PLAYWRIGHT:

            tasks.append(
                playwright_reviews(
                    place_id
                )
            )

        results = await asyncio.gather(

            *tasks,

            return_exceptions=True
        )

        logger.info(
            f"PROVIDER RESULTS => {results}"
        )

        for result in results:

            if isinstance(result, Exception):

                logger.error(
                    f"❌ PROVIDER FAILED => {result}"
                )

                continue

            if not result:

                continue

            all_reviews.extend(result)

        all_reviews = deduplicate_reviews(
            all_reviews
        )

        if MAX_REVIEWS > 0:

            all_reviews = all_reviews[:MAX_REVIEWS]

        logger.info(
            f"✅ FINAL UNIQUE REVIEWS => {len(all_reviews)}"
        )

        return all_reviews

    except Exception as e:

        logger.error(
            f"❌ MASTER SCRAPER ERROR => {e}"
        )

        logger.error(
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
# TEST
# =========================================================

if __name__ == "__main__":

    async def main():

        place_id = (
            "ChIJN1t_tDeuEmsRUsoyG83frY4"
        )

        reviews = await scrape_google_reviews(
            place_id
        )

        print(
            json.dumps(
                reviews[:5],
                indent=4,
                default=str
            )
        )

    asyncio.run(main())
