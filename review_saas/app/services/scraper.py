# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE SCRAPER - V31.0 ULTIMATE
# PROXY OPTIMIZED + ANTI-DETECTION + MULTI-ENGINE
# =========================================================

from __future__ import annotations

import os
import re
import time
import json
import asyncio
import hashlib
import logging
import random
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import deque, defaultdict
from urllib.parse import urlparse

# =========================================================
# THIRD-PARTY IMPORTS (Install with: pip install patchright playwright-stealth fake-useragent tenacity backoff selectolax curl_cffi beautifulsoup4)
# =========================================================

try:
    from patchright.async_api import async_playwright
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    from playwright.async_api import async_playwright
    PATCHRIGHT_AVAILABLE = False
    print("⚠️ Patchright not available - using Playwright (higher detection risk)")

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("⚠️ Playwright-stealth not available - limited stealth capabilities")

try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False
    print("⚠️ Fake-useragent not available - using default user agents")

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    from tenacity import before_sleep_log
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    print("⚠️ Tenacity not available - using basic retry logic")

try:
    import backoff
    BACKOFF_AVAILABLE = True
except ImportError:
    BACKOFF_AVAILABLE = False
    print("⚠️ Backoff not available - using basic backoff")

try:
    from selectolax.parser import HTMLParser
    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False
    print("⚠️ Selectolax not available - using BeautifulSoup fallback")

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("⚠️ BeautifulSoup not available - DOM extraction limited")

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️ Curl_CFFI not available - using standard requests")

# =========================================================
# CONSTANTS SECTION
# =========================================================

class ScraperConfig:
    """Centralized configuration for all scraper parameters"""
    
    # Review limits
    MAX_REVIEWS = 150
    MIN_REVIEW_LENGTH = 20
    MAX_REVIEW_LENGTH = 5000
    
    # Scroll behavior
    MAX_SCROLLS = 50
    SCROLL_DISTANCE_START = 1000
    SCROLL_DISTANCE_MAX = 3000
    SCROLL_STAGNANT_LIMIT = 3
    SCROLL_DELAY_MIN = 0.8
    SCROLL_DELAY_MAX = 1.5
    
    # Timeouts
    RPC_TIMEOUT = 12
    PAGE_LOAD_TIMEOUT = 60000
    NAVIGATION_TIMEOUT = 60000
    BROWSER_LAUNCH_TIMEOUT = 30000
    
    # Retry configuration
    MAX_RETRIES = 4
    RETRY_WAIT_MIN = 2
    RETRY_WAIT_MAX = 10
    
    # Rate limiting
    RATE_LIMIT_BACKOFF_MAX = 300  # 5 minutes max backoff
    
    # Human behavior simulation
    CLICK_DELAY_MIN = 0.3
    CLICK_DELAY_MAX = 0.8
    TYPING_DELAY_MIN = 0.05
    TYPING_DELAY_MAX = 0.15
    
    # Browser fingerprints
    VIEWPORTS = [
        {"width": 1366, "height": 768},
        {"width": 1920, "height": 1080},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1280, "height": 720}
    ]
    
    TIMEZONES = [
        "America/New_York", "America/Los_Angeles", "Europe/London",
        "Europe/Berlin", "Asia/Tokyo", "Australia/Sydney"
    ]
    
    LANGUAGES = ["en-US", "en-GB", "en-CA", "en-AU"]
    
    # Selector Brain
    SELECTOR_SAVE_INTERVAL = 50
    SELECTOR_EXPIRY_DAYS = 90
    
    # Proxy Brain
    PROXY_COOLDOWN_BASE = 600
    PROXY_COOLDOWN_MAX = 3600
    PROXY_RECENT_WEIGHT = 0.7
    
    # Deduplication
    DEDUP_CHAR_LIMIT = 100
    
    # Output
    SCREENSHOT_ON_ERROR = True
    SCREENSHOT_DIR = Path("/app/data/screenshots")
    
    # Health check
    HEALTH_CHECK_URL = "https://www.google.com"
    
    # Metrics
    METRICS_FILE = Path("/app/data/scraper_metrics.json")

