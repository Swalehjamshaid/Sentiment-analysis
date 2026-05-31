# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE GOOGLE REVIEW SCRAPER - V17.0
# ENTERPRISE GRADE WITH FULL DIAGNOSTICS & QUANTUM MODE
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
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from functools import lru_cache

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("=" * 70)
print("🚀 QUANTUM ENTERPRISE SCRAPER V17.0 - QUANTUM MODE ACTIVE")
print("=" * 70)

# =========================================================
# CACHE
# =========================================================

from cachetools import TTLCache

review_cache = TTLCache(maxsize=2000, ttl=3600)

# =========================================================
# TENACITY & BACKOFF
# =========================================================

from tenacity import retry, stop_after_attempt, wait_random_exponential
import backoff

# =========================================================
# IMPROVEMENT #9: DIAGNOSTICS STORAGE
# =========================================================

DIAGNOSTICS_DIR = os.getenv("DIAGNOSTICS_DIR", "/tmp/scraper_diagnostics")
Path(DIAGNOSTICS_DIR).mkdir(parents=True, exist_ok=True)

class DiagnosticsStore:
    """Store scraper diagnostics in JSON for historical analysis"""
    
    def __init__(self):
        self.diagnostics_file = Path(DIAGNOSTICS_DIR) / "scraper_diagnostics.json"
        self.diagnostics = []
        self._load()
    
    def _load(self):
        if self.diagnostics_file.exists():
            try:
                with open(self.diagnostics_file, 'r') as f:
                    self.diagnostics = json.load(f)
            except:
                self.diagnostics = []
    
    def save(self, entry: Dict):
        self.diagnostics.append(entry)
        # Keep last 1000 entries
        if len(self.diagnostics) > 1000:
            self.diagnostics = self.diagnostics[-1000:]
        with open(self.diagnostics_file, 'w') as f:
            json.dump(self.diagnostics, f, indent=2)
    
    def get_summary(self) -> Dict:
        if not self.diagnostics:
            return {"total_scrapes": 0}
        
        total = len(self.diagnostics)
        successful = sum(1 for d in self.diagnostics if d.get('reviews_found', 0) > 0)
        captcha_count = sum(1 for d in self.diagnostics if d.get('captcha_detected', False))
        
        return {
            "total_scrapes": total,
            "successful_scrapes": successful,
            "success_rate": successful / total if total > 0 else 0,
            "captcha_rate": captcha_count / total if total > 0 else 0,
            "avg_reviews": sum(d.get('reviews_found', 0) for d in self.diagnostics) / total if total > 0 else 0
        }

diagnostics_store = DiagnosticsStore()

# =========================================================
# LIBRARY AVAILABILITY
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

SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "300"))
MAX_REVIEWS = int(os.getenv("SCRAPER_MAX_REVIEWS", "100"))
HEADLESS_MODE = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"

USER_DATA_DIR = os.getenv("USER_DATA_DIR", "/tmp/chrome_profile")
Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

# =========================================================
# IMPROVEMENT #1 & #3: DEBUG DIRECTORY
# =========================================================

DEBUG_DIR = os.getenv("DEBUG_DIR", "/tmp/scraper_debug")
Path(DEBUG_DIR).mkdir(parents=True, exist_ok=True)
for subdir in ["screenshots", "html", "captcha", "no_reviews", "success"]:
    Path(f"{DEBUG_DIR}/{subdir}").mkdir(parents=True, exist_ok=True)

# =========================================================
# PROXY CONFIGURATION WITH ADVANCED SCORING
# =========================================================

PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip()
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()

PROXY_POOL = []
FAILED_PROXIES = set()
PROXY_HEALTH = {}

# Support multiple proxies
if "," in PROXY_SERVER:
    for proxy in PROXY_SERVER.split(","):
        proxy = proxy.strip()
        if proxy:
            PROXY_POOL.append({
                "server": f"http://{proxy}",
                "username": PROXY_USERNAME,
                "password": PROXY_PASSWORD
            })
