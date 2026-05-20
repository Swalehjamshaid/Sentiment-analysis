# ==========================================================
# FILE: app/services/scraper.py
# TRUSTLYTICS AI SAAS
# PROFESSIONAL GOOGLE MAPS REVIEW SCRAPER — WORLD CLASS EDITION
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

from tenacity import retry, stop_after_attempt, wait_exponential
from fake_useragent import UserAgent
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.core.models import Review

# ==========================================================
logger = logging.getLogger("app.services.scraper")

# ==========================================================
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

HEADLESS = False
MAX_SCROLL_ATTEMPTS = 220
MAX_IDLE_SCROLLS = 25
SCROLL_PAUSE_MIN = 3.2
SCROLL_PAUSE_MAX = 6.5

# ==========================================================
# HELPERS
# ==========================================================
def safe_string(value, default=""):
    try:
        return str(value).strip() if value is not None else default
    except:
        return default

def safe_int(value, default=0):
    try:
        return int(float(value))
    except:
        return default

def clean_review_text(text):
    text = safe_string(text)
    text = re.sub(r'\s+', ' ', text)
    return text[:5000]

def normalize_rating(label):
    try:
        match = re.search(r'([0-9.]+)', str(label))
        return int(float(match.group(1))) if match else 5
    except:
        return 5

def generate_hash(author, text):
    raw = f"{author}_{text[:200]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def build_google_maps_search_url(query):
    query = query.replace(" ", "+")
    return f"https://www.google.com/maps/search/{query}"


# ==========================================================
# DRIVER & UTILS
# ==========================================================
def create_driver():
    logger.info("🚀 STARTING WORLD-CLASS SELENIUMBASE UC DRIVER")
    proxy = f"{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_SERVER}" if all([PROXY_SERVER, PROXY_USERNAME, PROXY_PASSWORD]) else None

    driver = Driver(
        uc=True,
        headless=HEADLESS,
        undetectable=True,
        incognito=True,
        guest_mode=True,
        proxy=proxy,
        agent=UserAgent().random,
        chromium_arg=[
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--window-size=1440,960",
        ]
    )
    return driver


def is_rate_limited(driver):
    try:
        url = driver.current_url.lower()
        src = driver.page_source.lower()
        return any(x in url or x in src for x in ["captcha", "recaptcha", "unusual traffic", "/sorry/"])
    except:
        return False


def warmup_session(driver):
    try:
        driver.get("https://www.google.com")
        time.sleep(7)
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(2.5)
    except Exception as e:
        logger.exception(f"Warmup failed: {e}")


# ==========================================================
# ULTRA ROBUST REVIEWS PANEL OPENER (5-LAYER STRATEGY)
# ==========================================================
def open_reviews_panel(driver):
    logger.info("📦 OPENING REVIEWS PANEL — ULTRA ROBUST MODE")

    time.sleep(10)

    strategies = [
        # Strategy 1: Aria-label (Most Reliable)
        lambda: WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label*='Reviews'], button[aria-label*='review']"))
        ),
        # Strategy 2: Data-value
        lambda: WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-value='Reviews']"))
        ),
        # Strategy 3: XPath Text Content
        lambda: WebDriverWait(driver, 12).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'review')]"))
        ),
        # Strategy 4: Tab Role
        lambda: WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='tab']//span[contains(text(),'Reviews')]"))
        ),
    ]

    for i, strategy in enumerate(strategies, 1):
        try:
            elem = strategy()
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            time.sleep(1.5)
            driver.execute_script("arguments[0].click();", elem)
            logger.info(f"✅ Reviews panel opened using Strategy {i}")
            time.sleep(9)
            return True
        except:
            continue

    # === FINAL AGGRESSIVE FALLBACK ===
    logger.warning("⚠️ All standard strategies failed → Using AGGRESSIVE FALLBACK")
    try:
        # Find all elements with "review" text
        elements = driver.find_elements(By.XPATH, 
            "//button | //div[@role='tab'] | //span | //div[contains(@class,'button')]"
        )
        
        best_candidate = None
        best_score = 0

        for el in elements[:120]:
            try:
                text = safe_string(el.text).lower()
                aria = safe_string(el.get_attribute("aria-label")).lower()
                combined = text + " " + aria
                
                score = sum(1 for word in ["review", "reviews", "bewertungen", "reseñas", "avis"] if word in combined)
                if score > best_score:
                    best_score = score
                    best_candidate = el
            except:
                continue

        if best_candidate and best_score > 0:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", best_candidate)
            time.sleep(2)
            driver.execute_script("arguments[0].click();", best_candidate)
            logger.info("✅ Reviews opened using AGGRESSIVE FALLBACK")
            time.sleep(10)
            return True
    except Exception as e:
        logger.exception(f"Aggressive fallback failed: {e}")

    logger.error("❌ ALL STRATEGIES FAILED TO OPEN REVIEWS")
    return False


