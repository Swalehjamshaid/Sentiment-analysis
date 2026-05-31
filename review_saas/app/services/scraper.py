# =========================================================
# FILE: app/services/scraper.py
# ULTIMATE GOOGLE REVIEW SCRAPER - V14.0
# ENTERPRISE GRADE WITH FULL DIAGNOSTICS
# =========================================================

from __future__ import annotations

# =========================================================
# CORE LIBRARIES
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
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

# =========================================================
# PRIORITY 1: PATCHRIGHT (NOT PLAYWRIGHT)
# =========================================================
from patchright.async_api import async_playwright
from playwright_stealth import stealth_async

# =========================================================
# HTML PARSING
# =========================================================
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser

# =========================================================
# USER AGENTS & RETRY
# =========================================================
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential
import backoff

# =========================================================
# LOGGER
# =========================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("█▀▀░█▀█░█▀▄░█▀▀░█░█░░░█▀▀░█▀█░█▀█░█▀█░█▀▀░█▀▀")
print("█░░░█░█░█░█░█▀▀░▄▀▄░░░█░░░█░█░█░█░█▀▀░▀▀█░█▀▀")
print("▀▀▀░▀▀▀░▀▀░░▀▀▀░▀░▀░░░▀▀▀░▀▀▀░▀▀▀░▀░░░▀▀▀░▀▀▀")
print("🚀 GOOGLE REVIEW SCRAPER V14.0 - ENTERPRISE GRADE")
print("=" * 60)

# =========================================================
# ENVIRONMENT CONFIGURATION
# =========================================================
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "300"))
MAX_REVIEWS = int(os.getenv("SCRAPER_MAX_REVIEWS", "500"))
HEADLESS_MODE = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_SCRAPES", "5"))

# Directories for debugging
DEBUG_DIR = os.getenv("DEBUG_DIR", "/tmp/scraper_debug")
Path(DEBUG_DIR).mkdir(parents=True, exist_ok=True)
for subdir in ["captcha", "no_reviews", "success", "error", "html_dumps"]:
    Path(f"{DEBUG_DIR}/{subdir}").mkdir(parents=True, exist_ok=True)

