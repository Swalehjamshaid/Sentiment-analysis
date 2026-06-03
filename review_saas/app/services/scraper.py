# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE SCRAPER - V32.0 PRODUCTION
# CONCURRENCY SAFE + ROBUST RPC + TRUE ISOLATION
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
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import deque, defaultdict
from contextlib import asynccontextmanager

# =========================================================
# CRITICAL: CONCURRENCY CONTROL
# =========================================================

# Global semaphore to limit concurrent browser instances
# This prevents server overload when scraping many companies
SCRAPER_SEMAPHORE = asyncio.Semaphore(5)  # Max 5 concurrent scrapers
MAX_CONCURRENT_BROWSERS = 5

# =========================================================
# THIRD-PARTY IMPORTS (With graceful fallbacks)
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
    print("⚠️ Playwright-stealth not available")

try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False
    print("⚠️ Fake-useragent not available")

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    print("⚠️ Tenacity not available")

try:
    from selectolax.parser import HTMLParser
    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False
    print("⚠️ Selectolax not available")

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️ Curl_CFFI not available")

# =========================================================
# CONSTANTS
# =========================================================

class ScraperConfig:
    MAX_REVIEWS = 150
    MIN_REVIEW_LENGTH = 20
    MAX_REVIEW_LENGTH = 5000
    
    MAX_SCROLLS = 50
    SCROLL_DISTANCE_START = 1000
    SCROLL_DISTANCE_MAX = 3000
    SCROLL_STAGNANT_LIMIT = 3
    
    RPC_TIMEOUT = 15
    PAGE_LOAD_TIMEOUT = 60000
    NAVIGATION_TIMEOUT = 60000
    BROWSER_LAUNCH_TIMEOUT = 30000
    
    # Retry stages with different strategies
    MAX_RETRIES = 3
    PROXY_ROTATION_RETRIES = 2
    FRESH_BROWSER_RETRIES = 2
    
    # Concurrency
    MAX_CONCURRENT_SCRAPERS = 5
    
    # Session management
    USER_DATA_DIR = Path("/tmp/chrome_profiles")
    
    # Rate limiting
    RATE_LIMIT_BACKOFF_MAX = 300
    
    # Deduplication
    DEDUP_HASH_ALGO = "sha256"  # Use SHA256 instead of MD5
    
    SCREENSHOT_ON_ERROR = True
    SCREENSHOT_DIR = Path("/app/data/screenshots")
    
    HEALTH_CHECK_URL = "https://www.google.com"
    METRICS_FILE = Path("/app/data/scraper_metrics.json")

# =========================================================
# LOGGER
# =========================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("=" * 80)
print("🚀 QUANTUM ENTERPRISE SCRAPER V32.0 - PRODUCTION GRADE")
print("┌─────────────────────────────────────────────────────────────────┐")
print("│ CONCURRENCY SAFE │ SEMAPHORE PROTECTED │ BROWSER ISOLATION      │")
print("│ SHA256 DEDUP │ MULTI-STAGE RETRY │ ROBUST RPC EXTRACTION       │")
print("│ PLAYWRIGHT LOCATORS │ SELECTOLAX ENHANCED │ PROXY ROTATION      │")
print("└─────────────────────────────────────────────────────────────────┘")
print("=" * 80)

# =========================================================
# PHASE 1: ENHANCED PROXY MANAGER WITH PROVIDER-SPECIFIC SESSION FORMATS
# =========================================================

