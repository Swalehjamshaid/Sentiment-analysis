# ==========================================================
# FILE: app/services/scraper.py
# REVIEW INTEL AI - RAILWAY SAFE GOOGLE REVIEWS SCRAPER
# SERPAPI REVIEWS ENGINE + DB SAFE INSERT - MAY 2026
# ==========================================================

import os
import re
import gc
import random
import asyncio
import hashlib
import logging

from datetime import datetime, timedelta

import httpx

from fake_useragent import UserAgent
from playwright.async_api import async_playwright

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect

from app.core.db import AsyncSessionLocal
from app.core.models import Review

logger = logging.getLogger("app.services.scraper")

# ==========================================================
# ENV
# ==========================================================

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

ENABLE_PLAYWRIGHT_FALLBACK = (
    os.getenv("ENABLE_PLAYWRIGHT_FALLBACK", "false").lower() == "true"
)

# ==========================================================
# CONFIG
# ==========================================================

REQUEST_TIMEOUT = 120
PLAYWRIGHT_TIMEOUT = 70000
HEADLESS = True
MAX_SCROLLS = 25

# ==========================================================
# BASIC HELPERS
# ==========================================================

def get_user_agent():
    try:
        return UserAgent().random
    except Exception:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        )


def clean_text(text):
    try:
        if not text:
            return ""

        text = str(text)
        text = text.replace("\n", " ")
        text = text.replace("\r", " ")
        text = text.replace("\t", " ")

        return " ".join(text.split())[:5000]

    except Exception:
        return ""


def safe_int(value, default=0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            match = re.search(r"\d+", value)
            if match:
                return int(match.group(0))

        return int(value)

    except Exception:
        return default


def generate_hash(*parts):
    raw = "_".join([clean_text(part) for part in parts if part is not None])

    return hashlib.md5(
        raw.encode("utf-8")
    ).hexdigest()


def parse_relative_date(relative_text):
    try:
        if not relative_text:
            return datetime.utcnow()

        text = str(relative_text).lower().strip()
        now = datetime.utcnow()

        if "just now" in text or "today" in text:
            return now

        if "yesterday" in text:
            return now - timedelta(days=1)

        match = re.search(r"(\d+)", text)
        number = int(match.group(1)) if match else 1

        if "minute" in text:
            return now - timedelta(minutes=number)

        if "hour" in text:
            return now - timedelta(hours=number)

        if "day" in text:
            return now - timedelta(days=number)

        if "week" in text:
            return now - timedelta(weeks=number)

        if "month" in text:
            return now - timedelta(days=number * 30)

        if "year" in text:
            return now - timedelta(days=number * 365)

        return now

    except Exception:
        return datetime.utcnow()


def build_proxy_url():
    try:
        if not PROXY_SERVER:
            return None

        if PROXY_USERNAME and PROXY_PASSWORD:
            return f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_SERVER}"

        return f"http://{PROXY_SERVER}"

    except Exception:
        return None


def get_random_proxy():
    proxy = build_proxy_url()
    return proxy if proxy else None

# ==========================================================
# SQLALCHEMY MODEL HELPERS
# ==========================================================

def get_review_model_columns():
    try:
        return {
            column.key
            for column in sa_inspect(Review).mapper.column_attrs
        }
    except Exception as e:
        logger.exception(f"REVIEW MODEL INSPECT FAILED => {type(e).__name__}: {e}")
        return set()


def get_first_existing_column(possible_columns):
    columns = get_review_model_columns()

    for column in possible_columns:
        if column in columns:
            return column

    return None


async def load_existing_review_ids(company_id: int):
    existing = set()

    try:
        id_column_name = get_first_existing_column(
            [
                "google_review_id",
                "review_id",
                "external_review_id",
                "external_id",
                "hash",
            ]
        )

        if not id_column_name:
            logger.warning("NO REVIEW ID COLUMN FOUND FOR DUPLICATE CHECK")
            return existing

        company_column_name = get_first_existing_column(
            [
                "company_id",
                "business_id",
            ]
        )

        id_column = getattr(Review, id_column_name)

        async with AsyncSessionLocal() as db:
            stmt = select(id_column)

            if company_id and company_column_name:
                stmt = stmt.where(
                    getattr(Review, company_column_name) == company_id
                )

            result = await db.execute(stmt)
            rows = result.fetchall()

            for row in rows:
                if row[0]:
                    existing.add(str(row[0]))

        logger.info(f"EXISTING REVIEW IDS => {len(existing)}")
        return existing

    except Exception as e:
        logger.exception(f"LOAD EXISTING REVIEW IDS FAILED => {type(e).__name__}: {e}")
        return set()