# =========================================================
# PROXY CONFIGURATION WITH SMART SCORING
# =========================================================
class ProxyManager:
    """Smart proxy manager with scoring and rotation"""
    
    def __init__(self):
        self.proxies = []
        self.proxy_stats = {}  # PRIORITY 10: Track success/fail/captcha/latency
        self.load_proxies()
    
    def load_proxies(self):
        proxy_servers = os.getenv("PROXY_SERVERS", os.getenv("PROXY_SERVER", "")).strip()
        proxy_username = os.getenv("PROXY_USERNAME", "").strip()
        proxy_password = os.getenv("PROXY_PASSWORD", "").strip()
        
        if "," in proxy_servers:
            servers = [s.strip() for s in proxy_servers.split(",")]
        elif proxy_servers:
            servers = [proxy_servers]
        else:
            servers = []
        
        for server in servers:
            if server:
                proxy_config = {"server": f"http://{server}"}
                if proxy_username and proxy_password:
                    proxy_config["username"] = proxy_username
                    proxy_config["password"] = proxy_password
                self.proxies.append(proxy_config)
                self.proxy_stats[server] = {
                    "success": 0,
                    "fail": 0,
                    "captcha": 0,
                    "response_times": [],
                    "last_used": None,
                    "cooldown_until": None
                }
        
        logger.info(f"✅ Loaded {len(self.proxies)} proxies")
    
    def calculate_score(self, server: str) -> float:
        """PRIORITY 10: Advanced proxy scoring"""
        stats = self.proxy_stats.get(server, {})
        total = stats.get("success", 0) + stats.get("fail", 0)
        
        if total == 0:
            return 0.5
        
        success_rate = stats.get("success", 0) / total
        captcha_rate = stats.get("captcha", 0) / (total + stats.get("captcha", 0) + 1)
        
        avg_latency = sum(stats.get("response_times", [1.0])) / max(len(stats.get("response_times", [1.0])), 1)
        latency_score = min(avg_latency / 10, 0.5)
        
        # Score = (success_rate * 0.6) - (captcha_rate * 0.3) - (latency_score * 0.1)
        score = (success_rate * 0.6) - (captcha_rate * 0.3) - (latency_score * 0.1)
        return max(0, min(1, score))
    
    def get_best_proxy(self) -> Optional[Dict]:
        """Get highest scoring proxy not in cooldown"""
        available = []
        for proxy in self.proxies:
            server = proxy["server"].replace("http://", "")
            stats = self.proxy_stats.get(server, {})
            cooldown = stats.get("cooldown_until", 0)
            
            if cooldown < time.time():
                score = self.calculate_score(server)
                available.append((score, proxy))
        
        if not available:
            return self.proxies[0] if self.proxies else None
        
        available.sort(key=lambda x: x[0], reverse=True)
        return available[0][1]
    
    def report_result(self, proxy_server: str, success: bool, captcha: bool = False, response_time: float = 0):
        """Update proxy statistics"""
        if not proxy_server:
            return
        
        server = proxy_server.replace("http://", "")
        if server not in self.proxy_stats:
            return
        
        stats = self.proxy_stats[server]
        if success:
            stats["success"] += 1
        else:
            stats["fail"] += 1
        
        if captcha:
            stats["captcha"] += 1
        
        if response_time > 0:
            stats["response_times"].append(response_time)
            if len(stats["response_times"]) > 100:
                stats["response_times"] = stats["response_times"][-100:]
        
        stats["last_used"] = time.time()
        
        # Cooldown on high failure rate
        total = stats["success"] + stats["fail"]
        if total > 5 and stats["fail"] / total > 0.6:
            stats["cooldown_until"] = time.time() + 300  # 5 minutes
            logger.warning(f"⚠️ Proxy {server} in cooldown (fail rate: {stats['fail']/total:.1%})")

proxy_manager = ProxyManager()

# =========================================================
# USER AGENT MANAGER
# =========================================================
class UserAgentManager:
    def __init__(self):
        try:
            self.ua = UserAgent()
            self.has_fake_ua = True
        except:
            self.has_fake_ua = False
            self.static_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ]
    
    def get(self) -> str:
        if self.has_fake_ua:
            try:
                return self.ua.random
            except:
                pass
        return random.choice(self.static_agents)

ua_manager = UserAgentManager()

# =========================================================
# PERSISTENT MEMORY WITH REDIS (PRIORITY 12)
# =========================================================
class PersistentMemory:
    """Persistent learning across restarts"""
    
    def __init__(self):
        self.data = {
            "selector_stats": {},
            "proxy_stats": {},
            "place_history": {}
        }
        self.redis_client = None
        self._init_redis()
        self._load_data()
    
    def _init_redis(self):
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
    
    def _load_data(self):
        if self.redis_client:
            try:
                # Load selector stats
                selector_data = self.redis_client.get("selector_stats")
                if selector_data:
                    self.data["selector_stats"] = json.loads(selector_data)
                    logger.info(f"✅ Loaded {len(self.data['selector_stats'])} selector stats")
                
                # Load proxy stats
                proxy_data = self.redis_client.get("proxy_stats")
                if proxy_data:
                    self.data["proxy_stats"] = json.loads(proxy_data)
                    logger.info(f"✅ Loaded {len(self.data['proxy_stats'])} proxy stats")
            except Exception as e:
                logger.debug(f"Could not load persisted data: {e}")
    
    def save_selector_stats(self, selector: str, success: bool):
        if selector not in self.data["selector_stats"]:
            self.data["selector_stats"][selector] = {"success": 0, "fail": 0}
        
        if success:
            self.data["selector_stats"][selector]["success"] += 1
        else:
            self.data["selector_stats"][selector]["fail"] += 1
        
        if self.redis_client:
            self.redis_client.setex("selector_stats", 86400, json.dumps(self.data["selector_stats"]))
    
    def get_best_selector(self, selectors: List[str]) -> str:
        best = selectors[0]
        best_rate = 0
        
        for selector in selectors:
            stats = self.data["selector_stats"].get(selector, {"success": 0, "fail": 0})
            total = stats["success"] + stats["fail"]
            rate = stats["success"] / total if total > 0 else 0.5
            
            if rate > best_rate:
                best_rate = rate
                best = selector
        
        return best

