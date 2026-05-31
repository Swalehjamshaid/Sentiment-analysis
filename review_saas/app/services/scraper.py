# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE GOOGLE REVIEW SCRAPER
# PATCHRIGHT + PLAYWRIGHT STEALTH + CRAWL4AI
# FULLY ALIGNED WITH review.py
# =========================================================

from __future__ import annotations

# =========================================================
# STANDARD LIBRARIES
# =========================================================

import os
import re
import time
import random
import asyncio
import hashlib
import logging
import traceback
import secrets

from datetime import datetime
from typing import Dict, List, Any, Optional

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("🚀 QUANTUM ENTERPRISE SCRAPER BOOTING")

# =========================================================
# CACHE
# =========================================================

from cachetools import TTLCache

review_cache = TTLCache(
    maxsize=2000,
    ttl=3600
)

# =========================================================
# TENACITY & BACKOFF
# =========================================================

from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential
)
import backoff

# =========================================================
# EXTERNAL LIBRARIES CONDITIONAL IMPORT MATRICES
# =========================================================

SELECTOLAX_AVAILABLE = False
try:
    from selectolax.parser import HTMLParser
    SELECTOLAX_AVAILABLE = True
    logger.info("✅ SELECTOLAX READY")
except Exception as e:
    logger.error(f"❌ SELECTOLAX ERROR => {e}")

BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
    logger.info("✅ BS4 READY")
except Exception as e:
    logger.error(f"❌ BS4 ERROR => {e}")

CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
    logger.info("✅ CURL_CFFI READY")
except Exception as e:
    logger.error(f"❌ CURL_CFFI ERROR => {e}")

PATCHRIGHT_AVAILABLE = False
try:
    from patchright.async_api import (
        async_playwright,
        TimeoutError as PlaywrightTimeoutError
    )
    PATCHRIGHT_AVAILABLE = True
    logger.info("✅ PATCHRIGHT READY")
except Exception as e:
    logger.error(f"❌ PATCHRIGHT ERROR => {e}")

STEALTH_AVAILABLE = False
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
    logger.info("✅ STEALTH READY")
except Exception as e:
    logger.error(f"❌ STEALTH ERROR => {e}")

CRAWL4AI_AVAILABLE = False
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
    logger.info("✅ CRAWL4AI READY")
except Exception as e:
    logger.error(f"❌ CRAWL4AI ERROR => {e}")

FAKE_UA_AVAILABLE = False
try:
    from fake_useragent import UserAgent
    fake_ua = UserAgent()
    FAKE_UA_AVAILABLE = True
except Exception:
    fake_ua = None

# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "180"))
MAX_REVIEWS = int(os.getenv("SCRAPER_MAX_REVIEWS", "100"))
HEADLESS_MODE = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"

# =========================================================
# PROXY POOL STRUCTS & PERSISTENCE MAPPINGS
# =========================================================

PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip()
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()

PROXY_POOL = []
FAILED_PROXIES = set()

if PROXY_SERVER:
    PROXY_POOL.append({
        "server": f"http://{PROXY_SERVER}",
        "username": PROXY_USERNAME,
        "password": PROXY_PASSWORD
    })

logger.info(f"✅ PROXY COUNT => {len(PROXY_POOL)}")

# =========================================================
# CONCURRENCY SEMAPHORES
# =========================================================

SCRAPER_SEMAPHORE = asyncio.Semaphore(2)

# =========================================================
# ADVANCED STRUCTURAL ARCHITECTURE STATE persistence MATRIX
# =========================================================

QUANTUM_MEMORY = {
    "GLOBAL_STATE": {
        "best_proxy": None,
        "best_selector": None,
        "best_provider": "patchright"
    },
    "SELECTOR_STATE": {
        'button[jsaction*="pane.reviewChart.moreReviews"]': {"success": 1, "fail": 0},
        'button[aria-label*="reviews"]': {"success": 1, "fail": 0},
        'button[aria-label*="Reviews"]': {"success": 1, "fail": 0},
        'button[aria-label*="Review"]': {"success": 1, "fail": 0},
        'button[jsaction*="reviews"]': {"success": 1, "fail": 0},
        'button[data-tab-index="1"]': {"success": 1, "fail": 0},
        '[role="tab"][aria-label*="Reviews"]': {"success": 1, "fail": 0}
    },
    "PROXY_HEALTH": {},  # Format schema: { proxy_url: {"success_count": 1, "fail_count": 0, "captcha_count": 0, "response_time": [1.2]} }
    "PROVIDER_STATS": {
        "patchright": {"success": 1, "total": 1},
        "crawl4ai": {"success": 1, "total": 1}
    }
}

# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.utcnow()


def quantum_entropy():
    return secrets.randbelow(1000000)


async def quantum_delay():
    entropy = quantum_entropy()
    delay = ((entropy % 3000) / 1000)
    await asyncio.sleep(max(1, delay))


def maps_url(place_id: str):
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def get_user_agent():
    static_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ]
    if FAKE_UA_AVAILABLE and fake_ua:
        try:
            return fake_ua.random
        except Exception:
            pass
    return random.choice(static_agents)


def detect_captcha(html: str):
    html_lower = html.lower()
    patterns = ["captcha", "unusual traffic", "not a robot", "sorry"]
    return any(p in html_lower for p in patterns)

# =========================================================
# MACHINE PERSISTENT TELEMETRY OPTIMIZATION ENGINES
# =========================================================

def get_optimized_selectors() -> List[str]:
    """Sorts interactive layout click selectors based on dynamic real-time performance profiles."""
    state = QUANTUM_MEMORY["SELECTOR_STATE"]
    
    def calculate_selector_yield(sel: str) -> float:
        stats = state.get(sel, {"success": 1, "fail": 0})
        total = stats["success"] + stats["fail"]
        return stats["success"] / total if total > 0 else 0.5

    return sorted(list(state.keys()), key=calculate_selector_yield, reverse=True)


def update_selector_score(selector: str, success: bool):
    """Mutates global state memory, triggering instant propagation matrix updates."""
    if selector not in QUANTUM_MEMORY["SELECTOR_STATE"]:
        QUANTUM_MEMORY["SELECTOR_STATE"][selector] = {"success": 0, "fail": 0}
    
    if success:
        QUANTUM_MEMORY["SELECTOR_STATE"][selector]["success"] += 1
        QUANTUM_MEMORY["GLOBAL_STATE"]["best_selector"] = selector
    else:
        QUANTUM_MEMORY["SELECTOR_STATE"][selector]["fail"] += 1


def score_proxy(proxy_server: str) -> float:
    """Evaluates multi-variable routing vectors using weighted algorithmic scaling."""
    metrics = QUANTUM_MEMORY["PROXY_HEALTH"].get(proxy_server)
    if not metrics:
        return 0.5

    s_count = metrics["success_count"]
    f_count = metrics["fail_count"]
    c_count = metrics["captcha_count"]
    times = metrics["response_time"]

    total = s_count + f_count
    if total == 0:
        return 0.5

    success_rate = s_count / total
    captcha_rate = c_count / total
    avg_latency = sum(times) / len(times) if times else 1.5
    
    normalized_latency = min(avg_latency / 10.0, 1.0)
    
    # Mathematical Multi-Variable Scoring Optimization Formula
    score = (success_rate * 0.6) - (captcha_rate * 0.3) - (normalized_latency * 0.1)
    return score


def update_quantum_proxy(proxy_server: str, success: bool, is_captcha: bool, response_time: float):
    """Saves exact execution route telemetry data directly into the application state matrix."""
    if proxy_server not in QUANTUM_MEMORY["PROXY_HEALTH"]:
        QUANTUM_MEMORY["PROXY_HEALTH"][proxy_server] = {
            "success_count": 1, "fail_count": 0, "captcha_count": 0, "response_time": []
        }
    
    metrics = QUANTUM_MEMORY["PROXY_HEALTH"][proxy_server]
    if success:
        metrics["success_count"] += 1
    else:
        metrics["fail_count"] += 1

    if is_captcha:
        metrics["captcha_count"] += 1

    metrics["response_time"].append(response_time)
    if len(metrics["response_time"]) > 25:
        metrics["response_time"].pop(0)


def get_best_proxy() -> Optional[Dict[str, str]]:
    """Identifies the cleanest, highest-yielding network route available inside pool queues."""
    try:
        available = [p for p in PROXY_POOL if p["server"] not in FAILED_PROXIES]
        if not available:
            return None
        
        scored = sorted(available, key=lambda p: score_proxy(p["server"]), reverse=True)
        chosen = scored[0]
        QUANTUM_MEMORY["GLOBAL_STATE"]["best_proxy"] = chosen["server"]
        return chosen
    except Exception:
        return None