# ==========================================================
# NORMALIZE SERPAPI / PLAYWRIGHT REVIEW
# ==========================================================

def extract_review_text(review):
    return clean_text(
        review.get("snippet")
        or review.get("text")
        or review.get("description")
        or review.get("review")
        or ""
    )


def extract_author(review):
    user = review.get("user") or {}

    return clean_text(
        user.get("name")
        or review.get("user_name")
        or review.get("author_name")
        or review.get("author")
        or "Anonymous"
    )


def extract_review_date_text(review):
    return clean_text(
        review.get("date")
        or review.get("iso_date")
        or review.get("published_at")
        or review.get("relative_time_description")
        or ""
    )


def extract_rating(review):
    rating = (
        review.get("rating")
        or review.get("stars")
        or review.get("score")
        or 5
    )

    rating = safe_int(rating, 5)
    return max(1, min(rating, 5))


def normalize_review(
    review,
    existing_ids,
    seen,
    start_date=None,
    end_date=None,
):
    try:
        author = extract_author(review)
        text = extract_review_text(review)

        if not text or len(text) < 10:
            return None

        rating = extract_rating(review)

        review_date_text = extract_review_date_text(review)
        review_datetime = parse_relative_date(review_date_text)

        if start_date and review_datetime < start_date:
            return None

        if end_date and review_datetime > end_date:
            return None

        serpapi_review_id = clean_text(
            review.get("review_id")
            or review.get("link")
            or review.get("id")
            or ""
        )

        google_review_id = (
            serpapi_review_id
            if serpapi_review_id
            else generate_hash(author, text, str(rating), review_date_text)
        )

        google_review_id = str(google_review_id)

        if google_review_id in seen or google_review_id in existing_ids:
            return None

        seen.add(google_review_id)
        existing_ids.add(google_review_id)

        sentiment = "positive" if rating >= 4 else "negative"

        return {
            "google_review_id": google_review_id,
            "review_id": google_review_id,
            "author_name": author,
            "reviewer_name": author,
            "rating": rating,
            "stars": rating,
            "review_date": review_date_text,
            "google_review_time": review_datetime,
            "review_datetime": review_datetime,
            "text": text,
            "review_text": text,
            "content": text,
            "likes": safe_int(review.get("likes"), 0),
            "sentiment": sentiment,
            "source": "google",
            "platform": "google",
        }

    except Exception as e:
        logger.warning(f"NORMALIZE REVIEW FAILED => {type(e).__name__}: {e}")
        return None

# ==========================================================
# DB SAFE PAYLOAD BUILDER
# ==========================================================

def build_review_payload(company_id: int, review: dict):
    columns = get_review_model_columns()
    payload = {}

    direct_defaults = {
        "company_id": company_id,
        "business_id": company_id,
        "source": "google",
        "platform": "google",
    }

    for column, value in direct_defaults.items():
        if column in columns and value is not None:
            payload[column] = value

    field_sources = {
        "google_review_id": ["google_review_id", "review_id"],
        "review_id": ["review_id", "google_review_id"],
        "external_review_id": ["google_review_id", "review_id"],
        "external_id": ["google_review_id", "review_id"],
        "hash": ["google_review_id", "review_id"],

        "author_name": ["author_name", "reviewer_name"],
        "reviewer_name": ["reviewer_name", "author_name"],
        "author": ["author_name", "reviewer_name"],
        "name": ["author_name", "reviewer_name"],

        "rating": ["rating", "stars"],
        "stars": ["stars", "rating"],

        "review_date": ["review_date"],
        "date": ["review_date"],
        "google_review_time": ["google_review_time", "review_datetime"],
        "review_datetime": ["review_datetime", "google_review_time"],

        "text": ["text", "review_text", "content"],
        "review_text": ["review_text", "text", "content"],
        "content": ["content", "review_text", "text"],
        "comment": ["text", "review_text", "content"],

        "likes": ["likes"],
        "helpful_count": ["likes"],

        "sentiment": ["sentiment"],
    }

    for model_column, source_keys in field_sources.items():
        if model_column not in columns:
            continue

        for source_key in source_keys:
            value = review.get(source_key)

            if value is not None:
                payload[model_column] = value
                break

    return payload

