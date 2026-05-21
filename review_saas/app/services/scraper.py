# ==========================================================
# FILE: app/services/scraper.py
# GOOGLE REVIEWS SCRAPER - MAY 2026 ENTERPRISE VERSION
# PLAYWRIGHT + CAMOUFOX + COOKIES + PROXY + STEALTH
# ==========================================================

import os
import re
import gc
import json
import time
import random
import asyncio
import hashlib
import logging
import traceback

from typing import List, Dict, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential
)

from fake_useragent import UserAgent

from playwright.async_api import (
    TimeoutError
)

from camoufox.async_api import (
    AsyncCamoufox
)

# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(
    "app.services.scraper"
)

# ==========================================================
# CONFIG
# ==========================================================

HEADLESS = False

MAX_SCROLLS = 120

MAX_IDLE_SCROLLS = 10

SCROLL_PAUSE_MIN = 2

SCROLL_PAUSE_MAX = 6

DEBUG_DIR = "/tmp"

COOKIES_FILE = "cookies.json"

# ==========================================================
# PROXY CONFIG
# ==========================================================

PROXY_SERVER = os.getenv(
    "PROXY_SERVER",
    "http://gw.dataimpulse.com:823"
)

PROXY_USERNAME = os.getenv(
    "PROXY_USERNAME"
)

PROXY_PASSWORD = os.getenv(
    "PROXY_PASSWORD"
)

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


def clean_text(text):

    text = safe_string(text)

    text = text.replace("\n", " ")

    text = text.replace("\r", " ")

    text = text.replace("\t", " ")

    text = " ".join(text.split())

    return text[:5000]


def normalize_rating(value):

    try:

        match = re.search(
            r"([0-9.]+)",
            str(value)
        )

        if match:

            return int(
                float(
                    match.group(1)
                )
            )

    except Exception:
        pass

    return 5


def generate_hash(author, text):

    raw = f"{author}_{text}"

    return hashlib.md5(
        raw.encode("utf-8")
    ).hexdigest()

# ==========================================================
# DEBUGGING
# ==========================================================