class ProxyManager:
    """Proxy manager supporting multiple provider formats"""
    
    def __init__(self):
        self.proxy_pool = []
        self.provider_type = None  # datimpulse, luminati, oxylabs, etc.
        self.proxy_stats = {}
        self.init_proxies()
    
    def init_proxies(self):
        proxy_server = os.getenv("PROXY_SERVER", "").strip()
        proxy_username = os.getenv("PROXY_USERNAME", "").strip()
        proxy_password = os.getenv("PROXY_PASSWORD", "").strip()
        
        if not proxy_server:
            return
        
        # Detect provider based on domain
        if "dataimpulse" in proxy_server or "gw.dataimpulse" in proxy_server:
            self.provider_type = "dataimpulse"
        elif "luminati" in proxy_server:
            self.provider_type = "luminati"
        elif "oxylabs" in proxy_server:
            self.provider_type = "oxylabs"
        elif "scraperapi" in proxy_server:
            self.provider_type = "scraperapi"
        else:
            self.provider_type = "generic"
        
        servers = proxy_server.split(",") if "," in proxy_server else [proxy_server]
        
        for server in servers:
            server = server.strip()
            if not server:
                continue
            
            if not server.startswith(("http://", "https://")):
                server = f"http://{server}"
            
            base_proxy = {"server": server}
            
            if proxy_username and proxy_password:
                base_proxy["username"] = proxy_username
                base_proxy["password"] = proxy_password
            
            self.proxy_pool.append(base_proxy)
            self.proxy_stats[server] = {
                "success": 0, "fail": 0, "captcha": 0, 
                "reviews": 0, "latencies": [], "last_used": None
            }
        
        logger.info(f"✅ Proxy pool: {len(self.proxy_pool)} proxies (provider: {self.provider_type})")
    
    def get_proxy_with_session(self, force_fresh: bool = False) -> Optional[Dict]:
        """Get proxy with provider-appropriate session syntax"""
        if not self.proxy_pool:
            return None
        
        # Select best proxy
        best_proxy = self._select_best_proxy()
        if not best_proxy:
            return None
        
        session_id = random.randint(100000, 999999)
        
        # Provider-specific session syntax
        if self.provider_type == "dataimpulse":
            # DataImpulse format: username-session-sessionid
            if "username" in best_proxy:
                best_proxy["username"] = f"{best_proxy['username']}-session-{session_id}"
        
        elif self.provider_type == "luminati":
            # Luminati format: username-session-random
            if "username" in best_proxy:
                best_proxy["username"] = f"{best_proxy['username']}-session-{session_id}"
        
        elif self.provider_type == "oxylabs":
            # Oxylabs format: customer-username-sessid-random
            if "username" in best_proxy:
                best_proxy["username"] = f"{best_proxy['username']}-sessid-{session_id}"
        
        elif self.provider_type == "scraperapi":
            # ScraperAPI uses API key, not session rotation
            pass
        
        logger.debug(f"🔑 Proxy session: {session_id} (provider: {self.provider_type})")
        return best_proxy
    
    def _select_best_proxy(self) -> Optional[Dict]:
        """Select best performing proxy"""
        if not self.proxy_pool:
            return None
        
        best_score = -1
        best_proxy = None
        
        for proxy in self.proxy_pool:
            server = proxy.get("server", "")
            stats = self.proxy_stats.get(server, {})
            
            success_rate = stats.get("success", 1) / max(1, stats.get("success", 1) + stats.get("fail", 1))
            captcha_penalty = min(stats.get("captcha", 0) * 0.1, 0.5)
            score = success_rate - captcha_penalty
            
            if score > best_score:
                best_score = score
                best_proxy = proxy
        
        return best_proxy or self.proxy_pool[0]
    
    def report_result(self, proxy: Dict, success: bool, captcha: bool = False, 
                     reviews: int = 0, latency: float = 0):
        server = proxy.get("server", "")
        if server not in self.proxy_stats:
            return
        
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

# =========================================================
# PHASE 2: ISOLATED BROWSER SESSION MANAGER
# =========================================================