persistent_memory = PersistentMemory()

# =========================================================
# HEALTH METRICS (PRIORITY 15)
# =========================================================
class ExtractionHealth:
    """Track extraction health metrics"""
    
    def __init__(self):
        self.metrics = {
            "review_button_clicked": False,
            "review_panel_found": False,
            "review_cards_found": 0,
            "captcha_detected": False,
            "reviews_extracted": 0,
            "errors": []
        }
    
    def reset(self):
        self.metrics = {
            "review_button_clicked": False,
            "review_panel_found": False,
            "review_cards_found": 0,
            "captcha_detected": False,
            "reviews_extracted": 0,
            "errors": []
        }
    
    def log(self):
        logger.info(f"📊 HEALTH METRICS: {json.dumps(self.metrics, indent=2)}")
    
    def to_dict(self):
        return self.metrics.copy()

# =========================================================
# DEEP DIAGNOSTICS (PRIORITY 2)
# =========================================================
async def diagnose_page(page, place_id: str, stage: str, health: ExtractionHealth) -> Dict:
    """Comprehensive page diagnostics"""
    try:
        title = await page.title()
        url = page.url
        html = await page.content()
        html_length = len(html)
        
        logger.info(f"📊 DIAGNOSTICS [{stage}]")
        logger.info(f"   TITLE: {title}")
        logger.info(f"   URL: {url}")
        logger.info(f"   HTML LENGTH: {html_length} bytes")
        
        # Save debug files when no reviews found
        if stage == "after_extraction" and health.metrics["reviews_extracted"] == 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = f"{DEBUG_DIR}/html_dumps/{place_id}_{timestamp}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"📄 HTML saved: {html_path}")
            
            screenshot_path = f"{DEBUG_DIR}/no_reviews/{place_id}_{timestamp}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
        
        return {
            "title": title,
            "url": url,
            "html_length": html_length
        }
    except Exception as e:
        logger.error(f"Diagnostics error: {e}")
        return {}

# =========================================================
# STRONG CAPTCHA DETECTION (PRIORITY 9)
# =========================================================
def detect_captcha_strong(html: str) -> Tuple[bool, str]:
    """Enhanced CAPTCHA detection with type identification"""
    html_lower = html.lower()
    
    captcha_patterns = [
        ("captcha", "captcha"),
        ("unusual traffic", "traffic"),
        ("not a robot", "robot"),
        ("verify you are human", "verify"),
        ("security check", "security"),
        ("access denied", "access"),
        ("automated queries", "automated"),
        ("rate limit", "rate"),
        ("too many requests", "too_many"),
        ("blocked", "blocked")
    ]
    
    for pattern, pattern_type in captcha_patterns:
        if pattern in html_lower:
            logger.warning(f"🚨 CAPTCHA detected: {pattern_type}")
            return True, pattern_type
    
    return False, None

# =========================================================
# REVIEW PANEL VALIDATION (PRIORITY 6)
# =========================================================
async def verify_review_panel(page, health: ExtractionHealth) -> bool:
    """Verify that review panel exists"""
    try:
        panel_exists = await page.evaluate("""
            () => {
                const panel = document.querySelector('.m6QErb');
                if (panel) return true;
                const panels = document.querySelectorAll('[role="main"]');
                return panels.length > 0;
            }
        """)
        
        health.metrics["review_panel_found"] = panel_exists
        logger.info(f"📊 REVIEW PANEL FOUND: {panel_exists}")
        
        if not panel_exists:
            await page.screenshot(path=f"{DEBUG_DIR}/error/no_panel_{int(time.time())}.png", full_page=True)
        
        return panel_exists
    except Exception as e:
        logger.error(f"Panel verification error: {e}")
        return False

