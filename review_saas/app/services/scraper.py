# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE GOOGLE REVIEW SCRAPER - VERSION 11.0
# PRODUCTION GRADE WITH FULL DIAGNOSTICS
# FULLY ALIGNED WITH review.py - NO BREAKING CHANGES
# =========================================================

from __future__ import annotations

# =========================================================
# STANDARD LIBRARIES
# =========================================================

import os
import re
import time
import json
import random
import asyncio
import hashlib
import logging
import traceback
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field, asdict

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("🚀 QUANTUM ENTERPRISE SCRAPER V11.0 BOOTING - PRODUCTION GRADE")

# =========================================================
# CACHE (Maintained for compatibility)
# =========================================================

from cachetools import TTLCache

review_cache = TTLCache(maxsize=2000, ttl=3600)

# =========================================================
# QUANTUM MEMORY - PERSISTENT
# =========================================================

class QuantumMemory:
    """Persistent memory with Redis/PostgreSQL persistence"""
    
    def __init__(self):
        self.in_memory = {
            "GLOBAL_STATE": {
                "total_scrapes": 0,
                "total_reviews": 0,
                "started_at": datetime.utcnow().isoformat()
            },
            "SELECTOR_STATE": {},
            "PROVIDER_STATS": {},
            "PROXY_HEALTH": {},
            "COOLDOWN_PROXIES": {}
        }
        self.redis_client = None
        self.pg_conn = None
        self._init_persistence()
        self._load_selector_state()  # Priority 5: Load selector stats on startup
    
    def _init_persistence(self):
        """Initialize Redis and PostgreSQL connections if available"""
        try:
            import redis
            redis_host = os.getenv("REDIS_HOST", "")
            if redis_host:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    password=os.getenv("REDIS_PASSWORD", None),
                    decode_responses=True
                )
                self.redis_client.ping()
                logger.info("✅ Redis persistence enabled")
        except Exception as e:
            logger.debug(f"Redis not available: {e}")
        
        try:
            import psycopg2
            pg_host = os.getenv("PG_HOST", "")
            if pg_host:
                self.pg_conn = psycopg2.connect(
                    host=pg_host,
                    port=int(os.getenv("PG_PORT", 5432)),
                    database=os.getenv("PG_DATABASE", "quantum_scraper"),
                    user=os.getenv("PG_USER", "postgres"),
                    password=os.getenv("PG_PASSWORD", "")
                )
                self._init_postgres_schema()
                logger.info("✅ PostgreSQL persistence enabled")
        except Exception as e:
            logger.debug(f"PostgreSQL not available: {e}")
    
    def _init_postgres_schema(self):
        """Create tables if they don't exist"""
        try:
            with self.pg_conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS scraper_analytics (
                        id SERIAL PRIMARY KEY,
                        place_id TEXT,
                        reviews_found INTEGER,
                        duration FLOAT,
                        provider_used TEXT,
                        success BOOLEAN,
                        timestamp TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS selector_performance (
                        selector TEXT PRIMARY KEY,
                        success_count INTEGER DEFAULT 0,
                        fail_count INTEGER DEFAULT 0,
                        last_used TIMESTAMP DEFAULT NOW()
                    )
                """)
                self.pg_conn.commit()
        except Exception as e:
            logger.warning(f"PostgreSQL schema init failed: {e}")
    
    def _load_selector_state(self):
        """Priority 5: Load existing selector stats from persistence"""
        if self.redis_client:
            try:
                keys = self.redis_client.keys("selector:*")
                for key in keys:
                    selector = key.replace("selector:", "")
                    data = self.redis_client.hgetall(key)
                    if data:
                        self.in_memory["SELECTOR_STATE"][selector] = {
                            "success": int(data.get("success", 0)),
                            "fail": int(data.get("fail", 0))
                        }
                if self.in_memory["SELECTOR_STATE"]:
                    logger.info(f"✅ Loaded {len(self.in_memory['SELECTOR_STATE'])} selector stats from Redis")
            except Exception as e:
                logger.debug(f"Could not load selector stats from Redis: {e}")
        
        elif self.pg_conn:
            try:
                with self.pg_conn.cursor() as cur:
                    cur.execute("SELECT selector, success_count, fail_count FROM selector_performance")
                    rows = cur.fetchall()
                    for row in rows:
                        self.in_memory["SELECTOR_STATE"][row[0]] = {
                            "success": row[1],
                            "fail": row[2]
                        }
                if self.in_memory["SELECTOR_STATE"]:
                    logger.info(f"✅ Loaded {len(self.in_memory['SELECTOR_STATE'])} selector stats from PostgreSQL")
            except Exception as e:
                logger.debug(f"Could not load selector stats from PostgreSQL: {e}")
    
    def get(self, key: str, default=None):
        parts = key.split(".")
        current = self.in_memory
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current
    
    def set(self, key: str, value: Any):
        parts = key.split(".")
        current = self.in_memory
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        
        # Persist to Redis if available
        if self.redis_client and key.startswith("SELECTOR_STATE."):
            selector = key.replace("SELECTOR_STATE.", "")
            self.redis_client.hset(f"selector:{selector}", mapping=value)
        elif self.pg_conn and key.startswith("SELECTOR_STATE."):
            selector = key.replace("SELECTOR_STATE.", "")
            try:
                with self.pg_conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO selector_performance (selector, success_count, fail_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (selector) 
                        DO UPDATE SET success_count = selector_performance.success_count + %s,
                                      fail_count = selector_performance.fail_count + %s
                    """, (selector, value.get("success", 0), value.get("fail", 0), 
                          value.get("success", 0), value.get("fail", 0)))
                    self.pg_conn.commit()
            except Exception as e:
                logger.debug(f"Could not persist selector stats: {e}")