def get_annealed_provider() -> str:
    """Decides which extraction framework historical patterns favor most at initialization."""
    stats = QUANTUM_MEMORY["PROVIDER_STATS"]
    p_rate = stats["patchright"]["success"] / stats["patchright"]["total"] if stats["patchright"]["total"] > 0 else 1.0
    c_rate = stats["crawl4ai"]["success"] / stats["crawl4ai"]["total"] if stats["crawl4ai"]["total"] > 0 else 0.8
    
    winner = "patchright" if p_rate >= c_rate else "crawl4ai"
    QUANTUM_MEMORY["GLOBAL_STATE"]["best_provider"] = winner
    return winner

# =========================================================
# REVIEW NORMALIZATION & CLEANING
# =========================================================

def generate_review_id(place_id: str, author: str, text: str):
    raw = f"{place_id}:{author}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_review(review: Dict[str, Any], place_id: str):
    try:
        review_text = str(review.get("review_text", review.get("text", review.get("content", "")))).strip()
        if not review_text:
            return None

        author = str(review.get("author", review.get("author_name", "Anonymous"))).strip()
        if not author:
            author = "Anonymous"

        rating = review.get("rating", 5)
        try:
            rating = int(float(rating))
        except Exception:
            rating = 5
        rating = max(1, min(rating, 5))

        return {
            "google_review_id": generate_review_id(place_id, author, review_text),
            "author": author,
            "author_name": author,
            "rating": rating,
            "review_text": review_text,
            "content": review_text,
            "text": review_text,
            "sentiment_score": 0.5,
            "google_review_time": utc_now(),
            "scraped_at": utc_now()
        }
    except Exception as e:
        logger.error(f"❌ NORMALIZE ERROR => {e}")
        return None


def deduplicate_reviews(reviews: List[Dict]):
    seen = set()
    unique = []
    for review in reviews:
        review_id = review.get("google_review_id", "")
        if not review_id or review_id in seen:
            continue
        seen.add(review_id)
        unique.append(review)
    return unique


async def debug_page(page, stage: str):
    try:
        logger.info(f"🔥 PAGE URL [{stage}] => {page.url}")
        logger.info(f"🔥 PAGE TITLE [{stage}] => {await page.title()}")
        await page.screenshot(path=f"debug_{stage}.png", full_page=True)
    except Exception as e:
        logger.error(f"❌ DEBUG ERROR => {e}")

# =========================================================
# INTER-PARSER 3-WAY CONSENSUS VOTING ELECTION MATRIX
# =========================================================

def extract_via_consensus(html_content: str, card_selector: str, place_id: str) -> List[Dict[str, Any]]:
    """Executes multi-engine parse runs to validate extracted element volumes."""
    if not html_content:
        return []

    bs_reviews = []
    selectolax_count = 0
    heuristic_count = 0

    # Engine Module 1: BeautifulSoup Verification Runtime
    if BS4_AVAILABLE:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            elements = soup.select(card_selector)
            for el in elements:
                try:
                    author_el = el.select_one(".d4r55, .TSUbDb, span[class*=author]")
                    author = author_el.text.strip() if author_el else "Anonymous"
                    
                    text_el = el.select_one(".wiI7pd, .MyEned, span[jsname]")
                    text = text_el.text.strip() if text_el else ""
                    
                    rating_el = el.select_one("span.kvMYJc")
                    rating = 5
                    if rating_el and rating_el.has_attr("aria-label"):
                        aria = rating_el["aria-label"]
                        match = re.search(r"(\d)", aria)
                        if match:
                            rating = int(match.group(1))

                    normalized = normalize_review({"author": author, "rating": rating, "review_text": text}, place_id)
                    if normalized:
                        bs_reviews.append(normalized)
                except Exception:
                    continue
        except Exception as ex:
            logger.error(f"❌ CONSENSUS BS4 RUN FAULT => {ex}")

    # Engine Module 2: Selectolax Tokenization Verification
    if SELECTOLAX_AVAILABLE:
        try:
            tree = HTMLParser(html_content)
            selectolax_count = len(tree.css(card_selector))
        except Exception:
            selectolax_count = 0

    # Engine Module 3: Fast Text Density Heuristic Pattern Matches
    heuristic_count = len(re.findall(r'class="wiI7pd"', html_content))

    # Election Consolidation Logic Routine
    sample_sizes = [len(bs_reviews), selectolax_count, heuristic_count]
    voted_consensus_count = max(set(sample_sizes), key=sample_sizes.count)
    
    logger.info(f"🗳️ CONSENSUS ELECTIONS => BS4: {len(bs_reviews)} | Selectolax: {selectolax_count} | Heuristic: {heuristic_count}. Settled Count: {voted_consensus_count}")

    return bs_reviews[:voted_consensus_count]