# ==========================================================
# SAVE REVIEWS TO DATABASE
# ==========================================================

async def save_reviews_to_db(company_id: int, reviews: list[dict]):
    if not company_id:
        logger.error("COMPANY ID MISSING - CANNOT SAVE REVIEWS")
        return 0

    if not reviews:
        logger.info("NO REVIEWS TO SAVE")
        return 0

    saved_count = 0

    async with AsyncSessionLocal() as db:
        try:
            existing_ids = await load_existing_review_ids(company_id)

            for review in reviews:
                review_unique_id = str(
                    review.get("google_review_id")
                    or review.get("review_id")
                    or ""
                )

                if not review_unique_id:
                    continue

                if review_unique_id in existing_ids:
                    continue

                payload = build_review_payload(
                    company_id=company_id,
                    review=review,
                )

                if not payload:
                    logger.warning("EMPTY REVIEW PAYLOAD SKIPPED")
                    continue

                db_review = Review(**payload)
                db.add(db_review)

                existing_ids.add(review_unique_id)
                saved_count += 1

            await db.commit()

            logger.info(f"REVIEWS SAVED TO DB => {saved_count}")
            return saved_count

        except Exception as e:
            await db.rollback()
            logger.exception(f"SAVE REVIEWS FAILED => {type(e).__name__}: {e}")
            return 0

# ==========================================================
# SERPAPI GOOGLE MAPS REVIEWS SCRAPER
# ==========================================================