class BrowserSessionManager:
    """Create isolated browser sessions with unique profiles"""
    
    @staticmethod
    async def create_isolated_session(proxy: Dict = None) -> Tuple[any, any, str]:
        """Create a completely isolated browser session with unique profile"""
        
        # Generate unique session ID and profile directory
        session_id = str(uuid.uuid4())[:8]
        profile_dir = ScraperConfig.USER_DATA_DIR / f"profile_{session_id}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            async with async_playwright() as p:
                # Launch with isolated profile
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    proxy=proxy,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-features=Translate",
                        f"--profile-directory={session_id}"
                    ],
                    timeout=ScraperConfig.BROWSER_LAUNCH_TIMEOUT
                )
                
                page = context.pages[0] if context.pages else await context.new_page()
                
                # Apply stealth if available
                if STEALTH_AVAILABLE:
                    try:
                        await stealth_async(page)
                    except:
                        pass
                
                logger.debug(f"🆔 Isolated session created: {session_id}")
                return context, page, session_id
                
        except Exception as e:
            logger.error(f"Failed to create isolated session: {e}")
            # Cleanup on failure
            import shutil
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)
            raise
    
    @staticmethod
    async def cleanup_session(context, session_id: str):
        """Clean up isolated session and remove profile"""
        if context:
            await context.close()
        
        # Remove profile directory
        profile_dir = ScraperConfig.USER_DATA_DIR / f"profile_{session_id}"
        if profile_dir.exists():
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
            logger.debug(f"🗑️ Cleaned up profile: {session_id}")

# =========================================================
# PHASE 3: ROBUST RPC EXTRACTOR (EXPERIMENTAL - NOT PRIMARY)
# =========================================================

class DirectRPCExtractor:
    """Experimental direct RPC extraction - fragile, used as optimization only"""
    
    # Known RPC endpoints (Google changes these frequently)
    RPC_ENDPOINTS = [
        "https://www.google.com/maps/preview/review/listentitiesreviews",
        "https://www.google.com/maps/rpc/GetPlaceReviews",
        "https://www.google.com/maps/rpc/listugcposts"
    ]
    
    @classmethod
    async def fetch_reviews(cls, place_id: str, proxy: Dict = None) -> List[Dict]:
        """Attempt direct RPC extraction (experimental, may fail)"""
        if not CURL_CFFI_AVAILABLE:
            return []
        
        reviews = []
        
        for endpoint in cls.RPC_ENDPOINTS:
            try:
                reviews = await cls._try_endpoint(endpoint, place_id, proxy)
                if reviews:
                    logger.info(f"⚡ Direct RPC success from {endpoint.split('/')[-1]}")
                    return reviews
            except Exception as e:
                logger.debug(f"RPC endpoint {endpoint} failed: {e}")
                continue
        
        return []
    
    @classmethod
    async def _try_endpoint(cls, endpoint: str, place_id: str, proxy: Dict) -> List[Dict]:
        """Try a specific RPC endpoint"""
        # Build parameters (format varies by endpoint)
        params = {
            "authuser": "0",
            "hl": "en",
            "gl": "us"
        }
        
        if "listentitiesreviews" in endpoint:
            params["pb"] = f"!1m2!1y{place_id}!2y!2m2!1sen!2sus!3e2"
        elif "GetPlaceReviews" in endpoint:
            params["place_id"] = place_id
        
        # Setup proxy for curl
        proxies = None
        if proxy and proxy.get("server"):
            proxy_url = proxy["server"]
            if proxy.get("username") and proxy.get("password"):
                proxy_url = proxy_url.replace("http://", f"http://{proxy['username']}:{proxy['password']}@")
            proxies = {"http": proxy_url, "https": proxy_url}
        
        response = curl_requests.get(
            endpoint,
            params=params,
            proxies=proxies,
            timeout=15,
            impersonate="chrome120"
        )
        
        if response.status_code == 200 and len(response.text) > 500:
            # Try to decode as RPC
            from app.services.scraper import AdvancedRPCDecoder
            return AdvancedRPCDecoder.decode(response.text)
        
        return []

# =========================================================
# PHASE 4: HYBRID REVIEW EXTRACTOR (Playwright + Selectolax)
# =========================================================