# =========================================================
# PATCHRIGHT PROVIDER ENGINE
# =========================================================

@backoff.on_exception(backoff.expo, Exception, max_time=120)
async def patchright_reviews(place_id: str) -> List[Dict[str, Any]]:
    reviews = []
    if not PATCHRIGHT_AVAILABLE:
        logger.error("❌ PATCHRIGHT NOT AVAILABLE")
        return reviews

    QUANTUM_MEMORY["PROVIDER_STATS"]["patchright"]["total"] += 1
    start_mark = time.time()
    proxy = get_best_proxy()
    captcha_hit = False

    async with SCRAPER_SEMAPHORE:
        browser = None
        try:
            logger.info(f"🔥 ACTIVE PROXY NODE => {proxy}")
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=HEADLESS_MODE,
                    proxy=proxy,
                    channel="chrome",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                        "--no-sandbox",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--disable-site-isolation-trials",
                        "--disable-infobars",
                        "--start-maximized",
                        "--disable-extensions",
                        "--disable-popup-blocking"
                    ]
                )
                
                # FIX 1: Clean, explicit new_context assignment instantiation
                context = await browser.new_context(
                    user_agent=get_user_agent(),
                    locale="en-US",
                    timezone_id="America/New_York",
                    java_script_enabled=True,
                    ignore_https_errors=True,
                    color_scheme="dark",
                    viewport={"width": random.randint(1366, 1920), "height": random.randint(768, 1080)}
                )
                
                page = await context.new_page()
                await page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                
                if STEALTH_AVAILABLE:
                    try:
                        await stealth_async(page)
                    except Exception:
                        pass

                target_url = maps_url(place_id)
                logger.info(f"🔥 TARGET URL => {target_url}")
                
                await page.goto(target_url, wait_until="networkidle", timeout=120000)
                await page.wait_for_timeout(random.randint(4000, 7000))
                await debug_page(page, "before_reviews")

                # FIX 2: Optimized Adaptive Element Traversal Run
                review_button_selectors = get_optimized_selectors()
                clicked = False
                
                for selector in review_button_selectors:
                    try:
                        locator = page.locator(selector).first
                        count = await locator.count()
                        logger.info(f"🔥 REVIEW BUTTON {selector} => {count}")
                        
                        if count > 0:
                            await locator.click()
                            clicked = True
                            update_selector_score(selector, True)
                            logger.info(f"✅ CLICKED => {selector}")
                            break
                    except Exception as e:
                        update_selector_score(selector, False)
                        logger.error(f"❌ CLICK ERROR => {e}")

                if not clicked:
                    logger.error("❌ REVIEW BUTTON NOT FOUND IN INTERACTION RUN")

                await page.wait_for_timeout(6000)
                await debug_page(page, "after_review_click")

                html = await page.content()
                if detect_captcha(html):
                    captcha_hit = True
                    logger.error("❌ CAPTCHA DETECTED DURING INITIALIZATION")
                    return reviews

                # Infinite scrolling viewport extraction loop
                cards = page.locator("div.jftiEf")
                previous_count = 0
                no_growth = 0
                
                while no_growth < 6:
                    try:
                        await page.mouse.move(random.randint(100, 1000), random.randint(100, 600))
                        await page.evaluate(
                            "document.querySelectorAll('[role=\"main\"]').forEach(p => p.scrollTop += 2500);"
                        )
                        await quantum_delay()
                        current_count = await cards.count()
                        logger.info(f"🔥 REVIEW COUNT => {current_count}")
                        
                        if current_count == previous_count:
                            no_growth += 1
                        else:
                            no_growth = 0
                        
                        previous_count = current_count
                        if current_count >= MAX_REVIEWS:
                            break
                    except Exception as scroll_ex:
                        logger.error(f"❌ SCROLL ERROR => {scroll_ex}")
                        break

                final_markup = await page.content()
                
                # FIX 3: Route structural layout blocks through our Consensus Engine
                reviews = extract_via_consensus(final_markup, "div.jftiEf", place_id)
                logger.info(f"✅ PATCHRIGHT REVIEWS => {len(reviews)}")

                if proxy:
                    update_quantum_proxy(proxy["server"], True, False, time.time() - start_mark)
                QUANTUM_MEMORY["PROVIDER_STATS"]["patchright"]["success"] += 1

        except Exception as e:
            logger.error(f"❌ PATCHRIGHT RUN FAULT => {e}")
            if proxy:
                update_quantum_proxy(proxy["server"], False, captcha_hit, time.time() - start_mark)
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    return reviews