elif PROXY_SERVER:
    PROXY_POOL.append({
        "server": f"http://{PROXY_SERVER}",
        "username": PROXY_USERNAME,
        "password": PROXY_PASSWORD
    })

logger.info(f"✅ PROXY COUNT => {len(PROXY_POOL)}")

# =========================================================
# IMPROVEMENT #4: ADVANCED PROXY SCORING WITH LATENCY
# =========================================================

def score_proxy_advanced(proxy_server: str) -> float:
    """Advanced proxy scoring with success rate, captcha rate, and latency"""
    stats = PROXY_HEALTH.get(proxy_server, {
        "success": 1, 
        "fail": 1, 
        "captcha": 0,
        "response_times": [1.0]  # Default latency
    })
    
    total = stats["success"] + stats["fail"]
    success_rate = stats["success"] / total if total > 0 else 0.5
    
    captcha_total = stats["captcha"] + stats["success"] + stats["fail"]
    captcha_rate = stats["captcha"] / captcha_total if captcha_total > 0 else 0
    
    # Calculate average latency
    response_times = stats.get("response_times", [1.0])
    avg_latency = sum(response_times) / len(response_times) if response_times else 1.0
    latency_score = min(avg_latency / 10, 0.5)  # Normalize latency to 0-0.5
    
    # Weighted score: 60% success, 30% captcha penalty, 10% latency
    score = (success_rate * 0.6) - (captcha_rate * 0.3) - (latency_score * 0.1)
    
    return max(0, min(1, score))

def update_proxy_score_advanced(proxy_server: str, success: bool, captcha: bool = False, response_time: float = 0):
    """Update proxy health with response time tracking"""
    if proxy_server not in PROXY_HEALTH:
        PROXY_HEALTH[proxy_server] = {
            "success": 1, 
            "fail": 1, 
            "captcha": 0,
            "response_times": []
        }
    
    stats = PROXY_HEALTH[proxy_server]
    
    if success:
        stats["success"] += 1
    else:
        stats["fail"] += 1
    
    if captcha:
        stats["captcha"] += 1
    
    if response_time > 0:
        stats["response_times"].append(response_time)
        # Keep last 50 response times
        if len(stats["response_times"]) > 50:
            stats["response_times"] = stats["response_times"][-50:]

def get_best_proxy_advanced():
    """Get best proxy based on advanced scoring"""
    try:
        available = [p for p in PROXY_POOL if p["server"] not in FAILED_PROXIES]
        if not available:
            return None
        
        scored = sorted(
            available, 
            key=lambda p: score_proxy_advanced(p["server"]), 
            reverse=True
        )
        return scored[0]
    except Exception:
        return None

# =========================================================
# IMPROVEMENT #8: VALIDATE PLACE ID
# =========================================================

def validate_place_id(place_id: str) -> Tuple[bool, str]:
    """Validate place ID before scraping"""
    
    if not place_id:
        return False, "Empty place_id"
    
    if len(place_id) < 20:
        return False, f"Place ID too short: {len(place_id)} chars (expected 20+)"
    
    # Google Place IDs typically contain letters, numbers, and underscores
    if not re.match(r'^[A-Za-z0-9_\-]+$', place_id):
        return False, f"Invalid characters in place_id: {place_id}"
    
    return True, "Valid"

# =========================================================
# CONCURRENCY
# =========================================================

SCRAPER_SEMAPHORE = asyncio.Semaphore(2)

# =========================================================
# ENHANCED DIAGNOSTICS WITH SCREENSHOT CAPTURE
# =========================================================