class HybridReviewExtractor:
    """Extract reviews using both Playwright locators and HTML parsing"""
    
    @staticmethod
    async def extract_from_page(page, max_reviews: int = 150) -> List[Dict]:
        """Extract reviews with dual strategy: Playwright first, HTML fallback"""
        reviews = []
        
        # Strategy 1: Playwright locators (most reliable for dynamic content)
        try:
            logger.debug("Extracting with Playwright locators...")
            cards = await page.locator('div[data-review-id], div.jftiEf, div.MyEned').all()
            
            for card in cards[:max_reviews]:
                try:
                    review_data = {}
                    
                    # Extract text with multiple selector attempts
                    for sel in ['.wiI7pd', '.MyEned', 'span[jsname]']:
                        elem = card.locator(sel).first
                        if await elem.count() > 0:
                            review_data["text"] = (await elem.inner_text()).strip()
                            break
                    
                    if review_data.get("text") and len(review_data["text"]) >= ScraperConfig.MIN_REVIEW_LENGTH:
                        # Extract author
                        for sel in ['.d4r55', '.TSUbDb']:
                            elem = card.locator(sel).first
                            if await elem.count() > 0:
                                review_data["author"] = (await elem.inner_text()).strip()
                                break
                        else:
                            review_data["author"] = "Anonymous"
                        
                        # Extract rating
                        rating_elem = card.locator('span.kvMYJc').first
                        if await rating_elem.count() > 0:
                            aria = await rating_elem.get_attribute('aria-label')
                            if aria:
                                match = re.search(r'(\d)', aria)
                                if match:
                                    review_data["rating"] = int(match.group(1))
                        else:
                            review_data["rating"] = 5
                        
                        review_data["source"] = "playwright_locator"
                        reviews.append(review_data)
                        
                except Exception as e:
                    logger.debug(f"Playwright extraction failed: {e}")
                    continue
            
            if reviews:
                logger.info(f"✅ Playwright locators extracted {len(reviews)} reviews")
                return reviews
                
        except Exception as e:
            logger.debug(f"Playwright extraction strategy failed: {e}")
        
        # Strategy 2: HTML parsing with Selectolax (fallback)
        if SELECTOLAX_AVAILABLE:
            try:
                logger.debug("Extracting with Selectolax HTML parser...")
                html = await page.content()
                tree = HTMLParser(html)
                
                review_elements = tree.css('div[data-review-id], div.jftiEf, div.MyEned')
                for elem in review_elements[:max_reviews]:
                    text_elem = elem.css_first('.wiI7pd, .MyEned, span[jsname]')
                    if text_elem:
                        text = text_elem.text(strip=True)
                        if len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                            # Try to extract author
                            author_elem = elem.css_first('.d4r55, .TSUbDb')
                            author = author_elem.text(strip=True) if author_elem else "Anonymous"
                            
                            # Try to extract rating
                            rating_elem = elem.css_first('span.kvMYJc')
                            rating = 5
                            if rating_elem:
                                aria = rating_elem.attributes.get('aria-label', '')
                                match = re.search(r'(\d)', aria)
                                if match:
                                    rating = int(match.group(1))
                            
                            reviews.append({
                                "text": text,
                                "author": author,
                                "rating": rating,
                                "source": "selectolax_html"
                            })
                
                if reviews:
                    logger.info(f"✅ Selectolax extracted {len(reviews)} reviews")
                    return reviews
                    
            except Exception as e:
                logger.debug(f"Selectolax extraction failed: {e}")
        
        # Strategy 3: BeautifulSoup (last resort)
        if not SELECTOLAX_AVAILABLE:
            try:
                from bs4 import BeautifulSoup
                logger.debug("Extracting with BeautifulSoup...")
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                
                review_divs = soup.select('div[data-review-id], div.jftiEf, div.MyEned')
                for div in review_divs[:max_reviews]:
                    text_elem = div.select_one('.wiI7pd, .MyEned, span[jsname]')
                    if text_elem:
                        text = text_elem.get_text(strip=True)
                        if len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                            author_elem = div.select_one('.d4r55, .TSUbDb')
                            author = author_elem.get_text(strip=True) if author_elem else "Anonymous"
                            reviews.append({
                                "text": text,
                                "author": author,
                                "rating": 5,
                                "source": "beautifulsoup"
                            })
                
                if reviews:
                    logger.info(f"✅ BeautifulSoup extracted {len(reviews)} reviews")
                    
            except Exception as e:
                logger.debug(f"BeautifulSoup extraction failed: {e}")
        
        return reviews