# =========================================================
# LOGGER CONFIGURATION
# =========================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("=" * 80)
print("🚀 QUANTUM ENTERPRISE SCRAPER V31.0 - ULTIMATE EDITION")
print("┌─────────────────────────────────────────────────────────────────┐")
print("│ PATCHRIGHT │ PLAYWRIGHT-STEALTH │ FAKE UA │ PROXY ROTATION     │")
print("│ TENACITY RETRY │ BACKOFF RATE LIMIT │ SELECTOLAX              │")
print("│ CURL_CFFI RPC │ CAPTCHA DETECTION │ HUMAN BEHAVIOR            │")
print("│ FINGERPRINT ROTATION │ MULTI-ENGINE EXTRACTION                │")
print("└─────────────────────────────────────────────────────────────────┘")
print("=" * 80)

# =========================================================
# PHASE 1: ENHANCED PROXY MANAGER WITH SESSION ROTATION
# =========================================================

class ProxyManager:
    """Advanced proxy management with session rotation and statistics"""
    
    def __init__(self):
        self.proxy_pool = []
        self.session_counter = 0
        self.proxy_stats = {}
        self.init_proxies()
    
    def init_proxies(self):
        """Initialize proxies from environment with session rotation support"""
        proxy_server = os.getenv("PROXY_SERVER", "").strip()
        proxy_username = os.getenv("PROXY_USERNAME", "").strip()
        proxy_password = os.getenv("PROXY_PASSWORD", "").strip()
        
        if not proxy_server:
            return
        
        # Parse proxy servers (support multiple)
        servers = proxy_server.split(",") if "," in proxy_server else [proxy_server]
        
        for server in servers:
            server = server.strip()
            if not server:
                continue
            
            # Add protocol if missing
            if not server.startswith(("http://", "https://")):
                server = f"http://{server}"
            
            # Create base proxy config
            base_proxy = {"server": server}
            
            if proxy_username and proxy_password:
                base_proxy["username"] = proxy_username
                base_proxy["password"] = proxy_password
            
            self.proxy_pool.append(base_proxy)
            
            # Initialize stats for this proxy
            self.proxy_stats[server] = {
                "success": 0,
                "fail": 0,
                "captcha": 0,
                "reviews": 0,
                "latencies": [],
                "sessions": {},
                "last_used": None,
                "country": None
            }
        
        logger.info(f"✅ Initialized {len(self.proxy_pool)} proxies with session rotation support")
    
    def get_proxy_with_session(self, force_fresh: bool = False) -> Optional[Dict]:
        """Get proxy with rotating session ID for new IP on each request"""
        if not self.proxy_pool:
            return None
        
        # Select best proxy based on stats
        best_proxy = self._select_best_proxy()
        if not best_proxy:
            return None
        
        # Generate session ID for rotation
        if force_fresh or self.session_counter % 5 == 0:  # Rotate every 5 requests
            session_id = random.randint(100000, 999999)
        else:
            session_id = random.randint(10000, 99999)
        
        self.session_counter += 1
        
        # Create session-specific proxy config
        proxy_with_session = best_proxy.copy()
        if "username" in proxy_with_session:
            # Append session ID to username for DataImpulse rotation
            original_username = proxy_with_session["username"]
            proxy_with_session["username"] = f"{original_username}-session-{session_id}"
        
        # Update last used timestamp
        server = best_proxy.get("server", "")
        if server in self.proxy_stats:
            self.proxy_stats[server]["last_used"] = time.time()
            self.proxy_stats[server]["sessions"][session_id] = {
                "created_at": time.time(),
                "requests": 0
            }
        
        logger.debug(f"🔑 Using proxy session: {session_id}")
        return proxy_with_session
    
    def _select_best_proxy(self) -> Optional[Dict]:
        """Select best proxy based on performance statistics"""
        if not self.proxy_pool:
            return None
        
        best_score = -1
        best_proxy = None
        
        for proxy in self.proxy_pool:
            server = proxy.get("server", "")
            stats = self.proxy_stats.get(server, {})
            
            # Calculate score based on success rate and recent performance
            success_rate = stats.get("success", 1) / max(1, stats.get("success", 1) + stats.get("fail", 1))
            captcha_penalty = min(stats.get("captcha", 0) * 0.1, 0.5)
            recency_bonus = 0.1 if stats.get("last_used") and (time.time() - stats["last_used"]) > 60 else 0
            
            score = success_rate - captcha_penalty + recency_bonus
            
            if score > best_score:
                best_score = score
                best_proxy = proxy
        
        return best_proxy or self.proxy_pool[0]
    
    def report_result(self, proxy: Dict, success: bool, captcha: bool = False, 
                     reviews: int = 0, latency: float = 0, country: str = None):
        """Report proxy performance for learning"""
        server = proxy.get("server", "")
        if server not in self.proxy_stats:
            self.proxy_stats[server] = {"success": 0, "fail": 0, "captcha": 0, "reviews": 0, "latencies": []}
        
        stats = self.proxy_stats[server]
        
        if success:
            stats["success"] += 1
            stats["reviews"] += reviews
        else:
            stats["fail"] += 1
        
        if captcha:
            stats["captcha"] += 1
        
        if latency > 0:
            stats["latencies"].append(latency)
            stats["avg_latency"] = sum(stats["latencies"]) / len(stats["latencies"])
        
        if country:
            stats["country"] = country
        
        # Log performance
        success_rate = stats["success"] / max(1, stats["success"] + stats["fail"])
        logger.debug(f"📊 Proxy {server[:30]}: {success_rate*100:.1f}% success, {stats.get('reviews', 0)} reviews")
    
    def get_stats_summary(self) -> Dict:
        """Get summary of proxy performance"""
        if not self.proxy_stats:
            return {}
        
        total_success = sum(s["success"] for s in self.proxy_stats.values())
        total_fail = sum(s["fail"] for s in self.proxy_stats.values())
        total_reviews = sum(s["reviews"] for s in self.proxy_stats.values())
        
        return {
            "total_proxies": len(self.proxy_stats),
            "total_requests": total_success + total_fail,
            "success_rate": total_success / max(1, total_success + total_fail),
            "total_reviews": total_reviews,
            "avg_reviews_per_success": total_reviews / max(1, total_success)
        }