quantum_memory = QuantumMemory()

# =========================================================
# TENACITY & BACKOFF
# =========================================================

from tenacity import retry, stop_after_attempt, wait_random_exponential
import backoff

# =========================================================
# LIBRARY AVAILABILITY CHECKS
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
    from patchright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
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
    from crawl4ai import AsyncWebCrawler, CacheMode
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

# Persistent browser profile path
USER_DATA_DIR = os.getenv("USER_DATA_DIR", "/tmp/google_profile")
Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

# Debug directory for categorized screenshots
DEBUG_DIR = os.getenv("DEBUG_DIR", "/tmp/scraper_debug")
Path(DEBUG_DIR).mkdir(parents=True, exist_ok=True)
Path(f"{DEBUG_DIR}/captcha").mkdir(parents=True, exist_ok=True)
Path(f"{DEBUG_DIR}/review_panel_missing").mkdir(parents=True, exist_ok=True)
Path(f"{DEBUG_DIR}/review_cards_missing").mkdir(parents=True, exist_ok=True)
Path(f"{DEBUG_DIR}/success").mkdir(parents=True, exist_ok=True)

# =========================================================
# PROXY CONFIGURATION
# =========================================================

PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip()
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()

PROXY_POOL = []
FAILED_PROXIES = set()
COOLDOWN_PROXIES = {}

if PROXY_SERVER:
    proxy_config = {"server": f"http://{PROXY_SERVER}"}
    if PROXY_USERNAME and PROXY_PASSWORD:
        proxy_config["username"] = PROXY_USERNAME
        proxy_config["password"] = PROXY_PASSWORD
    PROXY_POOL.append(proxy_config)

logger.info(f"✅ PROXY COUNT => {len(PROXY_POOL)}")

# =========================================================
# CONCURRENCY
# =========================================================

SCRAPER_SEMAPHORE = asyncio.Semaphore(2)

# =========================================================
# PROVIDER ANNEALING - PRIORITY 10 (Crawl4AI as fallback only)
# =========================================================

