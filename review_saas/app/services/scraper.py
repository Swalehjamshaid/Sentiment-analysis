# =========================================================
# FILE: app/scraper.py
# TRUSTLYTICS AI - ENTERPRISE GOOGLE REVIEW SCRAPER
# =========================================================

from __future__ import annotations

import os
import re
import json
import asyncio
import logging
import traceback
import random
import hashlib

from datetime import datetime
from typing import List, Dict, Any

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
# GOOGLE MAPS URL
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
# SENTIMENT
# =========================================================

def simple_sentiment(
    text: str
):

    text = str(text).lower()

    positive_words = [
        "good",
        "great",
        "excellent",
        "amazing",
        "awesome",
        "love",
        "perfect",
    ]

    negative_words = [
        "bad",
        "terrible",
        "worst",
        "awful",
        "hate",
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

    except Exception as e:

        logger.error(
            f"❌ SERPAPI ERROR => {e}"
        )

    logger.info(
        f"✅ SERPAPI REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# PLAYWRIGHT
# =========================================================

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

        logger.warning(
            "❌ PLAYWRIGHT NOT AVAILABLE"
        )

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

                    "--disable-extensions",

                    "--single-process",

                    "--disable-background-networking",

                    "--window-size=1920,1080"
                ]
            )

            context = await browser.new_context(

                user_agent=get_user_agent(),

                viewport={

                    "width": 1920,

                    "height": 1080
                },

                locale="en-US"
            )

            page = await context.new_page()

            if STEALTH_AVAILABLE:

                await stealth_async(page)

            await page.goto(

                maps_url(place_id),

                timeout=120000,

                wait_until="domcontentloaded"
            )

            await human_delay(5, 8)

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

                    break

                except Exception:

                    pass

            for _ in range(50):

                await page.mouse.wheel(
                    0,
                    10000
                )

                await human_delay(
                    0.5,
                    1
                )

            await human_delay(5, 8)

            html = await page.content()

            soup = BeautifulSoup(
                html,
                "html.parser"
            )

            review_blocks = soup.select(
                "div.jftiEf, div[data-review-id]"
            )

            logger.info(
                f"PLAYWRIGHT BLOCKS => {len(review_blocks)}"
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

            await browser.close()

    except Exception as e:

        logger.error(
            f"❌ PLAYWRIGHT ERROR => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

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
# CURL_CFFI
# =========================================================

def curl_reviews(
    place_id: str
):

    logger.info(
        "🚀 CURL_CFFI STARTED"
    )

    reviews = []

    if not ENABLE_CURL:

        return reviews

    if not CURL_AVAILABLE:

        return reviews

    try:

        session = CurlSession()

        response = session.get(

            maps_url(place_id),

            impersonate="chrome124",

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

        parser = HTMLParser(
            response.text
        )

        nodes = parser.css(
            ".wiI7pd"
        )

        logger.info(
            f"CURL NODES => {len(nodes)}"
        )

        for node in nodes:

            review = normalize_review({

                "author":
                    "Google User",

                "rating":
                    5,

                "review_text":
                    node.text(),

                "source":
                    "CURL_CFFI"

            }, place_id)

            if review:

                reviews.append(review)

    except Exception as e:

        logger.error(
            f"❌ CURL ERROR => {e}"
        )

    logger.info(
        f"✅ CURL REVIEWS => {len(reviews)}"
    )

    return reviews

# =========================================================
# CRAWL4AI
# =========================================================

async def crawl4ai_reviews(
    place_id: str
):

    logger.info(
        "🚀 CRAWL4AI STARTED"
    )

    reviews = []

    if not ENABLE_CRAWL4AI:

        return reviews

    if not CRAWL4AI_AVAILABLE:

        return reviews

    try:

        async with AsyncWebCrawler() as crawler:

            result = await crawler.arun(

                url=maps_url(place_id)
            )

            html = getattr(
                result,
                "html",
                ""
            )

            soup = BeautifulSoup(
                html,
                "html.parser"
            )

            blocks = soup.select(
                ".wiI7pd"
            )

            logger.info(
                f"CRAWL4AI BLOCKS => {len(blocks)}"
            )

            for block in blocks:

                review = normalize_review({

                    "author":
                        "Google User",

                    "rating":
                        5,

                    "review_text":
                        block.text.strip(),

                    "source":
                        "CRAWL4AI"

                }, place_id)

                if review:

                    reviews.append(review)

    except Exception as e:

        logger.error(
            f"❌ CRAWL4AI ERROR => {e}"
        )

    logger.info(
        f"✅ CRAWL4AI REVIEWS => {len(reviews)}"
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

    provider_status = {

        "serpapi": False,
        "playwright": False,
        "curl_cffi": False,
        "crawl4ai": False
    }

    try:

        # =================================================
        # SERPAPI
        # =================================================

        serp_reviews = await asyncio.to_thread(

            serpapi_reviews,
            place_id
        )

        if serp_reviews:

            provider_status["serpapi"] = True

        all_reviews.extend(
            serp_reviews
        )

        all_reviews = deduplicate_reviews(
            all_reviews
        )

        logger.info(
            f"AFTER SERPAPI => {len(all_reviews)}"
        )

        # =================================================
        # PLAYWRIGHT
        # =================================================

        if len(all_reviews) < MAX_REVIEWS:

            try:

                playwright_result = await asyncio.wait_for(

                    playwright_reviews(place_id),

                    timeout=180
                )

            except asyncio.TimeoutError:

                logger.error(
                    "❌ PLAYWRIGHT TIMEOUT"
                )

                playwright_result = []

            if playwright_result:

                provider_status["playwright"] = True

            all_reviews.extend(
                playwright_result
            )

            all_reviews = deduplicate_reviews(
                all_reviews
            )

            logger.info(
                f"AFTER PLAYWRIGHT => {len(all_reviews)}"
            )

        # =================================================
        # CURL
        # =================================================

        if len(all_reviews) < MAX_REVIEWS:

            curl_result = await asyncio.to_thread(

                curl_reviews,
                place_id
            )

            if curl_result:

                provider_status["curl_cffi"] = True

            all_reviews.extend(
                curl_result
            )

            all_reviews = deduplicate_reviews(
                all_reviews
            )

            logger.info(
                f"AFTER CURL => {len(all_reviews)}"
            )

        # =================================================
        # CRAWL4AI
        # =================================================

        if len(all_reviews) < MAX_REVIEWS:

            crawl_result = await crawl4ai_reviews(
                place_id
            )

            if crawl_result:

                provider_status["crawl4ai"] = True

            all_reviews.extend(
                crawl_result
            )

            all_reviews = deduplicate_reviews(
                all_reviews
            )

            logger.info(
                f"AFTER CRAWL4AI => {len(all_reviews)}"
            )

        # =================================================
        # FINAL CLEANUP
        # =================================================

        all_reviews = deduplicate_reviews(
            all_reviews
        )

        if MAX_REVIEWS > 0:

            all_reviews = all_reviews[:MAX_REVIEWS]

        logger.info(
            f"""
            ======================================
            SCRAPER SUMMARY
            ======================================
            PLACE ID => {place_id}
            TOTAL REVIEWS => {len(all_reviews)}
            SERPAPI => {provider_status['serpapi']}
            PLAYWRIGHT => {provider_status['playwright']}
            CURL => {provider_status['curl_cffi']}
            CRAWL4AI => {provider_status['crawl4ai']}
            ======================================
            """
        )

        if len(all_reviews) == 0:

            logger.error(
                "❌ ALL SCRAPERS FAILED"
            )

            return []

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