# =========================================================
# CRAWL4AI PROVIDER SHADOW ENGINE
# =========================================================

async def crawl4ai_reviews(place_id: str) -> List[Dict[str, Any]]:
    """Fast secondary engine parsing engine layouts directly through async crawler channels."""
    if not CRAWL4AI_AVAILABLE:
        return []

    QUANTUM_MEMORY["PROVIDER_STATS"]["crawl4ai"]["total"] += 1
    start_mark = time.time()
    proxy = get_best_proxy()

    async with SCRAPER_SEMAPHORE:
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=maps_url(place_id),
                    bypass_cache=True,
                    timeout=45000
                )
                
                if result.success and result.html:
                    reviews = extract_via_consensus(result.html, "div.jftiEf", place_id)
                    if proxy:
                        update_quantum_proxy(proxy["server"], True, False, time.time() - start_mark)
                    QUANTUM_MEMORY["PROVIDER_STATS"]["crawl4ai"]["success"] += 1
                    return reviews
        except Exception as e:
            logger.error(f"❌ CRAWL4AI RUN FAULT => {e}")
            if proxy:
                update_quantum_proxy(proxy["server"], False, False, time.time() - start_mark)
        
        return []

# =========================================================
# MASTER SCRAPER CORE DRIVER
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict[str, Any]]:
    """Unified engine coordinator maintaining complete backwards compatibility signature constraints."""
    logger.info(f"🚀 MASTER SCRAPER => {place_id}")
    if not place_id:
        return []

    cache_key = f"reviews:{place_id}"
    try:
        cached = review_cache.get(cache_key)
        if cached:
            logger.info("⚡ CACHE HIT")
            return cached
    except Exception:
        pass

    start_time = time.time()
    all_reviews = []
    
    # Read optimization priorities from memory state mappings prior to gathering states
    favored_provider = get_annealed_provider()
    active_proxy_node = QUANTUM_MEMORY["GLOBAL_STATE"]["best_proxy"]
    active_selector_node = QUANTUM_MEMORY["GLOBAL_STATE"]["best_selector"]

    # Superposition execution layer: Trigger both collection pipelines simultaneously
    tasks = [
        patchright_reviews(place_id),
        crawl4ai_reviews(place_id)
    ]
    
    logger.info(f"🌌 EXECUTING CONCURRENT SUPERPOSITION DATA STATE RUNS [Favored Engine: {favored_provider}]")
    execution_states = await asyncio.gather(*tasks, return_exceptions=True)

    # Clean returned exceptions out of collection state arrays safely
    patchright_dataset = execution_states[0] if not isinstance(execution_states[0], Exception) else []
    crawl4ai_dataset = execution_states[1] if not isinstance(execution_states[1], Exception) else []

    # Dynamic Optimization Selection Matrix
    if len(patchright_dataset) >= len(crawl4ai_dataset) and patchright_dataset:
        all_reviews.extend(patchright_dataset)
        selected_provider = "patchright"
    elif crawl4ai_dataset:
        all_reviews.extend(crawl4ai_dataset)
        selected_provider = "crawl4ai"
    else:
        selected_provider = "none"

    # Consolidation, cleaning and bounds sizing operations
    all_reviews = deduplicate_reviews(all_reviews)
    all_reviews = all_reviews[:MAX_REVIEWS]

    try:
        review_cache[cache_key] = all_reviews
    except Exception:
        pass

    duration_delta = time.time() - start_time
    
    # Structural Telemetry Logs
    telemetry_payload = {
        "scrape_duration": duration_delta,
        "provider_used": selected_provider,
        "captcha_hits": 1 if selected_provider == "none" and len(all_reviews) == 0 else 0,
        "reviews_found": len(all_reviews),
        "proxy_used": active_proxy_node,
        "selector_used": active_selector_node,
        "timestamp": time.time()
    }
    
    logger.info(f"📊 SYSTEM OBSERVABILITY TELETREMY => {telemetry_payload}")
    logger.info(f"✅ FINAL REVIEWS => {len(all_reviews)}")

    return all_reviews

# =========================================================
# ALIAS MAPPINGS
# =========================================================

async def run_scraper(place_id: str) -> List[Dict[str, Any]]:
    return await scrape_google_reviews(place_id)

# =========================================================
# READY COLD START INITIALIZATION
# =========================================================

logger.info("✅ QUANTUM PATCHRIGHT SCRAPER READY")