class ProviderAnnealer:
    """Provider annealing - Patchright primary, Crawl4AI fallback"""
    
    def __init__(self):
        self.provider_stats = defaultdict(lambda: {"success": 0, "fail": 0})
        self._load_stats()
    
    def _load_stats(self):
        """Load historical provider stats"""
        for provider in ["patchright", "crawl4ai"]:
            stats = quantum_memory.get(f"PROVIDER_STATS.{provider}")
            if stats:
                self.provider_stats[provider] = stats
    
    def should_use_fallback(self, reviews_count: int) -> bool:
        """Priority 10: Only use Crawl4AI if Patchright returns 0 reviews"""
        return reviews_count == 0
    
    def update_provider_stats(self, provider: str, success: bool, reviews_count: int):
        """Update provider statistics"""
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {"success": 0, "fail": 0}
        
        if success and reviews_count > 0:
            self.provider_stats[provider]["success"] += 1
        else:
            self.provider_stats[provider]["fail"] += 1
        
        quantum_memory.set(f"PROVIDER_STATS.{provider}", self.provider_stats[provider])

provider_annealer = ProviderAnnealer()

# =========================================================
# PROXY COOLDOWN
# =========================================================

def is_proxy_in_cooldown(proxy_server: str) -> bool:
    """Check if proxy is in cooldown period"""
    if proxy_server not in COOLDOWN_PROXIES:
        return False
    
    cooldown_until = COOLDOWN_PROXIES[proxy_server]
    if time.time() < cooldown_until:
        return True
    else:
        del COOLDOWN_PROXIES[proxy_server]
        return False

def apply_proxy_cooldown(proxy_server: str, failures: int = 5):
    """Apply cooldown to proxy after repeated failures"""
    if failures >= 5:
        cooldown_hours = 1
        cooldown_until = time.time() + (cooldown_hours * 3600)
        COOLDOWN_PROXIES[proxy_server] = cooldown_until
        quantum_memory.set(f"COOLDOWN_PROXIES.{proxy_server}", cooldown_until)
        logger.warning(f"⚠️ Proxy {proxy_server} cooling down for {cooldown_hours} hour")

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def utc_now():
    return datetime.utcnow()

def quantum_entropy():
    return secrets.randbelow(1000000)

async def quantum_delay():
    entropy = quantum_entropy()
    delay = ((entropy % 3000) / 1000)
    await asyncio.sleep(max(0.5, delay))

def maps_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"

def fallback_reviews_url(place_id: str) -> str:
    """Priority 6: Fallback URL for Google Reviews"""
    return f"https://search.google.com/local/reviews?placeid={place_id}"

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

# =========================================================
# ENHANCED PAGE STATE DIAGNOSTICS - PRIORITY 1
# =========================================================

async def diagnose_page_state(page) -> Dict[str, Any]:
    """Comprehensive page state diagnostics"""
    try:
        title = await page.title()
        url = page.url
        content = await page.content()
        body_length = len(content)
        
        # Detect page type
        page_type = "UNKNOWN"
        if "captcha" in content.lower() or "unusual traffic" in content.lower():
            page_type = "CAPTCHA"
        elif "sorry" in content.lower() or "verify you are human" in content.lower():
            page_type = "BLOCKED"
        elif "google.com/maps" in url:
            page_type = "GOOGLE_MAPS"
        elif "search.google.com/local/reviews" in url:
            page_type = "REVIEWS_PAGE"
        
        # Log everything
        logger.info(f"📊 PAGE TITLE => {title}")
        logger.info(f"📊 PAGE URL => {url}")
        logger.info(f"📊 PAGE TYPE => {page_type}")
        logger.info(f"📊 BODY LENGTH => {body_length} bytes")
        
        # Check for no reviews message - Priority 9
        no_reviews_indicators = [
            "No reviews",
            "Be the first to review",
            "no reviews yet",
            "haven't been reviewed"
        ]
        
        has_no_reviews = any(indicator.lower() in content.lower() for indicator in no_reviews_indicators)
        if has_no_reviews:
            logger.info("📊 BUSINESS HAS NO REVIEWS")
        
        return {
            "title": title,
            "url": url,
            "page_type": page_type,
            "body_length": body_length,
            "has_no_reviews": has_no_reviews,
            "is_captcha": page_type == "CAPTCHA",
            "is_blocked": page_type == "BLOCKED"
        }
    except Exception as e:
        logger.error(f"❌ Page diagnosis error: {e}")
        return {"page_type": "ERROR", "error": str(e)}

