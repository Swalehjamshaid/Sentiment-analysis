# ==========================================================
# FILE: app/services/scraper.py
# TRUSTLYTICS AI SAAS
# PROFESSIONAL GOOGLE MAPS REVIEW SCRAPER
# SELENIUMBASE UC MODE + RESIDENTIAL PROXY
# ==========================================================
import os
import re
import gc
import time
import random
import hashlib
import logging
import traceback
from datetime import datetime
from typing import Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential
)
from fake_useragent import UserAgent
from sqlalchemy import (
    select,
    func,
    desc
)
from sqlalchemy.ext.asyncio import AsyncSession
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.core.models import (
    Review,
    Company
)

# ==========================================================
# LOGGER
# ==========================================================
logger = logging.getLogger(
    "app.services.scraper"
)

# ==========================================================
# ENVIRONMENT
# ==========================================================
PROXY_SERVER = os.getenv(
    "PROXY_SERVER"
)
PROXY_USERNAME = os.getenv(
    "PROXY_USERNAME"
)
PROXY_PASSWORD = os.getenv(
    "PROXY_PASSWORD"
)

# ==========================================================
# IMPORTANT
# ==========================================================
HEADLESS = False
MAX_SCROLL_ATTEMPTS = 180
MAX_IDLE_SCROLLS = 18
SCROLL_PAUSE_MIN = 2.8
SCROLL_PAUSE_MAX = 5.2

# ==========================================================
# REVIEW WORDS
# ==========================================================
REVIEW_WORDS = [
    "review", "reviews", "rating", "ratings", "avis",
    "bewertungen", "reseñas", "opinion", "yorum",
    "отзывы", "口コミ", "리뷰", "评论", "समीक्षा", "recensioni",
]

# ==========================================================
# HELPERS
# ==========================================================
def safe_string(value, default=""):
    try:
        if value is None:
            return default
        return str(value).strip()
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def clean_review_text(text):
    text = safe_string(text)
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")
    text = text.replace("\t", " ")
    text = " ".join(text.split())
    return text[:5000]


def normalize_rating(label):
    try:
        match = re.search(r"([0-9.]+)", str(label))
        if match:
            return int(float(match.group(1)))
    except Exception:
        pass
    return 5


def generate_hash(author, text):
    raw = f"{author}_{text[:250]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_google_maps_search_url(query):
    query = query.replace(" ", "+")
    return f"https://www.google.com/maps/search/{query}"