# ==========================================================
# SORT BY NEWEST
# ==========================================================
def sort_by_newest(driver):
    try:
        sort_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label,'Sort') or contains(text(),'Sort')]"))
        )
        driver.execute_script("arguments[0].click();", sort_btn)
        time.sleep(2.5)

        newest = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//li[contains(.,'Newest') or @data-index='1']"))
        )
        driver.execute_script("arguments[0].click();", newest)
        logger.info("✅ Sorted by Newest")
        time.sleep(7)
    except:
        logger.info("ℹ️ Could not sort by Newest (skipping)")


# ==========================================================
# EXTRACT REVIEWS
# ==========================================================
def expand_review_buttons(driver):
    for sel in ["button.w8nwRe", "button[jsaction*='expand']", "button[aria-label*='More']"]:
        try:
            for btn in driver.find_elements(By.CSS_SELECTOR, sel):
                driver.execute_script("arguments[0].click();", btn)
        except:
            pass


def extract_reviews(driver, target_limit=500):
    logger.info("📦 STARTING REVIEW EXTRACTION")
    reviews = []
    seen_ids = set()

    try:
        scroll_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"], div[aria-label*="Reviews"], .m6QErb'))
        )
    except:
        logger.error("❌ Review feed container not found")
        return reviews

    idle = 0
    prev = 0

    for attempt in range(MAX_SCROLL_ATTEMPTS):
        try:
            expand_review_buttons(driver)

            cards = driver.find_elements(By.CSS_SELECTOR, 'div.jftiEf, div[data-review-id], article')

            for card in cards:
                try:
                    author = safe_string(card.find_element(By.CSS_SELECTOR, ".d4r55, .TSUbDb").text)
                    text_el = card.find_element(By.CSS_SELECTOR, ".wiI7pd, .MyEned")
                    review_text = clean_review_text(text_el.text)

                    if not review_text:
                        continue

                    rating = 5
                    try:
                        rating_el = card.find_element(By.CSS_SELECTOR, "span[aria-label*='star']")
                        rating = normalize_rating(rating_el.get_attribute("aria-label"))
                    except:
                        pass

                    r_id = generate_hash(author, review_text)
                    if r_id in seen_ids:
                        continue
                    seen_ids.add(r_id)

                    reviews.append({
                        "review_id": r_id,
                        "author_name": author or "Anonymous",
                        "rating": rating,
                        "text": review_text
                    })
                except:
                    continue

            logger.info(f"📊 Progress: {len(reviews)} reviews | Attempt {attempt}")

            if len(reviews) >= target_limit:
                break

            driver.execute_script("arguments[0].scrollBy(0, 2800);", scroll_container)
            time.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))

            if len(reviews) == prev:
                idle += 1
            else:
                idle = 0
            prev = len(reviews)

            if idle >= MAX_IDLE_SCROLLS:
                break

        except Exception as e:
            logger.exception(f"Extraction error: {e}")

    gc.collect()
    return reviews[:target_limit]


# ==========================================================
# MAIN SCRAPER
# ==========================================================
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2.5, min=5, max=30))
async def scrape_google_reviews(business_name: str, target_limit: int = 500):
    driver = None
    try:
        driver = create_driver()

        driver.get("https://api.ipify.org")
        logger.info(f"🌐 Proxy IP: {driver.page_source.strip()[:100]}")

        warmup_session(driver)

        driver.get(build_google_maps_search_url(business_name))
        time.sleep(12)

        if is_rate_limited(driver):
            logger.warning("⚠️ Google Rate Limited")
            time.sleep(120)
            return []

        # Click first result
        if not click_first_search_result(driver):   # (Keep your original or use improved one)
            return []

        if not open_reviews_panel(driver):
            return []

        sort_by_newest(driver)

        reviews = extract_reviews(driver, target_limit)
        logger.info(f"✅ WORLD-CLASS SCRAPE COMPLETE: {len(reviews)} reviews")
        return reviews

    except Exception as e:
        logger.exception(f"❌ CRITICAL SCRAPER FAILURE: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


# ==========================================================
# Keep your existing helper functions below
# (get_existing_reviews, normalize_review, fetch_reviews_from_google, ReviewService)
# ==========================================================