# =========================================================
# CATEGORIZED SCREENSHOTS - PRIORITY 8
# =========================================================

async def take_categorized_screenshot(page, place_id: str, category: str):
    """Take categorized screenshot for easier debugging"""
    try:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{DEBUG_DIR}/{category}/{place_id}_{timestamp}.png"
        await page.screenshot(path=filename, full_page=True)
        logger.info(f"📸 Screenshot saved: {category} -> {filename}")
        return filename
    except Exception as e:
        logger.error(f"❌ Screenshot error: {e}")
        return None

# =========================================================
# PROXY SCORING
# =========================================================

def get_advanced_proxy_score(proxy_server: str) -> float:
    """Advanced proxy scoring with cooldown awareness"""
    if is_proxy_in_cooldown(proxy_server):
        return -1.0
    
    stats = quantum_memory.get(f"PROXY_HEALTH.{proxy_server}", {"success": 1, "fail": 1, "captcha": 0})
    
    success_rate = stats["success"] / (stats["success"] + stats["fail"])
    captcha_rate = stats["captcha"] / (stats["success"] + stats["fail"] + stats["captcha"] + 1)
    
    return (success_rate * 0.6) - (captcha_rate * 0.3)

def get_best_proxy():
    try:
        available = [p for p in PROXY_POOL if p["server"] not in FAILED_PROXIES]
        if not available:
            return None
        
        scored = sorted(
            available,
            key=lambda p: get_advanced_proxy_score(p["server"]),
            reverse=True
        )
        return scored[0]
    except Exception:
        return None

def update_proxy_score(proxy_server: str, success: bool, captcha: bool = False):
    """Update proxy score and track failures for cooldown"""
    stats_key = f"PROXY_HEALTH.{proxy_server}"
    stats = quantum_memory.get(stats_key, {"success": 1, "fail": 1, "captcha": 0, "failures_streak": 0})
    
    if success:
        stats["success"] += 1
        stats["failures_streak"] = 0
    else:
        stats["fail"] += 1
        stats["failures_streak"] = stats.get("failures_streak", 0) + 1
        
        if stats["failures_streak"] >= 5:
            apply_proxy_cooldown(proxy_server, stats["failures_streak"])
    
    if captcha:
        stats["captcha"] += 1
    
    quantum_memory.set(stats_key, stats)

# =========================================================
# SELECTOR OPTIMIZER - WITH PERSISTENCE (PRIORITY 5 FIXED)
# =========================================================

class SelectorOptimizer:
    """Self-healing selector system with persistence"""
    def __init__(self):
        # Load from quantum memory (already loaded in QuantumMemory.__init__)
        self.selector_stats = quantum_memory.get("SELECTOR_STATE", {})
        logger.info(f"✅ SelectorOptimizer loaded with {len(self.selector_stats)} existing selectors")
    
    def update(self, selector: str, success: bool):
        if selector not in self.selector_stats:
            self.selector_stats[selector] = {"success": 0, "fail": 0}
        
        if success:
            self.selector_stats[selector]["success"] += 1
        else:
            self.selector_stats[selector]["fail"] += 1
        
        quantum_memory.set(f"SELECTOR_STATE.{selector}", self.selector_stats[selector])
    
    def get_success_rate(self, selector: str) -> float:
        stats = self.selector_stats.get(selector, {"success": 0, "fail": 0})
        total = stats["success"] + stats["fail"]
        return stats["success"] / total if total > 0 else 0.5
    
    def sort_by_success_rate(self, selectors: List[str]) -> List[str]:
        return sorted(selectors, key=lambda s: self.get_success_rate(s), reverse=True)