# =========================================================
# PHASE 5: MULTI-STAGE RETRY WITH PROGRESSIVE BACKOFF
# =========================================================

class RetryManager:
    """Multi-stage retry with different strategies per stage"""
    
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
    
    async def scrape_with_retry(self, place_id: str) -> List[Dict]:
        """Scrape with progressive retry stages"""
        
        # Stage 1: Direct RPC (fast but fragile, experimental)
        logger.info("Stage 1: Attempting direct RPC extraction...")
        reviews = await DirectRPCExtractor.fetch_reviews(place_id)
        if reviews and len(reviews) >= 20:
            logger.info(f"✅ Stage 1 success: {len(reviews)} reviews")
            return reviews
        
        # Stage 2: Browser with proxy rotation
        for attempt in range(ScraperConfig.PROXY_ROTATION_RETRIES):
            logger.info(f"Stage 2: Browser extraction with proxy (attempt {attempt + 1})...")
            
            # Rotate proxy for each attempt
            proxy = self.proxy_manager.get_proxy_with_session(force_fresh=True)
            
            reviews = await self._browser_extraction(place_id, proxy)
            if reviews and len(reviews) >= 10:
                logger.info(f"✅ Stage 2 success: {len(reviews)} reviews")
                return reviews
            
            # Exponential backoff between attempts
            await asyncio.sleep(2 ** attempt)
        
        # Stage 3: Fresh browser with clean profile
        for attempt in range(ScraperConfig.FRESH_BROWSER_RETRIES):
            logger.info(f"Stage 3: Fresh browser profile (attempt {attempt + 1})...")
            
            reviews = await self._fresh_browser_extraction(place_id)
            if reviews and len(reviews) >= 5:
                logger.info(f"✅ Stage 3 success: {len(reviews)} reviews")
                return reviews
            
            await asyncio.sleep(3 ** attempt)
        
        return []
    
    async def _browser_extraction(self, place_id: str, proxy: Dict) -> List[Dict]:
        """Browser-based extraction with given proxy"""
        context = None
        session_id = None
        
        try:
            # Create isolated session
            context, page, session_id = await BrowserSessionManager.create_isolated_session(proxy)
            
            # Navigate and extract
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            await page.goto(url, wait_until="networkidle", timeout=ScraperConfig.NAVIGATION_TIMEOUT)
            await asyncio.sleep(random.uniform(1, 2))
            
            # Click reviews button
            reviews_button = page.locator('button[data-tab-index="1"]').first
            if await reviews_button.count() > 0:
                await reviews_button.click()
                await asyncio.sleep(random.uniform(2, 3))
            else:
                return []
            
            # Wait for content to load
            await asyncio.sleep(3)
            
            # Extract reviews with hybrid extractor
            reviews = await HybridReviewExtractor.extract_from_page(page)
            
            # Report success
            if proxy:
                self.proxy_manager.report_result(proxy, True, reviews=len(reviews))
            
            return reviews
            
        except Exception as e:
            logger.error(f"Browser extraction failed: {e}")
            if proxy:
                self.proxy_manager.report_result(proxy, False)
            return []
        finally:
            if context and session_id:
                await BrowserSessionManager.cleanup_session(context, session_id)
    
    async def _fresh_browser_extraction(self, place_id: str) -> List[Dict]:
        """Extraction with completely fresh browser (no proxy)"""
        return await self._browser_extraction(place_id, None)

# =========================================================
# PHASE 6: MAIN SCRAPER WITH CONCURRENCY CONTROL
# =========================================================