# =========================================================
# PROPER REVIEW PANEL SCROLLING (PRIORITY 3)
# =========================================================
async def scroll_review_panel(page, max_scrolls: int = 20) -> int:
    """Proper scrolling using .m6QErb panel"""
    scroll_count = 0
    
    for i in range(max_scrolls):
        try:
            result = await page.evaluate("""
                () => {
                    const panel = document.querySelector('.m6QErb');
                    if (panel) {
                        const before = panel.scrollHeight;
                        panel.scrollTop = panel.scrollHeight;
                        return { success: true, scrolled: true, height: panel.scrollHeight };
                    }
                    
                    const panels = document.querySelectorAll('[role="main"]');
                    for (const p of panels) {
                        const before = p.scrollHeight;
                        p.scrollTop = p.scrollHeight;
                        return { success: true, scrolled: true, height: p.scrollHeight };
                    }
                    return { success: false, scrolled: false };
                }
            """)
            
            if result and result.get('success'):
                scroll_count += 1
                await asyncio.sleep(random.uniform(1.0, 2.0))
            else:
                break
                
        except Exception as e:
            logger.debug(f"Scroll error: {e}")
            break
    
    logger.info(f"📊 SCROLL COUNT: {scroll_count}")
    return scroll_count

# =========================================================
# EXPAND TRUNCATED REVIEWS (PRIORITY 8)
# =========================================================
async def expand_truncated_reviews(page) -> int:
    """Click all 'More' and 'Read more' buttons"""
    expanded_count = 0
    
    expand_selectors = [
        'button:has-text("More")',
        'button:has-text("more")',
        'button:has-text("Read more")',
        'span:has-text("More")',
        'span:has-text("Read more")',
        'span.w8nwRe',
        'button[jsaction*="expand"]'
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
# REVIEW BUTTON CLICKING (PRIORITY 4 & 5)
# =========================================================
async def click_reviews_button(page, health: ExtractionHealth) -> bool:
    """Try multiple selectors to click reviews button"""
    
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
        'button[role="tab"]'
    ]
    
    for selector in review_button_selectors:
        try:
            button = page.locator(selector).first
            if await button.count() > 0:
                await button.click()
                persistent_memory.save_selector_stats(selector, True)
                health.metrics["review_button_clicked"] = True
                logger.info(f"✅ CLICKED REVIEW BUTTON: {selector}")
                
                # Wait and log URL after click (PRIORITY 5)
                await asyncio.sleep(3)
                logger.info(f"📊 URL AFTER CLICK: {page.url}")
                
                return True
        except Exception as e:
            persistent_memory.save_selector_stats(selector, False)
            logger.debug(f"Selector failed: {selector}")
    
    health.metrics["errors"].append("No review button found")
    logger.error("❌ NO REVIEW BUTTON FOUND")
    return False

# =========================================================
# REVIEW CARD COUNT (PRIORITY 5)
# =========================================================
async def count_review_cards(page, health: ExtractionHealth) -> int:
    """Count review cards using multiple selectors"""
    
    card_selectors = [
        'div[data-review-id]',
        'div.jftiEf',
        'div.MyEned',
        'div[role="article"]',
        'div[class*="review"]'
    ]
    
    for selector in card_selectors:
        try:
            count = await page.locator(selector).count()
            if count > 0:
                logger.info(f"📊 RAW REVIEW CARDS: {count} (selector: {selector})")
                health.metrics["review_cards_found"] = count
                return count
        except:
            pass
    
    logger.warning("📊 RAW REVIEW CARDS: 0")
    health.metrics["review_cards_found"] = 0
    return 0