selector_optimizer = SelectorOptimizer()

# =========================================================
# REVIEW NORMALIZATION
# =========================================================

def generate_review_id(place_id: str, author: str, text: str, date: str = ""):
    raw = f"{place_id}:{author}:{text}:{date}"
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
        
        review_date = review.get("review_date", "")
        owner_response = review.get("owner_response", "")
        owner_response_date = review.get("owner_response_date", "")
        likes_count = review.get("likes_count", 0)
        is_local_guide = review.get("is_local_guide", False)
        author_review_count = review.get("author_review_count", 0)
        
        return {
            "google_review_id": generate_review_id(place_id, author, review_text, review_date),
            "author": author,
            "author_name": author,
            "rating": rating,
            "review_text": review_text,
            "content": review_text,
            "text": review_text,
            "review_date": review_date,
            "owner_response": owner_response,
            "owner_response_date": owner_response_date,
            "likes_count": likes_count,
            "is_local_guide": is_local_guide,
            "author_review_count": author_review_count,
            "sentiment_score": 0.5,
            "google_review_time": utc_now() if not review_date else review_date,
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

# =========================================================
# ENHANCED REVIEW BUTTON DETECTION - PRIORITY 2
# =========================================================

async def click_reviews_button(page) -> bool:
    """Enhanced review button detection with verification"""
    
    review_button_selectors = [
        'button[jsaction*="pane.reviewChart.moreReviews"]',
        'button[aria-label*="reviews"]',
        'button[aria-label*="Reviews"]',
        'button[aria-label*="Review"]',
        'button[jsaction*="reviews"]',
        'button[data-tab-index="1"]',
        '[role="tab"][aria-label*="Reviews"]',
        '[data-value="Reviews"]',
        'button[jsaction*="pane.rating.moreReviews"]',
        'button[aria-label*="Google reviews"]',
        'button[role="tab"]',
        'a[aria-label*="reviews"]'
    ]
    
    sorted_selectors = selector_optimizer.sort_by_success_rate(review_button_selectors)
    
    for selector in sorted_selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                await locator.click()
                selector_optimizer.update(selector, True)
                logger.info(f"✅ CLICKED REVIEW BUTTON => {selector}")
                
                # Priority 2: Wait and log URL after click
                await page.wait_for_timeout(5000)
                logger.info(f"📊 URL AFTER CLICK => {page.url}")
                
                return True
        except Exception as e:
            selector_optimizer.update(selector, False)
            logger.debug(f"Selector {selector} failed: {e}")
    
    logger.error("❌ NO REVIEW BUTTON FOUND")
    return False

# =========================================================
# REVIEW PANEL DETECTION - PRIORITY 3
# =========================================================

async def verify_review_panel(page) -> bool:
    """Verify that review panel exists before scrolling"""
    try:
        panel_exists = await page.evaluate("""
            () => {
                const panel = document.querySelector('.m6QErb');
                if (panel) return true;
                const panels = document.querySelectorAll('[role="main"]');
                return panels.length > 0;
            }
        """)
        
        logger.info(f"📊 REVIEW PANEL FOUND => {panel_exists}")
        
        if not panel_exists:
            await take_categorized_screenshot(page, "unknown", "review_panel_missing")
        
        return panel_exists
    except Exception as e:
        logger.error(f"❌ Panel verification error: {e}")
        return False

# =========================================================
# REVIEW SCROLLING - FIXED
# =========================================================

async def scroll_reviews_page(page) -> int:
    """Improved scrolling using the correct .m6QErb panel"""
    scroll_count = 0
    try:
        for _ in range(30):  # Max 30 scroll attempts
            result = await page.evaluate("""
                () => {
                    const panel = document.querySelector('.m6QErb');
                    if (panel) {
                        const previousHeight = panel.scrollHeight;
                        panel.scrollTop = panel.scrollHeight;
                        return { success: true, previousHeight, newHeight: panel.scrollHeight };
                    }
                    
                    const panels = document.querySelectorAll('[role="main"]');
                    for (const p of panels) {
                        const previousHeight = p.scrollHeight;
                        p.scrollTop = p.scrollHeight;
                        return { success: true, previousHeight, newHeight: p.scrollHeight };
                    }
                    return { success: false };
                }
            """)
            
            if isinstance(result, dict) and result.get('success'):
                scroll_count += 1
                await asyncio.sleep(1.5)
            else:
                break
        
        logger.info(f"📊 SCROLL COUNT => {scroll_count}")
        return scroll_count
    except Exception as e:
        logger.error(f"❌ Scroll error: {e}")
        return scroll_count

# =========================================================
# EXPAND TRUNCATED REVIEWS
# =========================================================

async def expand_truncated_reviews(page) -> int:
    """Expand all truncated reviews"""
    try:
        expand_selectors = [
            'button:has-text("More")',
            'button:has-text("more")',
            'span:has-text("More")',
            'button:has-text("Read more")',
            'span:has-text("Read more")',
            'span.w8nwRe',
            'button[jsaction*="expand"]'
        ]
        
        expanded_count = 0
        for selector in expand_selectors:
            try:
                buttons = await page.locator(selector).all()
                for button in buttons:
                    try:
                        await button.click()
                        expanded_count += 1
                        await asyncio.sleep(0.3)
                    except:
                        pass
            except:
                pass
        
        if expanded_count > 0:
            logger.info(f"✅ Expanded {expanded_count} truncated reviews")
        
        return expanded_count
    except Exception as e:
        logger.error(f"❌ Expand reviews error: {e}")
        return 0

# =========================================================
# DOM SNAPSHOT BEFORE PARSING - PRIORITY 4
# =========================================================

async def get_review_card_count(page) -> int:
    """Get raw review card count before parsing"""
    try:
        selectors_to_try = [
            'div[data-review-id]',
            'div.jftiEf',
            'div.MyEned',
            'div[role="article"]',
            'div[class*="review"]'
        ]
        
        for selector in selectors_to_try:
            count = await page.locator(selector).count()
            if count > 0:
                logger.info(f"📊 RAW REVIEW CARDS => {count} (using selector: {selector})")
                return count
        
        logger.warning("📊 RAW REVIEW CARDS => 0")
        return 0
    except Exception as e:
        logger.error(f"❌ Card count error: {e}")
        return 0

# =========================================================
# TRUE CONSENSUS ENGINE - PRIORITY 7 (Playwright DOM + Selectolax + BeautifulSoup)
# =========================================================

async def true_consensus_engine(page, place_id: str) -> List[Dict]:
    """True 2-of-3 consensus using Playwright DOM + Selectolax + BeautifulSoup"""
    
    results = {}
    
    # Source 1: Playwright DOM (live browser)
    try:
        playwright_reviews = []
        review_cards = await page.locator('div[data-review-id], div.jftiEf, div.MyEned').all()
        
        for card in review_cards[:MAX_REVIEWS]:
            try:
                author = "Anonymous"
                for sel in ['.d4r55', '.TSUbDb', 'span[class*=author]']:
                    if await card.locator(sel).count() > 0:
                        author = (await card.locator(sel).first.inner_text()).strip()
                        break
                
                text = ""
                for sel in ['.wiI7pd', '.MyEned', 'span[jsname]']:
                    if await card.locator(sel).count() > 0:
                        text = (await card.locator(sel).first.inner_text()).strip()
                        break
                
                rating = 5
                if await card.locator('span.kvMYJc').count() > 0:
                    aria = await card.locator('span.kvMYJc').get_attribute('aria-label')
                    if aria:
                        match = re.search(r'(\d)', aria)
                        if match:
                            rating = int(match.group(1))
                
                date = ""
                for sel in ['.rsqaWe', '.DeaRdd']:
                    if await card.locator(sel).count() > 0:
                        date = (await card.locator(sel).first.inner_text()).strip()
                        break
                
                normalized = normalize_review({
                    "author": author, "rating": rating, "review_text": text, "review_date": date
                }, place_id)
                if normalized:
                    playwright_reviews.append(normalized)
            except:
                continue
        
        results["playwright"] = playwright_reviews
        logger.info(f"📊 PLAYWRIGHT DOM REVIEWS => {len(playwright_reviews)}")
    except Exception as e:
        logger.error(f"❌ Playwright DOM extraction error: {e}")
    
    # Source 2 & 3: Selectolax and BeautifulSoup on HTML
    html = await page.content()
    
    if SELECTOLAX_AVAILABLE:
        try:
            parser = HTMLParser(html)
            selectolax_reviews = []
            review_nodes = parser.css('div[data-review-id], div.jftiEf, div.MyEned')
            
            for node in review_nodes[:MAX_REVIEWS]:
                author_node = node.css_first('.d4r55, .TSUbDb')
                author = author_node.text(strip=True) if author_node else "Anonymous"
                
                text_node = node.css_first('.wiI7pd, .MyEned')
                text = text_node.text(strip=True) if text_node else ""
                
                rating = 5
                rating_node = node.css_first('span.kvMYJc')
                if rating_node and rating_node.attributes.get('aria-label'):
                    match = re.search(r'(\d)', rating_node.attributes['aria-label'])
                    if match:
                        rating = int(match.group(1))
                
                date_node = node.css_first('.rsqaWe, .DeaRdd')
                date = date_node.text(strip=True) if date_node else ""
                
                normalized = normalize_review({
                    "author": author, "rating": rating, "review_text": text, "review_date": date
                }, place_id)
                if normalized:
                    selectolax_reviews.append(normalized)
            
            results["selectolax"] = selectolax_reviews
            logger.info(f"📊 SELECTOLAX REVIEWS => {len(selectolax_reviews)}")
        except Exception as e:
            logger.error(f"❌ Selectolax error: {e}")
    
    if BS4_AVAILABLE:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            bs4_reviews = []
            review_elements = soup.select('div[data-review-id], div.jftiEf, div.MyEned')
            
            for elem in review_elements[:MAX_REVIEWS]:
                author_elem = elem.select_one('.d4r55, .TSUbDb')
                author = author_elem.get_text(strip=True) if author_elem else "Anonymous"
                
                text_elem = elem.select_one('.wiI7pd, .MyEned')
                text = text_elem.get_text(strip=True) if text_elem else ""
                
                rating = 5
                rating_elem = elem.select_one('span.kvMYJc')
                if rating_elem and rating_elem.get('aria-label'):
                    match = re.search(r'(\d)', rating_elem['aria-label'])
                    if match:
                        rating = int(match.group(1))
                
                date_elem = elem.select_one('.rsqaWe, .DeaRdd')
                date = date_elem.get_text(strip=True) if date_elem else ""
                
                normalized = normalize_review({
                    "author": author, "rating": rating, "review_text": text, "review_date": date
                }, place_id)
                if normalized:
                    bs4_reviews.append(normalized)
            
            results["beautifulsoup"] = bs4_reviews
            logger.info(f"📊 BEAUTIFULSOUP REVIEWS => {len(bs4_reviews)}")
        except Exception as e:
            logger.error(f"❌ BeautifulSoup error: {e}")
    
    # True 2-of-3 consensus
    review_votes = defaultdict(lambda: {"votes": 0, "review": None})
    
    for source_name, reviews in results.items():
        for review in