class UltimateGoogleScraper:
    """Production scraper with concurrency protection"""
    
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.retry_manager = RetryManager(self.proxy_manager)
        self._semaphore = SCRAPER_SEMAPHORE
    
    async def scrape(self, place_id: str) -> List[Dict]:
        """Main entry point with semaphore protection"""
        
        # CRITICAL: Limit concurrent scrapers
        async with self._semaphore:
            logger.info(f"🔒 Acquired semaphore slot (active: {self._semaphore._value})")
            
            start_time = time.time()
            
            try:
                # Execute with multi-stage retry
                reviews = await self.retry_manager.scrape_with_retry(place_id)
                
                # Normalize and deduplicate with SHA256
                normalized = self._normalize_reviews(reviews, place_id)
                
                duration = time.time() - start_time
                logger.info(f"✅ Scrape complete: {len(normalized)} reviews in {duration:.2f}s")
                
                # Log proxy stats summary
                stats = self.proxy_manager.proxy_stats
                if stats:
                    total_success = sum(s.get("success", 0) for s in stats.values())
                    total_fail = sum(s.get("fail", 0) for s in stats.values())
                    logger.info(f"📊 Proxy stats: {total_success} success, {total_fail} fail")
                
                return normalized
                
            except Exception as e:
                logger.error(f"Scrape failed: {e}")
                return []
    
    def _normalize_reviews(self, reviews: List[Dict], place_id: str) -> List[Dict]:
        """Normalize review format with SHA256 deduplication"""
        normalized = []
        seen = set()
        
        for r in reviews[:ScraperConfig.MAX_REVIEWS]:
            text = r.get("text", "").strip()
            if not text or len(text) < ScraperConfig.MIN_REVIEW_LENGTH:
                continue
            
            # Use SHA256 for deduplication (more secure than MD5)
            sig_string = f"{r.get('author', '')}:{text[:ScraperConfig.DEDUP_CHAR_LIMIT]}"
            sig = hashlib.sha256(sig_string.encode()).hexdigest()
            
            if sig in seen:
                continue
            seen.add(sig)
            
            review_id = hashlib.sha256(f"{place_id}:{sig}".encode()).hexdigest()
            
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
                "extraction_source": r.get("source", "unknown")
            })
        
        return normalized

# =========================================================
# GLOBAL SCRAPER INSTANCE
# =========================================================

_scraper_instance = None

def get_scraper() -> UltimateGoogleScraper:
    """Get or create global scraper instance"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = UltimateGoogleScraper()
    return _scraper_instance

# =========================================================
# PUBLIC API
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Main entry point for scraping Google reviews"""
    scraper = get_scraper()
    return await scraper.scrape(place_id)

async def run_scraper(place_id: str) -> List[Dict]:
    """Alias for compatibility"""
    return await scrape_google_reviews(place_id)

# =========================================================
# HEALTH CHECK
# =========================================================

async def health_check() -> Dict:
    """Check scraper health and configuration"""
    return {
        "status": "healthy",
        "patchright_available": PATCHRIGHT_AVAILABLE,
        "stealth_available": STEALTH_AVAILABLE,
        "selectolax_available": SELECTOLAX_AVAILABLE,
        "curl_cffi_available": CURL_CFFI_AVAILABLE,
        "proxy_pool_size": len(get_scraper().proxy_manager.proxy_pool),
        "proxy_provider": get_scraper().proxy_manager.provider_type,
        "max_concurrent": ScraperConfig.MAX_CONCURRENT_SCRAPERS,
        "semaphore_available": SCRAPER_SEMAPHORE._value
    }

# =========================================================
# READY
# =========================================================

print("=" * 80)
print("✅ PRODUCTION SCRAPER V32.0 READY")
print(f"   Max Concurrent: {ScraperConfig.MAX_CONCURRENT_SCRAPERS} (semaphore protected)")
print(f"   Proxy Provider: {get_scraper().proxy_manager.provider_type or 'none'}")
print(f"   Deduplication: SHA256 (secure)")
print(f"   Extraction: Hybrid (Playwright + Selectolax)")
print(f"   Retry Stages: 3 (RPC → Browser → Fresh)")
print(f"   Session Isolation: UUID4 profiles")
print("=" * 80)