# =========================================================
# REVIEW EXTRACTION WITH METADATA (PRIORITY 7 & 13)
# =========================================================
async def extract_reviews_with_metadata(page, place_id: str, health: ExtractionHealth) -> List[Dict]:
    """Extract reviews with all metadata"""
    reviews = []
    
    # Try multiple card selectors
    card_selectors = [
        'div[data-review-id]',
        'div.jftiEf',
        'div.MyEned',
        'div[role="article"]'
    ]
    
    for selector in card_selectors:
        cards = await page.locator(selector).all()
        if cards:
            logger.info(f"📊 Extracting from {len(cards)} cards using {selector}")
            
            for card in cards[:MAX_REVIEWS]:
                try:
                    # Extract review data
                    review_data = {}
                    
                    # Author
                    author_selectors = ['.d4r55', '.TSUbDb', 'span[class*="author"]', 'a[class*="author"]']
                    for sel in author_selectors:
                        if await card.locator(sel).count() > 0:
                            review_data["author"] = (await card.locator(sel).first.inner_text()).strip()
                            break
                    if "author" not in review_data:
                        review_data["author"] = "Anonymous"
                    
                    # Review text
                    text_selectors = ['.wiI7pd', '.MyEned', 'span[jsname]', 'div[class*="review-text"]']
                    for sel in text_selectors:
                        if await card.locator(sel).count() > 0:
                            review_data["review_text"] = (await card.locator(sel).first.inner_text()).strip()
                            break
                    
                    if not review_data.get("review_text"):
                        continue
                    
                    # Rating
                    if await card.locator('span.kvMYJc').count() > 0:
                        aria = await card.locator('span.kvMYJc').get_attribute('aria-label')
                        if aria:
                            match = re.search(r'(\d)', aria)
                            if match:
                                review_data["rating"] = int(match.group(1))
                    if "rating" not in review_data:
                        review_data["rating"] = 5
                    
                    # Date
                    date_selectors = ['.rsqaWe', '.DeaRdd', 'span[class*="date"]']
                    for sel in date_selectors:
                        if await card.locator(sel).count() > 0:
                            review_data["review_date"] = (await card.locator(sel).first.inner_text()).strip()
                            break
                    
                    # Likes count
                    likes_selectors = ['button[jsaction*="like"]', '.PKRcHd']
                    for sel in likes_selectors:
                        if await card.locator(sel).count() > 0:
                            likes_text = await card.locator(sel).first.inner_text()
                            match = re.search(r'(\d+)', likes_text)
                            if match:
                                review_data["likes_count"] = int(match.group(1))
                            break
                    
                    # Local guide
                    if await card.locator('img[alt*="Local Guide"]').count() > 0:
                        review_data["is_local_guide"] = True
                    
                    # Owner response
                    owner_selectors = ['[jsname="bN97Pc"]', '.CDe7pd']
                    for sel in owner_selectors:
                        if await card.locator(sel).count() > 0:
                            review_data["owner_response"] = (await card.locator(sel).first.inner_text()).strip()
                            break
                    
                    # Normalize and add
                    normalized = normalize_review(review_data, place_id)
                    if normalized:
                        reviews.append(normalized)
                        
                except Exception as e:
                    logger.debug(f"Card extraction error: {e}")
            
            if reviews:
                break
    
    health.metrics["reviews_extracted"] = len(reviews)
    logger.info(f"✅ EXTRACTED {len(reviews)} REVIEWS")
    return reviews

# =========================================================
# REVIEW NORMALIZATION
# =========================================================
@lru_cache(maxsize=10000)
def generate_review_id_cached(place_id: str, author: str, text_hash: str, date: str) -> str:
    raw = f"{place_id}:{author}:{text_hash}:{date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def normalize_review(review: Dict[str, Any], place_id: str) -> Optional[Dict]:
    try:
        review_text = str(review.get("review_text", "")).strip()
        if not review_text or len(review_text) < 3:
            return None
        
        author = str(review.get("author", "Anonymous")).strip()
        rating = min(5, max(1, int(review.get("rating", 5))))
        review_date = review.get("review_date", "")
        text_hash = hashlib.md5(review_text.encode()).hexdigest()[:16]
        
        return {
            "google_review_id": generate_review_id_cached(place_id, author, text_hash, review_date),
            "author": author,
            "author_name": author,
            "rating": rating,
            "review_text": review_text,
            "content": review_text,
            "text": review_text,
            "review_date": review_date,
            "likes_count": review.get("likes_count", 0),
            "is_local_guide": review.get("is_local_guide", False),
            "owner_response": review.get("owner_response", ""),
            "sentiment_score": 0.5,
            "google_review_time": datetime.utcnow(),
            "scraped_at": datetime.utcnow()
        }
    except Exception:
        return None