# ==========================================================
# EXISTING REVIEWS
# ==========================================================
async def get_existing_reviews(
    session: AsyncSession,
    company_id: int
):
    stmt = (
        select(Review)
        .where(Review.company_id == company_id)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    mapped = {row.google_review_id: row for row in rows}
    return mapped


# ==========================================================
# NORMALIZE REVIEW
# ==========================================================
def normalize_review(
    item: Dict[str, Any],
    company_id: int
):
    try:
        author_name = safe_string(item.get("author_name"), "Anonymous")
        review_text = clean_review_text(item.get("text"))

        if not review_text:
            return None

        rating = safe_int(item.get("rating"), 5)
        google_review_id = item.get("review_id") or generate_hash(author_name, review_text)

        return {
            "google_review_id": google_review_id,
            "author_name": author_name,
            "rating": rating,
            "text": review_text,
            "google_review_time": datetime.utcnow(),
            "review_likes": 0,
            "sentiment_score": round(rating / 5, 2)
        }
    except Exception as e:
        logger.exception(f"❌ NORMALIZE FAILED: {e}")
        return None


# ==========================================================
# CREATE DRIVER
# ==========================================================
def create_driver():
    logger.info("🚀 STARTING SELENIUMBASE UC DRIVER")
    proxy = None
    if PROXY_SERVER and PROXY_USERNAME and PROXY_PASSWORD:
        proxy = f"{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_SERVER}"

    driver = Driver(
        uc=True,
        headless=HEADLESS,
        undetectable=True,
        incognito=True,
        guest_mode=True,
        do_not_track=True,
        disable_gpu=True,
        proxy=proxy,
        agent=UserAgent().random,
        chromium_arg=[
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-popup-blocking",
            "--disable-notifications",
            "--disable-infobars",
            "--window-size=1440,960",
        ]
    )
    return driver


# ==========================================================
# CAPTCHA / RATE LIMIT
# ==========================================================
def is_rate_limited(driver):
    try:
        current_url = safe_string(driver.current_url).lower()
        source = safe_string(driver.page_source).lower()
        keywords = ["captcha", "recaptcha", "unusual traffic", "not a robot", "/sorry/"]
        return any(kw in current_url or kw in source for kw in keywords)
    except Exception:
        return False


# ==========================================================
# HUMAN WARMUP
# ==========================================================
def warmup_session(driver):
    try:
        logger.info("🔥 WARMING SESSION")
        driver.get("https://www.google.com")
        time.sleep(5)
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(2)
        driver.execute_script("window.scrollBy(0, -200);")
        time.sleep(2)
    except Exception as e:
        logger.exception(f"❌ WARMUP FAILED: {e}")


# ==========================================================
# CLICK SEARCH RESULT (Improved)
# ==========================================================
def click_first_search_result(driver):
    logger.info("📦 CLICKING SEARCH RESULT")
    selectors = [
        'a.hfpxzc', 'div.Nv2PK a', 'div[role="article"]',
        'a[href*="/maps/place/"]', 'a[jsaction]'
    ]

    for selector in selectors:
        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            results = driver.find_elements("css selector", selector)
            if not results:
                continue

            first = results[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", first)
            time.sleep(1.5)
            driver.execute_script("arguments[0].click();", first)

            logger.info("✅ SEARCH RESULT CLICKED")
            time.sleep(9)
            return True
        except Exception as e:
            logger.debug(f"Selector {selector} failed: {e}")
            continue
    return False


# ==========================================================
# OPEN REVIEWS PANEL (World-Class Smart Version)
# ==========================================================
def open_reviews_panel(driver):
    logger.info("📦 OPENING REVIEWS PANEL")
    time.sleep(12)

    # Smart selectors in priority order
    smart_selectors = [
        "button[aria-label*='Reviews']",
        "button[data-value='Reviews']",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'review')]",
        "//div[contains(@role,'tab')]//span[contains(text(),'Reviews')]",
        "button span:contains('Reviews')",
    ]

    for selector in smart_selectors:
        try:
            if selector.startswith("//"):
                elem = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            else:
                elem = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            time.sleep(1.8)
            driver.execute_script("arguments[0].click();", elem)

            logger.info("✅ REVIEWS PANEL OPENED")
            time.sleep(8)

            # Verify feed
            if driver.find_elements("css selector", 'div[role="feed"]'):
                logger.info("✅ REVIEW FEED VERIFIED")
                return True
        except Exception:
            continue

    # Fallback: Brute force with smart filtering
    logger.warning("⚠️ Smart selectors failed, using optimized fallback")
    try:
        elements = driver.find_elements("css selector", "button, div[role='tab'], span")
        for element in elements[:80]:   # Limited for performance
            try:
                text = safe_string(element.text).lower()
                aria = safe_string(element.get_attribute("aria-label")).lower()
                if any(word in text or word in aria for word in ["review", "reviews", "bewertungen", "reseñas"]):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(1.5)
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(8)
                    if driver.find_elements("css selector", 'div[role="feed"]'):
                        return True
            except:
                continue
    except Exception as e:
        logger.exception(f"❌ REVIEW PANEL FALLBACK FAILED: {e}")

    logger.warning("⚠️ REVIEWS BUTTON NOT FOUND")
    return False


# ==========================================================
# EXPAND MORE BUTTONS
# ==========================================================
def expand_review_buttons(driver):
    selectors = [
        "button.w8nwRe",
        "button[jsaction*='expandReview']",
        "button[aria-label*='More']"
    ]
    for selector in selectors:
        try:
            buttons = driver.find_elements("css selector", selector)
            for btn in buttons:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                except:
                    pass
        except:
            pass


# ==========================================================
# EXTRACT REVIEWS (Optimized & Cleaner)
# ==========================================================
def extract_reviews(driver, target_limit=500):
    logger.info("📦 STARTING REVIEW EXTRACTION")
    reviews = []
    seen_ids = set()

    try:
        scroll_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"], div[aria-label*="Reviews"]'))
        )
    except Exception:
        logger.error("❌ REVIEW FEED NOT FOUND")
        return reviews

    idle_scrolls = 0
    previous_count = 0

    for attempt in range(MAX_SCROLL_ATTEMPTS):
        try:
            expand_review_buttons(driver)

            cards = driver.find_elements(
                "css selector",
                'div.jftiEf, div[data-review-id], article'
            )

            for card in cards:
                try:
                    # Author
                    author = ""
                    for sel in [".d4r55", ".TSUbDb", "span.d4r55"]:
                        try:
                            author = safe_string(card.find_element("css selector", sel).text)
                            if author:
                                break
                        except:
                            pass

                    # Text
                    review_text = ""
                    for sel in [".wiI7pd", ".MyEned", "span.wiI7pd"]:
                        try:
                            review_text = clean_review_text(
                                card.find_element("css selector", sel).text
                            )
                            if review_text:
                                break
                        except:
                            pass

                    if not review_text:
                        continue

                    # Rating
                    rating = 5
                    for sel in ["span[aria-label*='star']", "span.kvMYJc"]:
                        try:
                            rating_label = card.find_element("css selector", sel).get_attribute("aria-label")
                            rating = normalize_rating(rating_label)
                            break
                        except:
                            pass

                    review_id = generate_hash(author, review_text)
                    if review_id in seen_ids:
                        continue

                    seen_ids.add(review_id)
                    reviews.append({
                        "review_id": review_id,
                        "author_name": author or "Anonymous",
                        "rating": rating,
                        "text": review_text
                    })
                except:
                    continue

            logger.info(f"✅ TOTAL REVIEWS: {len(reviews)} | Attempt: {attempt}")

            if len(reviews) >= target_limit:
                logger.info(f"🎯 TARGET LIMIT REACHED: {target_limit}")
                break

            # Human-like scroll
            driver.execute_script(
                "arguments[0].scrollBy(0, 2800);", scroll_container
            )
            time.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

            current_count = len(reviews)
            if current_count == previous_count:
                idle_scrolls += 1
            else:
                idle_scrolls = 0
            previous_count = current_count

            if idle_scrolls >= MAX_IDLE_SCROLLS:
                logger.warning("⚠️ SCROLL IDLE LIMIT REACHED")
                break

        except Exception as e:
            logger.exception(f"❌ SCROLL FAILED: {e}")

    gc.collect()
    return reviews