# =========================================================
# PHASE 2: BROWSER FINGERPRINT MANAGER
# =========================================================

class FingerprintManager:
    """Rotate browser fingerprints for human-like behavior"""
    
    @staticmethod
    def get_random_fingerprint() -> Dict:
        """Generate random browser fingerprint"""
        return {
            "viewport": random.choice(ScraperConfig.VIEWPORTS),
            "timezone": random.choice(ScraperConfig.TIMEZONES),
            "locale": random.choice(ScraperConfig.LANGUAGES),
            "device_scale_factor": random.uniform(1, 2),
            "is_mobile": False,
            "has_touch": False
        }
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Get random user agent using fake-useragent or fallback"""
        if FAKE_UA_AVAILABLE:
            try:
                ua = UserAgent()
                return ua.random
            except Exception as e:
                logger.debug(f"Fake useragent failed: {e}")
        
        # Fallback user agents
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ]
        return random.choice(user_agents)

# =========================================================
# PHASE 3: CAPTCHA DETECTOR
# =========================================================

class CaptchaDetector:
    """Detect CAPTCHA and rate limiting pages"""
    
    CAPTCHA_PATTERNS = [
        r"sorry/index",
        r"unusual traffic",
        r"recaptcha",
        r"captcha",
        r"rate limit",
        r"too many requests",
        r"automated requests"
    ]
    
    @classmethod
    def detect(cls, page_content: str, url: str) -> Tuple[bool, str]:
        """Check if page contains CAPTCHA or rate limiting"""
        content_lower = page_content.lower()
        url_lower = url.lower()
        
        for pattern in cls.CAPTCHA_PATTERNS:
            if pattern in content_lower or pattern in url_lower:
                return True, pattern
        
        return False, None
    
    @classmethod
    async def detect_async(cls, page) -> Tuple[bool, str]:
        """Async version using Playwright page"""
        try:
            content = await page.content()
            url = page.url
            return cls.detect(content, url)
        except:
            return False, None

# =========================================================
# PHASE 4: HUMAN BEHAVIOR SIMULATOR
# =========================================================

class HumanBehavior:
    """Simulate human-like interactions"""
    
    @staticmethod
    async def random_delay(min_sec: float = None, max_sec: float = None):
        """Random delay to simulate human hesitation"""
        min_delay = min_sec or 0.5
        max_delay = max_sec or 2.0
        await asyncio.sleep(random.uniform(min_delay, max_delay))
    
    @staticmethod
    async def random_mouse_movement(page):
        """Simulate random mouse movements"""
        try:
            viewport = page.viewport_size
            if viewport:
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                await page.mouse.move(x, y, steps=random.randint(5, 15))
        except:
            pass
    
    @staticmethod
    async def human_type(page, selector: str, text: str):
        """Type text with random delays between keystrokes"""
        try:
            await page.click(selector)
            await HumanBehavior.random_delay(0.1, 0.3)
            
            for char in text:
                await page.type(selector, char, delay=random.uniform(0.05, 0.15))
        except Exception as e:
            logger.debug(f"Human typing failed: {e}")

# =========================================================
# PHASE 5: CURL_CFFI DIRECT RPC EXTRACTION
# =========================================================

class DirectRPCExtractor:
    """Extract reviews directly using curl_cffi for speed"""
    
    @staticmethod
    async def fetch_reviews(place_id: str, proxy: Dict = None) -> List[Dict]:
        """Direct RPC fetch using curl_cffi (10x faster)"""
        if not CURL_CFFI_AVAILABLE:
            return []
        
        reviews = []
        
        try:
            # Google Maps API endpoint (reverse engineered)
            url = f"https://www.google.com/maps/preview/review/listentitiesreviews"
            
            params = {
                "authuser": "0",
                "hl": "en",
                "gl": "us",
                "pb": f"!1m2!1y{place_id}!2y!2m2!1sen!2sus!3e2"
            }
            
            # Setup proxy for curl
            proxies = None
            if proxy and proxy.get("server"):
                proxy_url = proxy["server"]
                if proxy.get("username") and proxy.get("password"):
                    proxy_url = proxy_url.replace("http://", f"http://{proxy['username']}:{proxy['password']}@")
                proxies = {"http": proxy_url, "https": proxy_url}
            
            # Make request
            response = curl_requests.get(
                url,
                params=params,
                proxies=proxies,
                timeout=30,
                impersonate="chrome120"
            )
            
            if response.status_code == 200:
                # Parse RPC response
                decoded = AdvancedRPCDecoder.decode(response.text)
                reviews.extend(decoded)
                logger.info(f"⚡ Direct RPC extraction: {len(reviews)} reviews")
            
        except Exception as e:
            logger.debug(f"Direct RPC extraction failed: {e}")
        
        return reviews

# =========================================================
# PHASE 6: ENHANCED RPC DECODER (from previous version)
# =========================================================

class AdvancedRPCDecoder:
    """Universal RPC decoder with validation"""
    
    @staticmethod
    def decode(payload: str, max_results: int = 150) -> List[Dict]:
        """Multi-format RPC decoder"""
        reviews = []
        
        decoders = [
            AdvancedRPCDecoder._decode_json_objects,
            AdvancedRPCDecoder._decode_nested_arrays,
            AdvancedRPCDecoder._decode_batchexecute,
        ]
        
        for decoder in decoders:
            try:
                result = decoder(payload)
                if result:
                    reviews.extend(result)
                    if len(reviews) >= 20:  # Early stop if we have enough
                        break
            except Exception as e:
                logger.debug(f"Decoder failed: {e}")
        
        return reviews[:max_results]
    
    @staticmethod
    def _decode_json_objects(payload: str) -> List[Dict]:
        """Extract reviews from JSON objects"""
        reviews = []
        try:
            json_pattern = r'\{[^{}]*"reviewText"[^{}]*\}'
            for match in re.findall(json_pattern, payload):
                try:
                    data = json.loads(match)
                    if "reviewText" in data:
                        reviews.append({
                            "text": data["reviewText"][:500],
                            "author": data.get("authorName", "Google User"),
                            "rating": data.get("rating", 5),
                            "source": "rpc_json"
                        })
                except:
                    pass
        except:
            pass
        return reviews
    
    @staticmethod
    def _decode_nested_arrays(payload: str) -> List[Dict]:
        """Extract reviews from nested arrays"""
        reviews = []
        try:
            text_pattern = r'\["reviewText","([^"]+)"\]'
            rating_pattern = r'\["rating",(\d+)\]'
            
            texts = re.findall(text_pattern, payload)
            ratings = re.findall(rating_pattern, payload)
            
            for i, text in enumerate(texts):
                if len(text) > 20:
                    rating = int(ratings[i]) if i < len(ratings) else 5
                    reviews.append({
                        "text": text[:500],
                        "author": "Google User",
                        "rating": rating,
                        "source": "rpc_array"
                    })
        except:
            pass
        return reviews
    
    @staticmethod
    def _decode_batchexecute(payload: str) -> List[Dict]:
        """Decode batchexecute format"""
        reviews = []
        try:
            freq_match = re.search(r'"f\.req":"([^"]+)"', payload)
            if freq_match:
                decoded = base64.b64decode(freq_match.group(1)).decode('utf-8', errors='ignore')
                text_matches = re.findall(r'"reviewText":"([^"\\]*(?:\\.[^"\\]*)*)"', decoded)
                for text in text_matches:
                    if len(text) > 20:
                        reviews.append({
                            "text": text[:500],
                            "author": "Google User",
                            "rating": 5,
                            "source": "rpc_batchexecute"
                        })
        except:
            pass
        return reviews

# =========================================================
# PHASE 7: TENACITY RETRY WRAPPER
# =========================================================

def with_retry(max_attempts: int = ScraperConfig.MAX_RETRIES):
    """Decorator for retry logic using tenacity if available"""
    if TENACITY_AVAILABLE:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
    else:
        # Simple retry decorator fallback
        def decorator(func):
            async def wrapper(*args, **kwargs):
                last_error = None
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_error = e
                        wait_time = min(2 ** attempt, 10)
                        logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                raise last_error
            return wrapper
        return decorator

# =========================================================
# PHASE 8: MAIN SCRAPER WITH ALL IMPROVEMENTS
# =========================================================

class UltimateGoogleScraper:
    """Ultimate scraper with all optimizations"""
    
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.fingerprint_manager = FingerprintManager()
        self.captcha_detector = CaptchaDetector()
        self.human_behavior = HumanBehavior()
        self.direct_extractor = DirectRPCExtractor()
    
    @with_retry(max_attempts=ScraperConfig.MAX_RETRIES)
    async def scrape(self, place_id: str) -> List[Dict]:
        """Main scrape method with retry logic"""
        
        logger.info("=" * 80)
        logger.info(f"🚀 Ultimate scraper starting: {place_id}")
        start_time = time.time()
        
        # Try direct RPC extraction first (fastest)
        reviews = await self._try_direct_rpc(place_id)
        if reviews and len(reviews) >= 20:
            logger.info(f"✅ Direct RPC extraction successful: {len(reviews)} reviews")
            return self._normalize_reviews(reviews, place_id, "direct_rpc")
        
        # Fallback to browser-based extraction
        reviews = await self._browser_extraction(place_id)
        
        duration = time.time() - start_time
        logger.info(f"✅ Scraping completed: {len(reviews)} reviews in {duration:.2f}s")
        
        return self._normalize_reviews(reviews, place_id, "browser")
    
    async def _try_direct_rpc(self, place_id: str) -> List[Dict]:
        """Try direct RPC extraction first"""
        proxy = self.proxy_manager.get_proxy_with_session(force_fresh=True)
        reviews = await self.direct_extractor.fetch_reviews(place_id, proxy)
        
        if reviews:
            self.proxy_manager.report_result(proxy, True, reviews=len(reviews))
            return reviews
        
        if proxy:
            self.proxy_manager.report_result(proxy, False)
        return []
    
    async def _browser_extraction(self, place_id: str) -> List[Dict]:
        """Browser-based extraction with full stealth"""
        
        reviews = []
        context = None
        browser = None
        
        try:
            async with async_playwright() as p:
                # Get proxy with session rotation
                proxy = self.proxy_manager.get_proxy_with_session()
                
                # Get random fingerprint
                fingerprint = self.fingerprint_manager.get_random_fingerprint()
                user_agent = self.fingerprint_manager.get_random_user_agent()
                
                # Launch browser with stealth args
                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-features=Translate",
                    "--disable-popup-blocking",
                    "--disable-notifications"
                ]
                
                if PATCHRIGHT_AVAILABLE:
                    # Patchright has better fingerprint masking
                    launch_args.append("--disable-features=ChromeWhatsNewUI")
                
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy,
                    args=launch_args,
                    timeout=ScraperConfig.BROWSER_LAUNCH_TIMEOUT
                )
                
                # Create context with fingerprint
                context = await browser.new_context(
                    viewport=fingerprint["viewport"],
                    user_agent=user_agent,
                    locale=fingerprint["locale"],
                    timezone_id=fingerprint["timezone"],
                    device_scale_factor=fingerprint["device_scale_factor"],
                    is_mobile=fingerprint["is_mobile"],
                    has_touch=fingerprint["has_touch"]
                )
                
                # Apply stealth if available
                page = await context.new_page()
                if STEALTH_AVAILABLE:
                    try:
                        await stealth_async(page)
                        logger.debug("✅ Playwright stealth applied")
                    except Exception as e:
                        logger.debug(f"Stealth application failed: {e}")
                
                # Add extra stealth scripts
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    window.chrome = {runtime: {}};
                """)
                
                # Navigate with human-like delay
                url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                await page.goto(url, wait_until="networkidle", timeout=ScraperConfig.NAVIGATION_TIMEOUT)
                await self.human_behavior.random_delay(1, 2)
                
                # Check for CAPTCHA
                is_captcha, captcha_type = await self.captcha_detector.detect_async(page)
                if is_captcha:
                    logger.warning(f"🚫 CAPTCHA detected: {captcha_type}")
                    self.proxy_manager.report_result(proxy, False, captcha=True)
                    return []
                
                # Click reviews button with human behavior
                reviews_button = page.locator('button[data-tab-index="1"]').first
                if await reviews_button.count() > 0:
                    await self.human_behavior.random_mouse_movement(page)
                    await self.human_behavior.random_delay(0.3, 0.7)
                    await reviews_button.click()
                    await self.human_behavior.random_delay(2, 3)
                else:
                    logger.warning("Reviews button not found")
                    await context.close()
                    return []
                
                # Wait for RPC data
                await asyncio.sleep(3)
                
                # Extract from page content using Selectolax (fast)
                html = await page.content()
                
                if SELECTOLAX_AVAILABLE:
                    # Fast HTML parsing
                    tree = HTMLParser(html)
                    # Extract review elements
                    review_elements = tree.css('div[data-review-id], div.jftiEf')
                    for elem in review_elements[:ScraperConfig.MAX_REVIEWS]:
                        text_elem = elem.css_first('.wiI7pd, .MyEned')
                        if text_elem:
                            text = text_elem.text(strip=True)
                            if len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                                reviews.append({
                                    "text": text,
                                    "author": "Anonymous",
                                    "rating": 5,
                                    "source": "selectolax"
                                })
                elif BEAUTIFULSOUP_AVAILABLE:
                    # BeautifulSoup fallback
                    soup = BeautifulSoup(html, 'html.parser')
                    review_divs = soup.select('div[data-review-id], div.jftiEf')
                    for div in review_divs[:ScraperConfig.MAX_REVIEWS]:
                        text_elem = div.select_one('.wiI7pd, .MyEned')
                        if text_elem:
                            text = text_elem.get_text(strip=True)
                            if len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                                reviews.append({
                                    "text": text,
                                    "author": "Anonymous",
                                    "rating": 5,
                                    "source": "beautifulsoup"
                                })
                
                # Report success
                self.proxy_manager.report_result(proxy, True, reviews=len(reviews))
                
        except Exception as e:
            logger.error(f"Browser extraction failed: {e}")
            if proxy:
                self.proxy_manager.report_result(proxy, False)
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
        
        return reviews
    
    def _normalize_reviews(self, reviews: List[Dict], place_id: str, source: str) -> List[Dict]:
        """Normalize review format"""
        normalized = []
        seen = set()
        
        for r in reviews[:ScraperConfig.MAX_REVIEWS]:
            text = r.get("text", "").strip()
            if not text or len(text) < ScraperConfig.MIN_REVIEW_LENGTH:
                continue
            
            # Deduplicate
            sig = hashlib.md5(text[:100].encode()).hexdigest()
            if sig in seen:
                continue
            seen.add(sig)
            
            review_id = hashlib.sha256(f"{place_id}:{r.get('author', '')}:{text[:100]}".encode()).hexdigest()
            
            normalized.append({
                "google_review_id": review_id,
                "author": r.get("author", "Anonymous")[:100],
                "author_name": r.get("author", "Anonymous")[:100],
                "rating": min(5, max(1, int(r.get("rating", 5)))),
                "review_text": text[:ScraperConfig.MAX_REVIEW_LENGTH],
                "content": text[:ScraperConfig.MAX_REVIEW_LENGTH],
                "sentiment_score": 0.5,
                "google_review_time": datetime.utcnow(),
                "scraped_at": datetime.utcnow(),
                "extraction_source": source,
                "extraction_method": r.get("source", source)
            })
        
        return normalized