async def save_debug_files(page, name="debug"):

    try:

        screenshot_path = f"{DEBUG_DIR}/{name}.png"

        html_path = f"{DEBUG_DIR}/{name}.html"

        await page.screenshot(
            path=screenshot_path,
            full_page=True
        )

        html = await page.content()

        with open(
            html_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

        logger.info(
            f"📸 DEBUG SAVED => {name}"
        )

        logger.info(
            f"🌐 TITLE => {await page.title()}"
        )

        logger.info(
            f"🌐 URL => {page.url}"
        )

    except Exception as e:

        logger.exception(
            f"❌ DEBUG SAVE FAILED => {e}"
        )

# ==========================================================
# CAPTCHA / GOOGLE BLOCK DETECTION
# ==========================================================

async def detect_google_block(page):

    try:

        content = (
            await page.content()
        ).lower()

        keywords = [

            "captcha",

            "unusual traffic",

            "not a robot",

            "/sorry/",

            "automated queries",

            "detected unusual traffic"
        ]

        for keyword in keywords:

            if keyword in content:

                logger.warning(
                    f"⚠️ GOOGLE BLOCK => {keyword}"
                )

                return True

        return False

    except Exception:

        return False

# ==========================================================
# LOAD COOKIES
# ==========================================================

async def load_cookies(context):

    try:

        if not os.path.exists(COOKIES_FILE):

            logger.warning(
                "⚠️ cookies.json NOT FOUND"
            )

            return

        with open(
            COOKIES_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            cookies = json.load(f)

        for cookie in cookies:

            if cookie.get("sameSite") not in [

                "Strict",

                "Lax",

                "None"
            ]:

                cookie["sameSite"] = "None"

        await context.add_cookies(
            cookies
        )

        logger.info(
            f"🍪 COOKIES LOADED => {len(cookies)}"
        )

    except Exception as e:

        logger.exception(
            f"❌ COOKIE LOAD FAILED => {e}"
        )

# ==========================================================
# HUMAN SCROLL
# ==========================================================

async def human_scroll(page):

    try:

        amount = random.randint(
            1200,
            4000
        )

        await page.mouse.wheel(
            0,
            amount
        )

        await asyncio.sleep(

            random.uniform(

                SCROLL_PAUSE_MIN,

                SCROLL_PAUSE_MAX
            )
        )

    except Exception:
        pass

# ==========================================================
# HANDLE CONSENT
# ==========================================================

async def handle_google_consent(page):

    try:

        buttons = await page.query_selector_all(
            "button"
        )

        for button in buttons:

            try:

                text = clean_text(
                    await button.inner_text()
                ).lower()

                if any(
                    x in text
                    for x in [

                        "accept",

                        "i agree",

                        "accept all"
                    ]
                ):

                    await button.click()

                    logger.info(
                        "✅ CONSENT ACCEPTED"
                    )

                    await asyncio.sleep(5)

                    return

            except Exception:
                continue

    except Exception:
        pass

# ==========================================================
# OPEN REVIEWS PANEL
# ==========================================================

async def open_reviews_panel(page):

    logger.info(
        "📦 OPENING REVIEW PANEL"
    )

    await asyncio.sleep(10)

    selectors = [

        'button[jsaction*="pane.reviewChart.moreReviews"]',

        'button[aria-label*="reviews"]',

        'button[aria-label*="Reviews"]',

        'div[role="button"][aria-label*="reviews"]',

        'div[role="button"][aria-label*="Reviews"]',

        'xpath=//span[@class="z3HNkc"]/following-sibling::span//a'
    ]

    for selector in selectors:

        try:

            elements = await page.query_selector_all(
                selector
            )

            logger.info(
                f"📦 SELECTOR => {selector} => {len(elements)}"
            )

            for element in elements:

                try:

                    await element.scroll_into_view_if_needed()

                    await asyncio.sleep(2)

                    await element.click(
                        timeout=15000
                    )

                    logger.info(
                        "✅ REVIEW BUTTON CLICKED"
                    )

                    await asyncio.sleep(12)

                    review_feed = await page.query_selector(
                        'div[role="feed"], div.RVCQse'
                    )

                    if review_feed:

                        logger.info(
                            "✅ REVIEW FEED FOUND"
                        )

                        return True

                except Exception:
                    continue

        except Exception:
            continue

    logger.warning(
        "⚠️ REVIEW PANEL NOT OPENED"
    )

    return False

# ==========================================================
# EXPAND REVIEWS
# ==========================================================

async def expand_reviews(page):

    try:

        buttons = await page.query_selector_all(
            "button"
        )

        for button in buttons:

            try:

                text = clean_text(
                    await button.inner_text()
                ).lower()

                if any(
                    x in text
                    for x in [

                        "more",

                        "full review"
                    ]
                ):

                    await button.click()

                    await asyncio.sleep(1)

            except Exception:
                continue

    except Exception:
        pass

# ==========================================================
# EXTRACT REVIEWS
# ==========================================================

async def extract_reviews(

    page,

    target_limit=500
):

    logger.info(
        "📦 STARTING ADVANCED EXTRACTION"
    )

    reviews = []

    seen_ids = set()

    idle_scrolls = 0

    previous_count = 0

    # ======================================================
    # REVIEW FEED RECOVERY
    # ======================================================

    review_feed = None

    for retry in range(5):

        logger.info(
            f"🔄 REVIEW FEED DETECTION => {retry}"
        )

        review_feed = await page.query_selector(

            'div[role="feed"], div.RVCQse'
        )

        if review_feed:

            logger.info(
                "✅ REVIEW FEED FOUND"
            )

            break

        await human_scroll(page)

        await asyncio.sleep(

            random.uniform(3, 7)
        )

    if not review_feed:

        logger.warning(
            "⚠️ REVIEW FEED NOT FOUND"
        )

        await save_debug_files(
            page,
            "review_feed_missing"
        )

        return []

    # ======================================================
    # EXTRACTION LOOP
    # ======================================================

    for scroll in range(MAX_SCROLLS):

        logger.info(
            f"📦 SCROLL => {scroll}"
        )

        try:

            # ==================================================
            # CAPTCHA DETECTION
            # ==================================================

            blocked = await detect_google_block(
                page
            )

            if blocked:

                logger.warning(
                    "⚠️ CAPTCHA DURING EXTRACTION"
                )

                await save_debug_files(
                    page,
                    "captcha_mid_scrape"
                )

                break

            # ==================================================
            # REVIEW MODAL VALIDATION
            # ==================================================

            review_modal = await page.query_selector(
                'div[role="dialog"]'
            )

            if not review_modal:

                logger.warning(
                    "⚠️ REVIEW MODAL CLOSED"
                )

                reopened = await open_reviews_panel(
                    page
                )

                if reopened:

                    logger.info(
                        "✅ REVIEW MODAL REOPENED"
                    )

                    await asyncio.sleep(10)

            # ==================================================
            # WAIT FOR REVIEW CARDS
            # ==================================================

            try:

                await page.wait_for_selector(

                    'div[data-review-id], '

                    'div[jsname="ShBeI"], '

                    'div.jftiEf, '

                    'div.MyEned',

                    timeout=30000
                )

            except Exception:

                logger.warning(
                    "⚠️ REVIEW CARD WAIT TIMEOUT"
                )

            # ==================================================
            # MULTI SELECTOR EXTRACTION
            # ==================================================

            review_selectors = [

                'div[data-review-id]',

                'div[jsname="ShBeI"]',

                'div.jftiEf',

                'div.MyEned',

                'div[role="article"]'
            ]

            cards = []

            for selector in review_selectors:

                try:

                    selector_cards = await page.query_selector_all(
                        selector
                    )

                    logger.info(
                        f"📦 SELECTOR => {selector} => {len(selector_cards)}"
                    )

                    if len(selector_cards) > 0:

                        cards.extend(
                            selector_cards
                        )

                except Exception:
                    continue

            # ==================================================
            # REMOVE DUPLICATES
            # ==================================================

            unique_cards = []

            seen_elements = set()

            for card in cards:

                try:

                    html = await card.inner_html()

                    element_hash = hashlib.md5(
                        html.encode("utf-8")
                    ).hexdigest()

                    if element_hash in seen_elements:
                        continue

                    seen_elements.add(
                        element_hash
                    )

                    unique_cards.append(
                        card
                    )

                except Exception:
                    continue

            cards = unique_cards

            logger.info(
                f"📦 UNIQUE CARDS => {len(cards)}"
            )

            # ==================================================
            # PARSE REVIEWS
            # ==================================================

            for card in cards:

                try:

                    author = ""

                    review_text = ""

                    rating = 5

                    review_date = ""

                    # ==========================================
                    # AUTHOR
                    # ==========================================

                    author_selectors = [

                        '.d4r55',

                        '.TSUbDb',

                        '.Vpc5Fe',

                        'span[class*="d4r55"]'
                    ]

                    for selector in author_selectors:

                        try:

                            elem = await card.query_selector(
                                selector
                            )

                            if elem:

                                author = clean_text(

                                    await elem.inner_text()
                                )

                                if author:
                                    break

                        except Exception:
                            continue

                    # ==========================================
                    # REVIEW TEXT
                    # ==========================================

                    text_selectors = [

                        '.wiI7pd',

                        '.MyEned',

                        '.OA1nbd',

                        'span[jscontroller]',

                        'div[class*="review"] span'
                    ]

                    for selector in text_selectors:

                        try:

                            elem = await card.query_selector(
                                selector
                            )

                            if elem:

                                review_text = clean_text(

                                    await elem.inner_text()
                                )

                                if review_text:
                                    break

                        except Exception:
                            continue

                    if not review_text:
                        continue

                    # ==========================================
                    # RATING
                    # ==========================================

                    rating_selectors = [

                        'span[aria-label*="star"]',

                        '.kvMYJc',

                        '.dHX2k'
                    ]

                    for selector in rating_selectors:

                        try:

                            elem = await card.query_selector(
                                selector
                            )

                            if elem:

                                label = await elem.get_attribute(
                                    "aria-label"
                                )

                                rating = normalize_rating(
                                    label
                                )

                                break

                        except Exception:
                            continue

                    # ==========================================
                    # DATE
                    # ==========================================

                    date_selectors = [

                        '.rsqaWe',

                        '.y3Ibjb'
                    ]

                    for selector in date_selectors:

                        try:

                            elem = await card.query_selector(
                                selector
                            )

                            if elem:

                                review_date = clean_text(

                                    await elem.inner_text()
                                )

                                if review_date:
                                    break

                        except Exception:
                            continue

                    # ==========================================
                    # DEDUPLICATION
                    # ==========================================

                    review_id = generate_hash(
                        author,
                        review_text
                    )

                    if review_id in seen_ids:
                        continue

                    seen_ids.add(
                        review_id
                    )

                    reviews.append({

                        "review_id":
                            review_id,

                        "author_name":
                            author,

                        "rating":
                            rating,

                        "review_date":
                            review_date,

                        "text":
                            review_text
                    })

                except Exception as e:

                    logger.warning(
                        f"⚠️ REVIEW PARSE FAILED => {e}"
                    )

                    continue

            logger.info(
                f"✅ TOTAL REVIEWS => {len(reviews)}"
            )

            # ==================================================
            # TARGET LIMIT
            # ==================================================

            if len(reviews) >= target_limit:

                logger.info(
                    "🎯 TARGET LIMIT REACHED"
                )

                break

            # ==================================================
            # EXPAND REVIEWS
            # ==================================================

            await expand_reviews(page)

            # ==================================================
            # PRIMARY FEED SCROLL
            # ==================================================

            try:

                await page.evaluate("""

                    () => {

                        const feed = document.querySelector(
                            'div[role="feed"], div.RVCQse'
                        );

                        if (feed) {

                            feed.scrollBy(
                                0,
                                4000
                            );
                        }
                    }

                """)

            except Exception:

                logger.warning(
                    "⚠️ FEED SCROLL FAILED"
                )

            # ==================================================
            # FALLBACK PAGE SCROLL
            # ==================================================

            try:

                await page.mouse.wheel(
                    0,
                    4000
                )

            except Exception:
                pass

            await asyncio.sleep(

                random.uniform(4, 8)
            )

            # ==================================================
            # IDLE DETECTION
            # ==================================================

            current_count = len(reviews)

            if current_count == previous_count:

                idle_scrolls += 1

                logger.warning(
                    f"⚠️ IDLE SCROLL => {idle_scrolls}"
                )

            else:

                idle_scrolls = 0

            previous_count = current_count

            # ==================================================
            # RECOVERY REOPEN
            # ==================================================

            if idle_scrolls >= 3:

                logger.warning(
                    "⚠️ REOPENING REVIEW PANEL"
                )

                await open_reviews_panel(
                    page
                )

                await asyncio.sleep(10)

            # ==================================================
            # FINAL STOP
            # ==================================================

            if idle_scrolls >= MAX_IDLE_SCROLLS:

                logger.warning(
                    "⚠️ MAX IDLE SCROLL REACHED"
                )

                break

        except Exception as e:

            logger.exception(
                f"❌ EXTRACTION LOOP ERROR => {e}"
            )

            await save_debug_files(
                page,
                f"extraction_error_{scroll}"
            )

    logger.info(
        f"✅ FINAL REVIEW COUNT => {len(reviews)}"
    )

    gc.collect()

    return reviews

# ==========================================================
# MAIN SCRAPER
# ==========================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(
        multiplier=2,
        min=3,
        max=20
    )
)
async def scrape_google_reviews(

    place_id: str,

    target_limit: int = 500
):

    browser = None

    try:

        logger.info(
            "🚀 STARTING SCRAPER"
        )

        proxy = {

            "server":
                PROXY_SERVER,

            "username":
                PROXY_USERNAME,

            "password":
                PROXY_PASSWORD
        }

        browser = await AsyncCamoufox(

            headless=HEADLESS,

            humanize=True,

            geoip=True,

            block_webrtc=True,

            i_know_what_im_doing=True,

            proxy=proxy
        ).start()

        context = await browser.new_context(

            locale="en-US",

            timezone_id="America/New_York",

            user_agent=UserAgent().random,

            viewport={

                "width": 1440,

                "height": 960
            }
        )

        # ==================================================
        # LOAD COOKIES
        # ==================================================

        await load_cookies(context)

        page = await context.new_page()

        # ==================================================
        # STEALTH PATCH
        # ==================================================

        await page.add_init_script("""

            Object.defineProperty(
                navigator,
                'webdriver',
                {
                    get: () => undefined
                }
            );

        """)

        # ==================================================
        # VERIFY PROXY
        # ==================================================

        logger.info(
            "🌐 VERIFYING PROXY"
        )

        await page.goto(

            "https://ipinfo.io/json",

            wait_until="domcontentloaded",

            timeout=120000
        )

        ip_data = await page.text_content(
            "body"
        )

        logger.info(
            f"🌐 ACTIVE PROXY IP => {ip_data}"
        )

        # ==================================================
        # GOOGLE WARMUP
        # ==================================================

        await page.goto(

            "https://www.google.com",

            wait_until="domcontentloaded",

            timeout=120000
        )

        await asyncio.sleep(8)

        await handle_google_consent(page)

        await human_scroll(page)

        # ==================================================
        # OPEN MAPS
        # ==================================================

        maps_url = (
            f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        )

        logger.info(
            f"🌐 OPENING URL => {maps_url}"
        )

        await page.goto(

            maps_url,

            wait_until="domcontentloaded",

            timeout=120000
        )

        await asyncio.sleep(15)

        await handle_google_consent(page)

        await save_debug_files(
            page,
            "maps_loaded"
        )

        # ==================================================
        # GOOGLE BLOCK CHECK
        # ==================================================

        blocked = await detect_google_block(
            page
        )

        if blocked:

            logger.warning(
                "⚠️ GOOGLE BLOCK DETECTED"
            )

            await save_debug_files(
                page,
                "google_blocked"
            )

            return []

        # ==================================================
        # OPEN REVIEW PANEL
        # ==================================================

        opened = await open_reviews_panel(
            page
        )

        if not opened:

            logger.warning(
                "⚠️ REVIEW PANEL FAILED"
            )

            await save_debug_files(
                page,
                "review_panel_failed"
            )

            return []

        # ==================================================
        # EXTRACT REVIEWS
        # ==================================================

        reviews = await extract_reviews(

            page,

            target_limit=target_limit
        )

        if len(reviews) == 0:

            logger.warning(
                "⚠️ NO REVIEWS SCRAPED"
            )

            await save_debug_files(
                page,
                "no_reviews_scraped"
            )

        else:

            logger.info(
                f"✅ SCRAPED REVIEWS => {len(reviews)}"
            )

            await save_debug_files(
                page,
                "reviews_success"
            )

        return reviews

    except TimeoutError:

        logger.exception(
            "❌ PLAYWRIGHT TIMEOUT"
        )

        return []

    except Exception as e:

        logger.exception(
            f"❌ SCRAPER FAILED => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return []

    finally:

        try:

            if browser:

                await browser.close()

        except Exception:
            pass

        gc.collect()