# ==========================================================
# MAIN SCRAPER
# ==========================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=20)
)
async def scrape_google_reviews(
    business_name: str,
    target_limit: int = 500
):
    driver = None
    try:
        driver = create_driver()

        logger.info("🌐 VERIFYING PROXY")
        driver.get("https://api.ipify.org")
        logger.info(f"🌐 ACTIVE IP: {driver.page_source.strip()[:120]}")

        warmup_session(driver)

        search_url = build_google_maps_search_url(business_name)
        logger.info(f"🌐 SEARCH URL: {search_url}")
        driver.get(search_url)
        time.sleep(10)

        if is_rate_limited(driver):
            logger.warning("⚠️ GOOGLE RATE LIMITED")
            time.sleep(70)
            return []

        clicked = click_first_search_result(driver)
        if not clicked:
            logger.warning("⚠️ SEARCH RESULT CLICK FAILED")
            return []

        opened = open_reviews_panel(driver)
        if not opened:
            logger.warning("⚠️ REVIEWS PANEL FAILED")
            return []

        reviews = extract_reviews(driver, target_limit=target_limit)
        logger.info(f"✅ SCRAPED REVIEWS: {len(reviews)}")
        return reviews

    except Exception as e:
        logger.exception(f"❌ SCRAPER FAILED: {e}")
        logger.error(traceback.format_exc())
        return []
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


# ==========================================================
# FETCH REVIEWS + ANALYTICS SERVICE (Unchanged)
# ==========================================================
async def fetch_reviews_from_google(
    business_name: str,
    company_id: int,
    session: AsyncSession,
    target_limit: int = 500
):
    logger.info(f"🚀 FETCH REVIEWS STARTED | company={company_id}")
    try:
        reviews = await scrape_google_reviews(
            business_name=business_name,
            target_limit=target_limit
        )
        if not reviews:
            logger.warning("⚠️ NO REVIEWS SCRAPED")
            return []

        existing_reviews = await get_existing_reviews(session, company_id)
        inserted_reviews = []

        for idx, item in enumerate(reviews):
            try:
                normalized = normalize_review(item, company_id)
                if not normalized:
                    continue

                if normalized["google_review_id"] in existing_reviews:
                    continue

                review = Review(
                    company_id=company_id,
                    google_review_id=normalized["google_review_id"],
                    author_name=normalized["author_name"],
                    rating=normalized["rating"],
                    text=normalized["text"],
                    google_review_time=normalized["google_review_time"],
                    review_likes=normalized["review_likes"],
                    sentiment_score=normalized["sentiment_score"]
                )
                session.add(review)
                inserted_reviews.append(normalized)

                if idx % 50 == 0:
                    await session.commit()
            except Exception as row_error:
                logger.exception(f"❌ SAVE REVIEW FAILED: {row_error}")

        await session.commit()
        logger.info(f"✅ INSERTED REVIEWS: {len(inserted_reviews)}")
        return inserted_reviews

    except Exception as e:
        logger.exception(f"❌ FETCH FAILED: {e}")
        await session.rollback()
        return []


class ReviewService:
    @staticmethod
    async def get_latest_reviews(
        db: AsyncSession,
        company_id: int,
        limit: int = 50
    ):
        stmt = (
            select(Review)
            .where(Review.company_id == company_id)
            .order_by(desc(Review.created_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_total_reviews(db: AsyncSession, company_id: int):
        stmt = select(func.count(Review.id)).where(Review.company_id == company_id)
        result = await db.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    async def get_average_rating(db: AsyncSession, company_id: int):
        stmt = select(func.avg(Review.rating)).where(Review.company_id == company_id)
        result = await db.execute(stmt)
        avg = result.scalar()
        return round(float(avg), 2) if avg else 0