# =========================================================
# MAIN ENTRY POINT
# =========================================================

scraper_instance = UltimateGoogleScraper()

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Main entry point for scraping Google reviews"""
    return await scraper_instance.scrape(place_id)

async def run_scraper(place_id: str) -> List[Dict]:
    """Alias for compatibility"""
    return await scrape_google_reviews(place_id)

# =========================================================
# READY
# =========================================================

print("=" * 80)
print("✅ ULTIMATE SCRAPER V31.0 READY")
print(f"   Proxy Manager: {len(scraper_instance.proxy_manager.proxy_pool)} proxies (session rotation enabled)")
print(f"   Patchright: {'✅' if PATCHRIGHT_AVAILABLE else '❌'}")
print(f"   Playwright-Stealth: {'✅' if STEALTH_AVAILABLE else '❌'}")
print(f"   Fake UserAgent: {'✅' if FAKE_UA_AVAILABLE else '❌'}")
print(f"   Tenacity Retry: {'✅' if TENACITY_AVAILABLE else '❌'}")
print(f"   Backoff: {'✅' if BACKOFF_AVAILABLE else '❌'}")
print(f"   Selectolax: {'✅' if SELECTOLAX_AVAILABLE else '❌'}")
print(f"   Curl_CFFI: {'✅' if CURL_CFFI_AVAILABLE else '❌'}")
print(f"   CAPTCHA Detection: ✅")
print(f"   Human Behavior Simulation: ✅")
print(f"   Fingerprint Rotation: ✅")
print("=" * 80)