def deduplicate_reviews(reviews: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for review in reviews:
        rid = review.get("google_review_id", "")
        if rid and rid not in seen:
            seen.add(rid)
            unique.append(review)
    return unique

# =========================================================
# TRUE CONSENSUS ENGINE (PRIORITY 11)
# =========================================================
async def consensus_extraction(page, place_id: str, health: ExtractionHealth) -> List[Dict]:
    """True consensus using Playwright DOM + Selectolax + BeautifulSoup"""
    
    results = {}
    
    # Source 1: Playwright DOM
    playwright_reviews = await extract_reviews_with_metadata(page, place_id, health)
    results["playwright"] = playwright_reviews
    logger.info(f"📊 PLAYWRIGHT: {len(playwright_reviews)} reviews")
    
    # Get HTML for other parsers
    html = await page.content()
    
    # Source 2: Selectolax
    try:
        parser = HTMLParser(html)
        selectolax_reviews = []
        nodes = parser.css('div[data-review-id], div.jftiEf')
        
        for node in nodes[:MAX_REVIEWS]:
            author_node = node.css_first('.d4r55, .TSUbDb')
            text_node = node.css_first('.wiI7pd, .MyEned')
            
            if text_node:
                review = {
                    "author": author_node.text(strip=True) if author_node else "Anonymous",
                    "review_text": text_node.text(strip=True),
                    "rating": 5
                }
                
                rating_node = node.css_first('span.kvMYJc')
                if rating_node and rating_node.attributes.get('aria-label'):
                    match = re.search(r'(\d)', rating_node.attributes['aria-label'])
                    if match:
                        review["rating"] = int(match.group(1))
                
                normalized = normalize_review(review, place_id)
                if normalized:
                    selectolax_reviews.append(normalized)
        
        results["selectolax"] = selectolax_reviews
        logger.info(f"📊 SELECTOLAX: {len(selectolax_reviews)} reviews")
    except Exception as e:
        logger.error(f"Selectolax error: {e}")
    
    # Source 3: BeautifulSoup
    try:
        soup = BeautifulSoup(html, 'html.parser')
        bs4_reviews = []
        elements = soup.select('div[data-review-id], div.jftiEf')
        
        for elem in elements[:MAX_REVIEWS]:
            author_elem = elem.select_one('.d4r55, .TSUbDb')
            text_elem = elem.select_one('.wiI7pd, .MyEned')
            
            if text_elem:
                review = {
                    "author": author_elem.get_text(strip=True) if author_elem else "Anonymous",
                    "review_text": text_elem.get_text(strip=True),
                    "rating": 5
                }
                
                rating_elem = elem.select_one('span.kvMYJc')
                if rating_elem and rating_elem.get('aria-label'):
                    match = re.search(r'(\d)', rating_elem['aria-label'])
                    if match:
                        review["rating"] = int(match.group(1))
                
                normalized = normalize_review(review, place_id)
                if normalized:
                    bs4_reviews.append(normalized)
        
        results["beautifulsoup"] = bs4_reviews
        logger.info(f"📊 BEAUTIFULSOUP: {len(bs4_reviews)} reviews")
    except Exception as e:
        logger.error(f"BeautifulSoup error: {e}")
    
    # Consensus: Accept if at least 2 parsers agree
    review_votes = defaultdict(lambda: {"votes": 0, "review": None})
    
    for source, reviews in results.items():
        for review in reviews:
            rid = review.get("google_review_id")
            if rid:
                if review_votes[rid]["votes"] == 0:
                    review_votes[rid]["review"] = review
                review_votes[rid]["votes"] += 1
    
    consensus = [data["review"] for data in review_votes.values() if data["votes"] >= 2]
    logger.info(f"🎯 CONSENSUS: {len(consensus)} reviews (2+ parsers agree)")
    
    return consensus

# =========================================================
# MULTI-STEP NAVIGATION (PRIORITY 14)
# =========================================================
async def ultimate_scrape_reviews(place_id: str) -> List[Dict]:
    """Enterprise-grade multi-step navigation"""
    
    health = ExtractionHealth()
    start_time = time.time()
    
    logger.info(f"🚀 ULTIMATE SCRAPE: {place_id}")
    
    # Check cache
    cache_key = f"reviews:{place_id}"
    
    proxy = proxy_manager.get_best_proxy()
    proxy_start = time.time()
    
    async with async_playwright() as p:
        browser = None
        context = None
        
        try:
            # Step 1: Launch browser
            browser = await p.chromium.launch(
                headless=HEADLESS_MODE,
                proxy=proxy,
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--window-size=1920,1080"
                ]
            )
            
            # Step 2: Create context
            context = await browser.new_context(
                user_agent=ua_manager.get(),
                viewport={"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},
                locale="en-US",
                timezone_id="America/New_York"
            )
            
            page = await context.new_page()
            
            # Step 3: Apply stealth
            await stealth_async(page)
            
            # Step 4: Navigate to place
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            logger.info(f"🌐 NAVIGATING TO: {url}")
            
            response = await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Step 5: Check for errors
            if response and response.status >= 400:
                logger.error(f"HTTP {response.status} error")
                return []
            
            await asyncio.sleep(random.uniform(2, 4))
            
            # Step 6: Check CAPTCHA
            html = await page.content()
            is_captcha, captcha_type = detect_captcha_strong(html)
            if is_captcha:
                health.metrics["captcha_detected"] = True
                proxy_manager.report_result(proxy["server"] if proxy else None, False, captcha=True)
                await page.screenshot(path=f"{DEBUG_DIR}/captcha/{place_id}_{captcha_type}.png", full_page=True)
                return []
            
            # Step 7: Click reviews button
            button_clicked = await click_reviews_button(page, health)
            if not button_clicked:
                await diagnose_page(page, place_id, "no_button", health)
                return []
            
            # Step 8: Verify review panel
            panel_found = await verify_review_panel(page, health)
            if not panel_found:
                await diagnose_page(page, place_id, "no_panel", health)
                return []
            
            # Step 9: Scroll review panel
            scroll_count = await scroll_review_panel(page, max_scrolls=20)
            logger.info(f"📊 SCROLLED {scroll_count} times")
            
            # Step 10: Expand truncated reviews
            expanded = await expand_truncated_reviews(page)
            logger.info(f"📊 EXPANDED {expanded} truncated reviews")
            
            # Step 11: Count review cards
            card_count = await count_review_cards(page, health)
            
            # Step 12: Extract reviews with consensus
            reviews = await consensus_extraction(page, place_id, health)
            
            # Step 13: Final diagnostics
            await diagnose_page(page, place_id, "after_extraction", health)
            
            # Step 14: Report success
            response_time = time.time() - proxy_start
            proxy_manager.report_result(proxy["server"] if proxy else None, len(reviews) > 0, response_time=response_time)
            
            # Step 15: Log health metrics
            health.log()
            
            # Cache results
            if reviews:
                review_cache_l1[cache_key] = reviews
            
            duration = time.time() - start_time
            logger.info(f"✅ COMPLETE: {len(reviews)} reviews in {duration:.2f}s")
            
            return reviews[:MAX_REVIEWS]
            
        except Exception as e:
            logger.error(f"❌ Scraping error: {e}")
            logger.error(traceback.format_exc())
            proxy_manager.report_result(proxy["server"] if proxy else None, False)
            return []
        
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

# =========================================================
# MAIN EXPORT FUNCTIONS
# =========================================================

# Simple cache for frequent access
review_cache_l1 = {}

async def scrape_google_reviews(place_id: str) -> List