def build_serpapi_params(place_id, next_page_token=None):
    params = {
        "engine": "google_maps_reviews",
        "api_key": SERPAPI_KEY,
        "hl": "en",
        "gl": "us",
        "sort_by": "newestFirst",
    }

    place_id = clean_text(place_id)

    if place_id.startswith("0x") or ":0x" in place_id:
        params["data_id"] = place_id
    else:
        params["place_id"] = place_id

    if next_page_token:
        params["next_page_token"] = next_page_token

    return params


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=2, max=15),
)
async def scrape_serpapi_reviews(
    place_id,
    existing_ids=None,
    target_limit=100,
    start_date=None,
    end_date=None,
):
    reviews = []
    existing_ids = existing_ids or set()

    if not SERPAPI_KEY:
        logger.error("SERPAPI KEY MISSING")
        return []

    if not place_id:
        logger.error("PLACE ID MISSING FOR SERPAPI")
        return []

    try:
        headers = {
            "User-Agent": get_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json",
        }

        proxy_url = get_random_proxy()
        client_kwargs = {
            "timeout": REQUEST_TIMEOUT,
            "headers": headers,
        }

        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            next_page_token = None
            fetched = 0
            seen = set()

            while fetched < target_limit:
                params = build_serpapi_params(
                    place_id=place_id,
                    next_page_token=next_page_token,
                )

                logger.info(
                    f"SERPAPI GOOGLE MAPS REVIEWS REQUEST => fetched={fetched}"
                )

                response = await client.get(
                    "https://serpapi.com/search.json",
                    params=params,
                )

                logger.info(f"SERPAPI STATUS => {response.status_code}")

                if response.status_code != 200:
                    logger.warning(
                        f"SERPAPI BAD STATUS => {response.status_code} | {response.text[:800]}"
                    )
                    break

                data = response.json()

                search_status = data.get("search_metadata", {}).get("status")
                serp_error = data.get("error")
                place_info = data.get("place_info") or {}

                logger.info(f"SERPAPI SEARCH STATUS => {search_status}")
                logger.info(f"SERPAPI PLACE TITLE => {place_info.get('title')}")
                logger.info(f"SERPAPI PLACE TOTAL REVIEWS => {place_info.get('reviews')}")

                if serp_error:
                    logger.error(f"SERPAPI ERROR => {serp_error}")
                    break

                raw_reviews = data.get("reviews", []) or []

                logger.info(f"SERPAPI RAW REVIEWS => {len(raw_reviews)}")

                if not raw_reviews:
                    break

                for raw_review in raw_reviews:
                    normalized = normalize_review(
                        review=raw_review,
                        existing_ids=existing_ids,
                        seen=seen,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    if not normalized:
                        continue

                    reviews.append(normalized)
                    fetched += 1

                    if fetched >= target_limit:
                        break

                next_page_token = data.get(
                    "serpapi_pagination", {}
                ).get("next_page_token")

                if not next_page_token:
                    break

                await asyncio.sleep(random.uniform(1, 2.5))

        logger.info(f"SERPAPI REVIEWS FETCHED => {len(reviews)}")
        return reviews

    except Exception as e:
        logger.exception(f"SERPAPI FAILED => {type(e).__name__}: {e}")
        return []

# ==========================================================
# PLAYWRIGHT FALLBACK
# DISABLED BY DEFAULT ON RAILWAY
# ==========================================================

@retry(
    stop=stop_after_attempt(2),
    wait=wait_random_exponential(multiplier=2, max=10),
)
async def playwright_backup(
    place_id,
    existing_ids=None,
    target_limit=50,
    start_date=None,
    end_date=None,
):
    reviews = []
    existing_ids = existing_ids or set()

    if not ENABLE_PLAYWRIGHT_FALLBACK:
        logger.info("PLAYWRIGHT FALLBACK DISABLED")
        return []

    browser = None
    context = None

    try:
        async with async_playwright() as p:
            launch_options = {
                "headless": HEADLESS,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--no-sandbox",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                ],
            }

            if PROXY_SERVER:
                launch_options["proxy"] = {
                    "server": f"http://{PROXY_SERVER}",
                }

                if PROXY_USERNAME and PROXY_PASSWORD:
                    launch_options["proxy"]["username"] = PROXY_USERNAME
                    launch_options["proxy"]["password"] = PROXY_PASSWORD

            browser = await p.chromium.launch(**launch_options)

            context = await browser.new_context(
                user_agent=get_user_agent(),
                locale="en-US",
                viewport={
                    "width": 1366,
                    "height": 768,
                },
            )

            page = await context.new_page()
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(PLAYWRIGHT_TIMEOUT)

            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2}",
                lambda route: route.abort(),
            )

            url = (
                "https://www.google.com/maps/search/"
                f"?api=1&query=Google&query_place_id={place_id}"
            )

            logger.info(f"PLAYWRIGHT GOTO => {url}")

            try:
                await page.goto(
                    url,
                    wait_until="commit",
                    timeout=PLAYWRIGHT_TIMEOUT,
                )
            except Exception as goto_error:
                logger.exception(
                    f"PLAYWRIGHT GOTO FAILED => {type(goto_error).__name__}: {goto_error}"
                )
                return []

            await page.wait_for_timeout(5000)

            try:
                buttons = page.locator(
                    'button:has-text("Accept all"), '
                    'button:has-text("I agree"), '
                    'button:has-text("Accept")'
                )

                if await buttons.count() > 0:
                    await buttons.first.click()
                    await page.wait_for_timeout(2500)

            except Exception:
                pass

            try:
                review_button = page.locator(
                    'button[jsaction*="pane.reviewChart.moreReviews"], '
                    'button:has-text("Reviews"), '
                    'button:has-text("reviews")'
                )

                if await review_button.count() > 0:
                    await review_button.first.click()
                    await page.wait_for_timeout(5000)

            except Exception as e:
                logger.warning(f"PLAYWRIGHT REVIEW BUTTON FAILED => {e}")

            review_feed = page.locator('div[role="feed"]')

            for _ in range(MAX_SCROLLS):
                try:
                    if await review_feed.count() > 0:
                        await review_feed.first.evaluate(
                            "(el) => el.scrollTop = el.scrollHeight"
                        )

                    await page.mouse.wheel(0, random.randint(1200, 3000))
                    await page.wait_for_timeout(random.randint(1000, 2000))

                except Exception:
                    pass

            cards = page.locator("div[data-review-id]")
            count = await cards.count()

            logger.info(f"PLAYWRIGHT REVIEW CARDS => {count}")

            seen = set()

            for i in range(count):
                try:
                    card = cards.nth(i)

                    try:
                        author = clean_text(
                            await card.locator(".d4r55").inner_text()
                        )
                    except Exception:
                        author = "Anonymous"

                    text = ""

                    for selector in [
                        'span[jsname="bN97Pc"]',
                        ".MyEned",
                        ".wiI7pd",
                    ]:
                        try:
                            text = clean_text(
                                await card.locator(selector).inner_text()
                            )

                            if text:
                                break

                        except Exception:
                            pass

                    if not text:
                        continue

                    try:
                        review_date = clean_text(
                            await card.locator(".rsqaWe").inner_text()
                        )
                    except Exception:
                        review_date = ""

                    rating = 5

                    try:
                        aria = await card.locator(".kvMYJc").get_attribute(
                            "aria-label"
                        )

                        match = re.search(r"(\d)", str(aria))

                        if match:
                            rating = int(match.group(1))

                    except Exception:
                        pass

                    normalized = normalize_review(
                        review={
                            "user": {
                                "name": author,
                            },
                            "snippet": text,
                            "rating": rating,
                            "date": review_date,
                        },
                        existing_ids=existing_ids,
                        seen=seen,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    if not normalized:
                        continue

                    reviews.append(normalized)

                    if len(reviews) >= target_limit:
                        break

                except Exception as card_error:
                    logger.warning(f"PLAYWRIGHT CARD FAILED => {card_error}")
                    continue

        logger.info(f"PLAYWRIGHT REVIEWS FETCHED => {len(reviews)}")
        return reviews

    except Exception as e:
        logger.exception(f"PLAYWRIGHT FAILED => {type(e).__name__}: {e}")
        return []

    finally:
        try:
            if context:
                await context.close()
        except Exception:
            pass

        try:
            if browser:
                await browser.close()
        except Exception:
            pass

# ==========================================================
# MAIN SCRAPER
# ==========================================================

async def scrape_google_reviews(
    place_id: str,
    company_id: int = None,
    target_limit: int = 100,
    start_date=None,
    end_date=None,
    save_to_database: bool = True,
):
    logger.info(f"HYBRID SCRAPER STARTED => {place_id}")

    try:
        if not place_id:
            logger.error("PLACE ID MISSING")
            return []

        existing_review_ids = set()

        if company_id:
            existing_review_ids = await load_existing_review_ids(company_id)

        serp_reviews = await scrape_serpapi_reviews(
            place_id=place_id,
            existing_ids=existing_review_ids,
            target_limit=target_limit,
            start_date=start_date,
            end_date=end_date,
        )

        if len(serp_reviews) < target_limit and ENABLE_PLAYWRIGHT_FALLBACK:
            remaining = target_limit - len(serp_reviews)

            logger.warning(f"PLAYWRIGHT FALLBACK STARTED => {remaining}")

            playwright_reviews = await playwright_backup(
                place_id=place_id,
                existing_ids=existing_review_ids,
                target_limit=remaining,
                start_date=start_date,
                end_date=end_date,
            )

            serp_reviews.extend(playwright_reviews)

        else:
            logger.info("PLAYWRIGHT FALLBACK SKIPPED")

        final_reviews = []
        seen = set()

        for review in serp_reviews:
            review_id = str(
                review.get("google_review_id")
                or review.get("review_id")
                or ""
            )

            if not review_id:
                continue

            if review_id in seen:
                continue

            if not review.get("text") and not review.get("review_text"):
                continue

            seen.add(review_id)
            final_reviews.append(review)

        logger.info(f"FINAL REVIEW COUNT => {len(final_reviews)}")

        if save_to_database and company_id:
            saved_count = await save_reviews_to_db(
                company_id=company_id,
                reviews=final_reviews,
            )

            logger.info(f"FINAL DB SAVED COUNT => {saved_count}")

        return final_reviews

    except Exception as e:
        logger.exception(f"SCRAPER FAILED => {type(e).__name__}: {e}")
        return []

    finally:
        gc.collect()