class ScrapeDiagnostics:
    """Track detailed scrape diagnostics with screenshot capture"""
    
    def __init__(self, place_id: str):
        self.place_id = place_id
        self.start_time = datetime.now()
        self.steps = []
        self.errors = []
        self.reviews_found = 0
        self.captcha_detected = False
        self.button_clicked = False
        self.panel_found = False
        self.cards_found = 0
        self.page_title = ""
        self.page_url = ""
    
    async def capture_page_state(self, page, stage: str):
        """IMPROVEMENT #1: Capture screenshot and HTML when no reviews found"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Capture screenshot
        screenshot_path = f"{DEBUG_DIR}/screenshots/{self.place_id}_{stage}_{timestamp}.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"📸 Screenshot saved: {screenshot_path}")
        
        # Capture HTML
        html = await page.content()
        html_path = f"{DEBUG_DIR}/html/{self.place_id}_{stage}_{timestamp}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"📄 HTML saved: {html_path}")
        
        # Capture page title and URL
        self.page_title = await page.title()
        self.page_url = page.url
        logger.info(f"📊 PAGE TITLE: {self.page_title}")
        logger.info(f"📊 PAGE URL: {self.page_url}")
        
        return {
            "screenshot": screenshot_path,
            "html": html_path,
            "title": self.page_title,
            "url": self.page_url
        }
    
    def add_step(self, step: str, success: bool = True, details: str = None):
        self.steps.append({
            "step": step,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        if not success:
            logger.warning(f"⚠️ STEP FAILED: {step} - {details}")
        else:
            logger.info(f"✅ STEP PASSED: {step}")
    
    def add_error(self, error: str):
        self.errors.append(error)
        logger.error(f"❌ ERROR: {error}")
    
    def log_summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        logger.info("=" * 50)
        logger.info(f"📊 SCRAPE SUMMARY for {self.place_id}")
        logger.info(f"   Duration: {duration:.2f}s")
        logger.info(f"   Reviews found: {self.reviews_found}")
        logger.info(f"   Steps passed: {sum(1 for s in self.steps if s['success'])}/{len(self.steps)}")
        logger.info(f"   Button clicked: {self.button_clicked}")
        logger.info(f"   Panel found: {self.panel_found}")
        logger.info(f"   Cards found: {self.cards_found}")
        logger.info(f"   Captcha: {self.captcha_detected}")
        logger.info(f"   Page Title: {self.page_title[:100] if self.page_title else 'N/A'}")
        if self.errors:
            logger.info(f"   Errors: {len(self.errors)}")
        logger.info("=" * 50)
        
        # IMPROVEMENT #9: Store diagnostics in JSON
        diagnostics_store.save({
            "place_id": self.place_id,
            "timestamp": self.start_time.isoformat(),
            "duration": duration,
            "reviews_found": self.reviews_found,
            "steps_passed": sum(1 for s in self.steps if s['success']),
            "total_steps": len(self.steps),
            "button_clicked": self.button_clicked,
            "panel_found": self.panel_found,
            "cards_found": self.cards_found,
            "captcha_detected": self.captcha_detected,
            "page_title": self.page_title[:200] if self.page_title else "",
            "errors": self.errors[:5]
        })

# =========================================================
# ENHANCED CAPTCHA DETECTION
# =========================================================

def detect_captcha_enhanced(html: str) -> Tuple[bool, str]:
    """Enhanced CAPTCHA detection with type identification"""
    html_lower = html.lower()
    
    patterns = [
        ("captcha", "captcha"),
        ("unusual traffic", "traffic"),
        ("not a robot", "robot"),
        ("sorry", "sorry"),
        ("verify you are human", "verify"),
        ("security check", "security"),
        ("access denied", "denied"),
        ("automated queries", "automated"),
        ("rate limit", "rate"),
        ("too many requests", "too_many"),
        ("blocked", "blocked")
    ]
    
    for pattern, name in patterns:
        if pattern in html_lower:
            return True, name
    
    return False, None

# =========================================================
# HELPERS
# =========================================================

def utc_now():
    return datetime.utcnow()

def quantum_entropy():
    return secrets.randbelow(1000000)

async def quantum_delay():
    entropy = quantum_entropy()
    delay = (entropy % 3000) / 1000
    await asyncio.sleep(max(0.5, delay))

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

# =========================================================
# IMPROVEMENT #6: REVIEW EXPANSION
# =========================================================

async def expand_truncated_reviews(page) -> int:
    """Expand truncated reviews by clicking 'More' and 'Read more' buttons"""
    
    expanded_count = 0
    
    expand_selectors = [
        'button:has-text("More")',
        'button:has-text("more")',
        'span:has-text("More")',
        'button:has-text("Read more")',
        'span:has-text("Read more")',
        'span.w8nwRe',
        'button[jsaction*="expand"]',
        'button[aria-label*="expand"]'
    ]
    
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

# =========================================================
# IMPROVEMENT #7: ROLE-BASED EXTRACTION
# =========================================================

async def extract_reviews_role_based(page, diagnostics: ScrapeDiagnostics) -> List[Dict]:
    """Extract reviews using role-based selectors (more stable)"""
    
    reviews = []
    
    # Priority 1: Role-based selectors (most stable)
    role_selectors = [
        '[role="article"]',
        '[data-review-id]',
        '[aria-label*="review" i]'
    ]
    
    # Priority 2: Class-based selectors (fallback)
    class_selectors = [
        'div.jftiEf',
        'div.MyEned',
        'div[class*="review"]'
    ]
    
    all_selectors = role_selectors + class_selectors
    
    for selector in all_selectors:
        try:
            cards = await page.locator(selector).all()
            if cards:
                logger.info(f"📊 Found {len(cards)} cards using: {selector}")
                
                for card in cards[:MAX_REVIEWS]:
                    try:
                        # Extract author using multiple methods
                        author = "Anonymous"
                        author_selectors = [
                            '[data-author-name]',
                            '.d4r55', 
                            '.TSUbDb', 
                            'span[class*="author"]'
                        ]
                        for sel in author_selectors:
                            if await card.locator(sel).count() > 0:
                                author = (await card.locator(sel).first.inner_text()).strip()
                                break
                        
                        # Extract text
                        text = ""
                        text_selectors = [
                            '[data-review-text]',
                            '.wiI7pd', 
                            '.MyEned', 
                            'span[jsname]'
                        ]
                        for sel in text_selectors:
                            if await card.locator(sel).count() > 0:
                                text = (await card.locator(sel).first.inner_text()).strip()
                                break
                        
                        if not text:
                            continue
                        
                        # Extract rating
                        rating = 5
                        rating_locator = card.locator('span.kvMYJc')
                        if await rating_locator.count() > 0:
                            aria = await rating_locator.get_attribute("aria-label")
                            if aria:
                                match = re.search(r'(\d)', aria)
                                if match:
                                    rating = int(match.group(1))
                        
                        normalized = normalize_review({
                            "author": author,
                            "rating": rating,
                            "review_text": text
                        }, diagnostics.place_id)
                        
                        if normalized:
                            reviews.append(normalized)
                            
                    except Exception as e:
                        logger.debug(f"Card parse error: {e}")
                
                if reviews:
                    break
        except:
            continue
    
    return reviews

# =========================================================
# REVIEW NORMALIZATION
# =========================================================

def generate_review_id(place_id: str, author: str, text: str):
    raw = f"{place_id}:{author}:{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def normalize_review(review: Dict[str, Any], place_id: str):
    try:
        review_text = str(review.get("review_text", review.get("text", review.get("content", "")))).strip()
        if not review_text or len(review_text) < 3:
            return None

        author = str(review.get("author", review.get("author_name", "Anonymous"))).strip()
        if not author or len(author) > 100:
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

# =========================================================
# REVIEW BUTTON CLICKING - ENHANCED
# =========================================================

async def click_reviews_button_enhanced(page, diagnostics: ScrapeDiagnostics) -> bool:
    """Enhanced button clicking with multiple strategies"""
    
    button_selectors = [
        'button[jsaction*="pane.reviewChart.moreReviews"]',
        'button[aria-label*="reviews"]',
        'button[aria-label*="Reviews"]',
        'button[data-tab-index="1"]',
        '[role="tab"][aria-label*="Reviews"]',
        '[data-value="Reviews"]',
        'button[jsaction*="pane.rating.moreReviews"]',
        'button[aria-label*="Google reviews"]'
    ]
    
    for selector in button_selectors:
        try:
            button = page.locator(selector).first
            if await button.count() > 0:
                await button.click()
                diagnostics.button_clicked = True
                diagnostics.add_step("click_reviews_button", True, f"Selector: {selector}")
                logger.info(f"✅ CLICKED REVIEW BUTTON: {selector}")
                await asyncio.sleep(3)
                return True
        except Exception as e:
            continue
    
    diagnostics.add_step("click_reviews_button", False, "No button found")
    return False

# =========================================================
# REVIEW PANEL DETECTION - ENHANCED
# =========================================================

async def find_review_panel_enhanced(page, diagnostics: ScrapeDiagnostics) -> bool:
    """Enhanced panel detection with multiple strategies"""
    
    panel_selectors = [
        (".m6QErb", "classic"),
        ("[role='main']", "main"),
        (".section-scrollbox", "scrollbox"),
        ("[role='dialog'] .m6QErb", "dialog"),
        ("div[aria-label*='Reviews']", "aria")
    ]
    
    for selector, name in panel_selectors:
        try:
            panel = await page.evaluate(f"""
                () => {{
                    const el = document.querySelector('{selector}');
                    return !!el;
                }}
            """)
            if panel:
                diagnostics.panel_found = True
                diagnostics.add_step("find_review_panel", True, f"Selector: {selector} ({name})")
                logger.info(f"✅ REVIEW PANEL FOUND: {name}")
                return True
        except:
            continue
    
    diagnostics.add_step("find_review_panel", False, "No panel found")
    return False

# =========================================================
# REVIEW SCROLLING - ENHANCED
# =========================================================

async def scroll_reviews_enhanced(page, max_scrolls: int = 25) -> int:
    """Enhanced scrolling with proper panel detection"""
    
    scroll_count = 0
    last_height = 0
    no_change_count = 0
    
    for i in range(max_scrolls):
        try:
            result = await page.evaluate("""
                () => {
                    const panel = document.querySelector('.m6QErb') || 
                                 document.querySelector('[role="main"]') ||
                                 document.querySelector('.section-scrollbox');
                    
                    if (panel) {
                        const currentHeight = panel.scrollHeight;
                        panel.scrollTop = panel.scrollHeight;
                        return { success: true, height: currentHeight };
                    }
                    return { success: false };
                }
            """)
            
            if result and result.get('success'):
                current_height = result.get('height', 0)
                if current_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        break
                else:
                    no_change_count = 0
                    last_height = current_height
                
                scroll_count += 1
                await asyncio.sleep(random.uniform(1.0, 1.5))
            else:
                break
        except:
            break
    
    logger.info(f"📊 SCROLLED {scroll_count} times")
    return scroll_count

# =========================================================
# IMPROVEMENT #10: QUANTUM MULTI-PROVIDER EXECUTION
# =========================================================

async def crawl4ai_quantum(place_id: str, diagnostics: ScrapeDiagnostics) -> List[Dict]:
    """Crawl4AI provider for quantum mode"""
    
    reviews = []
    
    if not CRAWL4AI_AVAILABLE:
        return reviews
    
    try:
        logger.info("🔄 [QUANTUM] Starting Crawl4AI provider...")
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=maps_url(place_id),
                bypass_cache=True,
                wait_until="networkidle"
            )
            
            if result and result.html:
                if BS4_AVAILABLE:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    review_elements = soup.select('div[data-review-id], div.jftiEf, div.MyEned')
                    
                    for elem in review_elements[:MAX_REVIEWS]:
                        text_elem = elem.select_one('.wiI7pd, .MyEned')
                        if text_elem:
                            text = text_elem.get_text(strip=True)
                            if text:
                                review = normalize_review({
                                    "author": "Anonymous",
                                    "rating": 5,
                                    "review_text": text
                                }, place_id)
                                if review:
                                    reviews.append(review)
        
        if reviews:
            logger.info(f"✅ [QUANTUM] Crawl4AI found {len(reviews)} reviews")
        else:
            logger.info("⚠️ [QUANTUM] Crawl4AI found no reviews")
            
    except Exception as e:
        logger.debug(f"Crawl4AI quantum error: {e}")
    
    return reviews

async def curl_quantum(place_id: str, diagnostics: ScrapeDiagnostics) -> List[Dict]:
    """Curl-CFFI provider for quantum mode"""
    
    reviews = []
    
    if not CURL_CFFI_AVAILABLE:
        return reviews
    
    try:
        logger.info("🔄 [QUANTUM] Starting Curl-CFFI provider...")
        response = curl_requests.get(
            maps_url(place_id),
            headers={"User-Agent": get_user_agent()},
            timeout=30
        )
        
        if response.status_code == 200 and BS4_AVAILABLE:
            soup = BeautifulSoup(response.text, 'html.parser')
            review_elements = soup.select('div[data-review-id], div.jftiEf')
            
            for elem in review_elements[:MAX_REVIEWS]:
                text_elem = elem.select_one('.wiI7pd, .MyEned')
                if text_elem:
                    text = text_elem.get_text(strip=True)
                    if text:
                        review = normalize_review({
                            "author": "Anonymous",
                            "rating": 5,
                            "review_text": text
                        }, place_id)
                        if review:
                            reviews.append(review)
        
        if reviews:
            logger.info(f"✅ [QUANTUM] Curl-CFFI found {len(reviews)} reviews")
            
    except Exception as e:
        logger.debug(f"Curl quantum error: {e}")
    
    return reviews

# =========================================================
# MAIN PATCHRIGHT PROVIDER - ENHANCED
# =========================================================

@backoff.on_exception(backoff.expo, Exception, max_time=300)
async def patchright_reviews_enhanced(place_id: str, diagnostics: ScrapeDiagnostics) -> List[Dict]:
    """Enhanced Patchright with full diagnostics and screenshot capture"""
    
    reviews = []
    
    if not PATCHRIGHT_AVAILABLE:
        diagnostics.add_error("Patchright not available")
        return reviews
    
    async with SCRAPER_SEMAPHORE:
        context = None
        start_time = time.time()
        
        for attempt in range(3):
            proxy = get_best_proxy_advanced()
            proxy_start = time.time()
            
            try:
                logger.info(f"🔥 PATCHRIGHT ATTEMPT => {attempt+1}")
                
                # IMPROVEMENT #3: Browser launch diagnostics
                logger.info("🚀 LAUNCHING PATCHRIGHT BROWSER")
                logger.info(f"   User Data Dir: {USER_DATA_DIR}")
                logger.info(f"   Proxy: {proxy['server'] if proxy else 'None'}")
                logger.info(f"   Headless: {HEADLESS_MODE}")
                
                async with async_playwright() as p:
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir=USER_DATA_DIR,
                        headless=HEADLESS_MODE,
                        proxy=proxy,
                        channel="chromium",
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--window-size=1920,1080",
                            "--no-sandbox"
                        ]
                    )
                    
                    logger.info("✅ PATCHRIGHT BROWSER LAUNCHED SUCCESSFULLY")
                    
                    page = context.pages[0] if context.pages else await context.new_page()
                    
                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)
                    
                    if STEALTH_AVAILABLE:
                        try:
                            await stealth_async(page)
                        except:
                            pass
                    
                    # Navigate to page
                    target_url = maps_url(place_id)
                    logger.info(f"🌐 TARGET URL => {target_url}")
                    diagnostics.add_step("navigate", True, target_url)
                    
                    response = await page.goto(target_url, wait_until="networkidle", timeout=60000)
                    
                    if response and response.status >= 400:
                        diagnostics.add_step("navigate", False, f"HTTP {response.status}")
                        continue
                    
                    await asyncio.sleep(random.randint(2, 4))
                    
                    # IMPROVEMENT #2: Log page title
                    page_title = await page.title()
                    diagnostics.page_title = page_title
                    logger.info(f"📊 PAGE TITLE: {page_title}")
                    
                    # Check for CAPTCHA
                    html = await page.content()
                    is_captcha, captcha_type = detect_captcha_enhanced(html)
                    if is_captcha:
                        diagnostics.captcha_detected = True
                        diagnostics.add_step("captcha_check", False, captcha_type)
                        
                        # Capture screenshot for CAPTCHA
                        captcha_path = f"{DEBUG_DIR}/captcha/{place_id}_{captcha_type}.png"
                        await page.screenshot(path=captcha_path, full_page=True)
                        logger.info(f"📸 CAPTCHA screenshot saved: {captcha_path}")
                        
                        if proxy:
                            update_proxy_score_advanced(proxy["server"], False, captcha=True, response_time=time.time() - proxy_start)
                        continue
                    
                    diagnostics.add_step("captcha_check", True)
                    
                    # Click reviews button
                    button_clicked = await click_reviews_button_enhanced(page, diagnostics)
                    if not button_clicked:
                        diagnostics.add_step("button_click", False, "Could not find button")
                        await diagnostics.capture_page_state(page, "no_button")
                        continue
                    
                    await asyncio.sleep(3)
                    
                    # Find review panel
                    panel_found = await find_review_panel_enhanced(page, diagnostics)
                    if not panel_found:
                        diagnostics.add_step("panel_found", False, "No panel detected")
                        await diagnostics.capture_page_state(page, "no_panel")
                        continue
                    
                    # Scroll to load reviews
                    scrolls = await scroll_reviews_enhanced(page, max_scrolls=20)
                    diagnostics.add_step("scrolling", True, f"{scrolls} scrolls")
                    
                    # IMPROVEMENT #6: Expand truncated reviews
                    expanded = await expand_truncated_reviews(page)
                    if expanded > 0:
                        logger.info(f"📊 Expanded {expanded} truncated reviews")
                    
                    await asyncio.sleep(2)
                    
                    # IMPROVEMENT #7: Role-based extraction
                    reviews = await extract_reviews_role_based(page, diagnostics)
                    
                    diagnostics.reviews_found = len(reviews)
                    diagnostics.add_step("extract_reviews", True, f"{len(reviews)} reviews")
                    
                    logger.info(f"✅ EXTRACTED {len(reviews)} REVIEWS")
                    
                    response_time = time.time() - proxy_start
                    if proxy:
                        update_proxy_score_advanced(proxy["server"], len(reviews) > 0, response_time=response_time)
                    
                    # Capture success state
                    if reviews:
                        await diagnostics.capture_page_state(page, "success")
                    
                    if reviews:
                        break
                    
            except Exception as e:
                logger.error(f"❌ PATCHRIGHT ERROR: {e}")
                diagnostics.add_error(str(e))
                if proxy:
                    update_proxy_score_advanced(proxy["server"], False, response_time=time.time() - proxy_start)
                await asyncio.sleep(random.uniform(3, 8))
            
            finally:
                if context:
                    await context.close()
    
    return reviews

# =========================================================
# IMPROVEMENT #10: QUANTUM MULTI-PROVIDER EXECUTION
# =========================================================

async def quantum_multi_provider_execution(place_id: str, diagnostics: ScrapeDiagnostics) -> List[Dict]:
    """Run multiple providers simultaneously and choose best result"""
    
    logger.info("=" * 50)
    logger.info("🌌 QUANTUM MODE: Running all providers simultaneously")
    logger.info("=" * 50)
    
    # Run all providers concurrently
    results = await asyncio.gather(
        patchright_reviews_enhanced(place_id, diagnostics),
        crawl4ai_quantum(place_id, diagnostics),
        curl_quantum(place_id, diagnostics),
        return_exceptions=True
    )
    
    all_reviews = []
    provider_results = {
        "patchright": [],
        "crawl4ai": [],
        "curl": []
    }
    
    provider_names = ["patchright", "crawl4ai", "curl"]
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"❌ {provider_names[i].upper()} provider failed: {result}")
        elif isinstance(result, list):
            provider_results[provider_names[i]] = result
            logger.info(f"✅ {provider_names[i].upper()} found {len(result)} reviews")
            all_reviews.extend(result)
    
    # Choose best provider result (largest set)
    best_count = 0
    best_provider = None
    for provider, reviews in provider_results.items():
        if len(reviews) > best_count:
            best_count = len(reviews)
            best_provider = provider
    
    if best_provider:
        logger.info(f"🏆 BEST PROVIDER: {best_provider.upper()} with {best_count} reviews")
    
    return deduplicate_reviews(all_reviews)[:MAX_REVIEWS]

# =========================================================
# MASTER SCRAPER - WITH QUANTUM MODE
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Enhanced master scraper with quantum multi-provider execution"""
    
    # IMPROVEMENT #8: Validate place ID before scraping
    is_valid, validation_msg = validate_place_id(place_id)
    if not is_valid:
        logger.error(f"❌ {validation_msg}")
        return []
    
    # Create diagnostics tracker
    diagnostics = ScrapeDiagnostics(place_id)
    
    logger.info("=" * 60)
    logger.info(f"🚀 QUANTUM SCRAPER STARTING for {place_id}")
    logger.info("=" * 60)
    diagnostics.add_step("scraper_start", True)
    
    # Check cache (only return non-empty results)
    cache_key = f"reviews:{place_id}"
    try:
        cached = review_cache.get(cache_key)
        if cached and len(cached) > 0:
            logger.info(f"⚡ CACHE HIT: {len(cached)} reviews")
            diagnostics.add_step("cache_hit", True, f"{len(cached)} reviews")
            diagnostics.reviews_found = len(cached)
            diagnostics.log_summary()
            return cached
    except Exception as e:
        logger.debug(f"Cache error: {e}")
    
    # IMPROVEMENT #10: Quantum multi-provider execution
    all_reviews = await quantum_multi_provider_execution(place_id, diagnostics)
    
    # Final deduplication
    all_reviews = deduplicate_reviews(all_reviews)[:MAX_REVIEWS]
    
    # Update diagnostics
    diagnostics.reviews_found = len(all_reviews)
    
    # Only cache non-empty results
    if all_reviews and len(all_reviews) > 0:
        try:
            review_cache[cache_key] = all_reviews
            logger.info(f"💾 CACHED {len(all_reviews)} reviews for {place_id}")
        except Exception as e:
            logger.debug(f"Cache set error: {e}")
    else:
        logger.warning(f"⚠️ No reviews found for {place_id} - debug files saved to {DEBUG_DIR}")
    
    # Log summary
    diagnostics.log_summary()
    
    # Get diagnostics summary
    diag_summary = diagnostics_store.get_summary()
    logger.info(f"📊 DIAGNOSTICS SUMMARY: {diag_summary}")
    
    logger.info(f"✅ FINAL REVIEWS => {len(all_reviews)}")
    
    return all_reviews

# =========================================================
# ALIAS
# =========================================================

async def run_scraper(place_id: str):
    return await scrape_google_reviews(place_id)

# =========================================================
# READY
# =========================================================

logger.info("=" * 70)
logger.info("✅ QUANTUM PATCHRIGHT SCRAPER V17.0 READY")
logger.info(f"📊 Persistent profile: {USER_DATA_DIR}")
logger.info(f"📊 Max reviews: {MAX_REVIEWS}")
logger.info(f"📊 Debug directory: {DEBUG_DIR}")
logger.info(f"📊 Diagnostics directory: {DIAGNOSTICS_DIR}")
logger.info(f"🌌 Quantum mode: ENABLED (3 providers simultaneously)")
logger.info("=" * 70)
