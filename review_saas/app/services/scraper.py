# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE SCRAPER - V34.0 "PHOENIX"
# NEW INNOVATIVE LOGIC FOR RELIABLE DATA EXTRACTION
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
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import deque, defaultdict
from contextlib import asynccontextmanager

# =========================================================
# CONCURRENCY CONTROL
# =========================================================

SCRAPER_SEMAPHORE = asyncio.Semaphore(5)
MAX_CONCURRENT_BROWSERS = 5

# =========================================================
# THIRD-PARTY IMPORTS
# =========================================================

try:
    from patchright.async_api import async_playwright as patchright_playwright
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    from playwright.async_api import async_playwright as patchright_playwright
    PATCHRIGHT_AVAILABLE = False
    print("⚠️ Patchright not available - using Playwright")

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

# =========================================================
# CONSTANTS (unchanged to keep integrations)
# =========================================================

class ScraperConfig:
    MAX_REVIEWS = 150
    MIN_REVIEW_LENGTH = 20
    MAX_REVIEW_LENGTH = 5000
    
    # Infinite scroll settings
    MAX_SCROLLS = 60
    SCROLL_DISTANCE = 3000
    SCROLL_DELAY_MIN = 1.0
    SCROLL_DELAY_MAX = 2.0
    SCROLL_STAGNANT_LIMIT = 3
    
    # Timeouts
    RPC_TIMEOUT = 15
    PAGE_LOAD_TIMEOUT = 60000
    NAVIGATION_TIMEOUT = 60000
    BROWSER_LAUNCH_TIMEOUT = 30000
    
    # Retry settings
    MAX_RETRIES = 3
    
    # Session management
    USER_DATA_DIR = Path("/tmp/chrome_profiles")
    
    # Debugging
    SCREENSHOT_ON_FAILURE = True
    SCREENSHOT_DIR = Path("/app/data/screenshots")
    
    # Health check
    HEALTH_CHECK_URL = "https://www.google.com"
    IP_CHECK_URL = "https://api.ipify.org?format=json"

# =========================================================
# LOGGER (unchanged)
# =========================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add detailed logging for debugging
DETAILED_LOGGING = os.getenv("DETAILED_LOGGING", "false").lower() == "true"
if DETAILED_LOGGING:
    logger.setLevel(logging.DEBUG)

print("=" * 80)
print("🚀 QUANTUM ENTERPRISE SCRAPER V34.0 - PHOENIX EDITION")
print("┌─────────────────────────────────────────────────────────────────┐")
print("│ MULTI-STRATEGY EXTRACTION │ ADAPTIVE SCROLL                    │")
print("│ SELECTOR ROTATION │ RPC SNIFFING │ REGEX FALLBACK              │")
print("│ DEDUPLICATION │ METADATA ENRICHMENT                           │")
print("└─────────────────────────────────────────────────────────────────┘")
print("=" * 80)

# =========================================================
# PHASE 1: FIXED BROWSER SESSION MANAGER (unchanged, but we keep)
# =========================================================

class BrowserSessionManager:
    """Fixed browser session manager - proper lifecycle management"""
    
    @staticmethod
    async def create_isolated_session(proxy: Dict = None) -> Tuple[any, any, any, str]:
        """Create isolated session WITHOUT async with bug"""
        
        session_id = str(uuid.uuid4())[:8]
        profile_dir = ScraperConfig.USER_DATA_DIR / f"profile_{session_id}"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            playwright = await patchright_playwright().start()
            context = await playwright.chromium.launch_persistent_context(
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
            
            if STEALTH_AVAILABLE:
                try:
                    await stealth_async(page)
                    logger.debug("✅ Stealth applied")
                except Exception as e:
                    logger.debug(f"Stealth failed: {e}")
            
            logger.debug(f"🆔 Isolated session created: {session_id}")
            return playwright, context, page, session_id
            
        except Exception as e:
            logger.error(f"Failed to create isolated session: {e}")
            import shutil
            if profile_dir.exists():
                shutil.rmtree(profile_dir, ignore_errors=True)
            raise
    
    @staticmethod
    async def cleanup_session(playwright, context, session_id: str):
        """Proper cleanup of all resources"""
        if context:
            await context.close()
        if playwright:
            await playwright.stop()
        
        profile_dir = ScraperConfig.USER_DATA_DIR / f"profile_{session_id}"
        if profile_dir.exists():
            import shutil
            shutil.rmtree(profile_dir, ignore_errors=True)
            logger.debug(f"🗑️ Cleaned up profile: {session_id}")

# =========================================================
# PHASE 2: NEW ADAPTIVE SCROLL ENGINE
# =========================================================

class AdaptiveScrollEngine:
    """Intelligent scroll that detects when new content loads"""
    
    @staticmethod
    async def scroll_until_exhaustion(page) -> Tuple[int, int]:
        """
        Adaptive scroll with dynamic waiting and change detection.
        Returns (scroll_count, total_reviews_found)
        """
        scroll_count = 0
        stagnant_count = 0
        last_review_count = 0
        total_reviews = 0
        review_elements = []
        
        # Predefined scroll containers in order of likelihood
        containers = [
            'div[role="feed"]',
            '.section-scrollbox',
            'div[data-review-id]',
            'div[role="main"]',
            'body'
        ]
        
        # Find best container
        container_selector = None
        for sel in containers:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    container_selector = sel
                    logger.info(f"📦 Using container: {sel}")
                    break
            except:
                continue
        
        if not container_selector:
            container_selector = 'body'
            logger.warning("⚠️ No specific container found, scrolling body")
        
        logger.info("📜 Starting adaptive infinite scroll...")
        
        for i in range(ScraperConfig.MAX_SCROLLS):
            # Scroll the container
            try:
                if container_selector == 'body':
                    await page.evaluate("window.scrollBy(0, 3000)")
                else:
                    await page.evaluate(f"""
                        const el = document.querySelector('{container_selector}');
                        if (el) el.scrollTop += 3000;
                    """)
            except:
                await page.evaluate("window.scrollBy(0, 3000)")
            
            # Dynamic delay based on network speed estimate
            delay = random.uniform(ScraperConfig.SCROLL_DELAY_MIN, ScraperConfig.SCROLL_DELAY_MAX)
            # After first few scrolls, increase delay to let content load
            if i > 10:
                delay *= 1.5
            await asyncio.sleep(delay)
            
            # Count visible review cards
            current_count = await AdaptiveScrollEngine._count_review_cards(page)
            total_reviews = max(total_reviews, current_count)
            
            # Log progress
            if i % 5 == 0:
                logger.info(f"📜 Scroll {i}: {current_count} reviews visible")
            
            # Check stagnation
            if current_count == last_review_count:
                stagnant_count += 1
                if stagnant_count >= ScraperConfig.SCROLL_STAGNANT_LIMIT:
                    logger.info(f"📜 Stagnant after {i} scrolls - stopping")
                    break
            else:
                stagnant_count = 0
                last_review_count = current_count
            
            # Early exit if we have enough
            if current_count >= ScraperConfig.MAX_REVIEWS:
                logger.info(f"📜 Target reached: {current_count} reviews")
                break
            
            scroll_count += 1
        else:
            logger.info(f"📜 Max scrolls reached ({ScraperConfig.MAX_SCROLLS})")
        
        # Final count
        final_count = await AdaptiveScrollEngine._count_review_cards(page)
        logger.info(f"📜 Final review card count: {final_count}")
        return scroll_count, final_count
    
    @staticmethod
    async def _count_review_cards(page) -> int:
        """Count review cards using multiple strategies"""
        selectors = [
            'div[data-review-id]',
            'div.jftiEf',
            'div.MyEned',
            'div[role="article"]',
            'div[jsaction*="review"]'
        ]
        max_count = 0
        for sel in selectors:
            try:
                count = await page.locator(sel).count()
                if count > max_count:
                    max_count = count
            except:
                continue
        return max_count

# =========================================================
# PHASE 3: RPC SNIFFER + API EXTRACTION
# =========================================================

class RPCSniffer:
    """Intercept RPC responses and also sniff other API endpoints"""
    
    def __init__(self):
        self.captured_data = []
        self.received_event = asyncio.Event()
    
    async def setup(self, page):
        """Setup response interception"""
        
        def on_response(response):
            asyncio.create_task(self._process_response(response))
        
        page.on("response", on_response)
        logger.info("📡 RPC sniffer active")
    
    async def _process_response(self, response):
        """Process potential review-bearing responses"""
        try:
            url = response.url
            # Targets: batchexecute, GetPlaceReviews, listugcposts, etc.
            if any(k in url for k in ['batchexecute', 'review', 'rpc', 'listugcposts', 'GetReviews']):
                if response.status == 200:
                    # Try to get JSON body
                    try:
                        body = await response.text()
                        if body and len(body) > 500:
                            # Attempt to extract reviews
                            reviews = self._extract_from_payload(body)
                            if reviews:
                                self.captured_data.extend(reviews)
                                self.received_event.set()
                                logger.info(f"📡 Sniffed {len(reviews)} reviews from {url[:60]}")
                    except:
                        pass
        except:
            pass
    
    def _extract_from_payload(self, payload: str) -> List[Dict]:
        """Extract reviews from various payload formats (JSON, JSONP, RPC)"""
        reviews = []
        
        # Try JSON parse
        try:
            data = json.loads(payload)
            # Recursively search for review-like objects
            reviews = self._search_reviews_in_json(data)
            if reviews:
                return reviews
        except:
            pass
        
        # Fallback to regex
        patterns = [
            r'"reviewText":"([^"\\]*(?:\\.[^"\\]*)*)"',
            r'"text":"([^"\\]*(?:\\.[^"\\]*)*)"',
            r'"snippet":"([^"\\]*(?:\\.[^"\\]*)*)"',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, payload)
            for match in matches:
                if len(match) >= ScraperConfig.MIN_REVIEW_LENGTH:
                    rating = 5
                    # Try to find rating nearby
                    rating_match = re.search(r'"rating":(\d+)', payload)
                    if rating_match:
                        rating = int(rating_match.group(1))
                    author = "Anonymous"
                    author_match = re.search(r'"authorName":"([^"]+)"', payload)
                    if author_match:
                        author = author_match.group(1)
                    reviews.append({
                        "text": match[:ScraperConfig.MAX_REVIEW_LENGTH],
                        "author": author,
                        "rating": rating,
                        "source": "rpc_regex"
                    })
        return reviews
    
    def _search_reviews_in_json(self, obj) -> List[Dict]:
        """Recursively search JSON for review-like structures"""
        results = []
        if isinstance(obj, dict):
            # Check if this looks like a review
            text_keys = ['text', 'reviewText', 'snippet', 'content']
            for key in text_keys:
                if key in obj and isinstance(obj[key], str) and len(obj[key]) >= ScraperConfig.MIN_REVIEW_LENGTH:
                    review = {
                        "text": obj[key][:ScraperConfig.MAX_REVIEW_LENGTH],
                        "author": obj.get('authorName') or obj.get('author', {}).get('displayName') or "Anonymous",
                        "rating": obj.get('rating') or obj.get('starRating', 5),
                        "source": "json_extract"
                    }
                    if isinstance(review["rating"], str):
                        review["rating"] = int(re.search(r'\d+', review["rating"]).group(0)) if re.search(r'\d+', review["rating"]) else 5
                    results.append(review)
            # Recurse
            for v in obj.values():
                results.extend(self._search_reviews_in_json(v))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(self._search_reviews_in_json(item))
        return results
    
    def get_captured(self) -> List[Dict]:
        return self.captured_data

# =========================================================
# PHASE 4: DOM EXTRACTOR WITH SMART SELECTOR ROTATION
# =========================================================

class DOMExtractor:
    """Extract reviews using a rotating set of selectors"""
    
    # Comprehensive list of selectors (CSS and XPath)
    CARD_SELECTORS = [
        'div[data-review-id]',
        'div.jftiEf',
        'div.MyEned',
        'div[role="article"]',
        'div[jsaction*="review"]',
        'div[class*="review"]',
        'div[data-review]',
        '.review-card',
        '.review-container',
        'div[class*="widget-pane"] div[role="article"]',
        'xpath=//div[contains(@data-review-id, "")]',
        'xpath=//div[contains(@class, "jftiEf")]',
    ]
    
    TEXT_SELECTORS = [
        '.wiI7pd',
        '.MyEned',
        'span[jsname]',
        '.review-text',
        '[data-review-text]',
        '.review-content',
        'span[aria-hidden="true"]',
        'xpath=//span[contains(@class, "wiI7pd")]',
    ]
    
    AUTHOR_SELECTORS = [
        '.d4r55',
        '.TSUbDb',
        '[data-author]',
        '.author-name',
        'a[href*="user"]',
        '.reviewer-name',
        'xpath=//span[contains(@class, "d4r55")]',
    ]
    
    RATING_SELECTORS = [
        'span.kvMYJc',
        '[aria-label*="stars"]',
        '[role="img"][aria-label*="star"]',
        '.rating-value',
        '.star-rating',
        'xpath=//span[contains(@aria-label, "star")]',
    ]
    
    DATE_SELECTORS = [
        '.rsqaWe',
        '.dehysf',
        '.review-date',
        '[data-date]',
        '.rating-time',
        'xpath=//span[contains(@class, "rsqaWe")]',
    ]
    
    @classmethod
    async def extract_reviews(cls, page) -> List[Dict]:
        """Extract using best-performing selector combination"""
        reviews = []
        
        # Try each card selector
        for card_sel in cls.CARD_SELECTORS:
            try:
                # For XPath, use locator with xpath= prefix
                if card_sel.startswith('xpath='):
                    locator = page.locator(card_sel[6:])
                else:
                    locator = page.locator(card_sel)
                
                cards = await locator.all()
                if cards:
                    logger.info(f"🔍 Found {len(cards)} cards with selector: {card_sel[:50]}")
                    for card in cards[:ScraperConfig.MAX_REVIEWS]:
                        review = await cls._extract_from_card(card)
                        if review and review.get("text"):
                            reviews.append(review)
                    if reviews:
                        logger.info(f"✅ Extracted {len(reviews)} reviews using {card_sel[:50]}")
                        return reviews
            except Exception as e:
                logger.debug(f"Selector {card_sel} failed: {e}")
                continue
        
        return reviews
    
    @classmethod
    async def _extract_from_card(cls, card) -> Optional[Dict]:
        """Extract data from a single card using multiple sub-selectors"""
        try:
            review_data = {}
            
            # Extract text
            for text_sel in cls.TEXT_SELECTORS:
                try:
                    if text_sel.startswith('xpath='):
                        elem = card.locator(text_sel[6:]).first
                    else:
                        elem = card.locator(text_sel).first
                    if await elem.count() > 0:
                        text = (await elem.inner_text()).strip()
                        if text and len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                            review_data["text"] = text[:ScraperConfig.MAX_REVIEW_LENGTH]
                            break
                except:
                    continue
            if not review_data.get("text"):
                return None
            
            # Author
            for auth_sel in cls.AUTHOR_SELECTORS:
                try:
                    if auth_sel.startswith('xpath='):
                        elem = card.locator(auth_sel[6:]).first
                    else:
                        elem = card.locator(auth_sel).first
                    if await elem.count() > 0:
                        author = (await elem.inner_text()).strip()
                        if author:
                            review_data["author"] = author
                            break
                except:
                    continue
            if "author" not in review_data:
                review_data["author"] = "Anonymous"
            
            # Rating
            for rate_sel in cls.RATING_SELECTORS:
                try:
                    if rate_sel.startswith('xpath='):
                        elem = card.locator(rate_sel[6:]).first
                    else:
                        elem = card.locator(rate_sel).first
                    if await elem.count() > 0:
                        aria = await elem.get_attribute('aria-label')
                        if aria:
                            nums = re.findall(r'\d+', aria)
                            if nums:
                                review_data["rating"] = int(nums[0])
                                break
                        # Try inner text
                        text = await elem.inner_text()
                        nums = re.findall(r'\d+', text)
                        if nums:
                            review_data["rating"] = int(nums[0])
                            break
                except:
                    continue
            if "rating" not in review_data:
                review_data["rating"] = 5
            
            # Date
            for date_sel in cls.DATE_SELECTORS:
                try:
                    if date_sel.startswith('xpath='):
                        elem = card.locator(date_sel[6:]).first
                    else:
                        elem = card.locator(date_sel).first
                    if await elem.count() > 0:
                        date_text = (await elem.inner_text()).strip()
                        if date_text:
                            review_data["date"] = date_text
                            break
                except:
                    continue
            
            review_data["source"] = "dom_extraction"
            return review_data
        except:
            return None

# =========================================================
# PHASE 5: REGEX FALLBACK (last resort)
# =========================================================

class RegexFallback:
    """Extract reviews from raw HTML when DOM methods fail"""
    
    @classmethod
    def extract_from_html(cls, html: str) -> List[Dict]:
        """Use regular expressions to find review snippets"""
        reviews = []
        # Patterns to find review text blocks
        text_patterns = [
            r'>([^<]{30,500}?)<',  # any text between tags with length 30-500
        ]
        for pattern in text_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if len(match) >= ScraperConfig.MIN_REVIEW_LENGTH:
                    # Try to find nearby rating
                    rating = 5
                    rating_match = re.search(r'(\d)\s*star', html[max(0, html.find(match)-500):html.find(match)+100], re.I)
                    if rating_match:
                        rating = int(rating_match.group(1))
                    reviews.append({
                        "text": match[:ScraperConfig.MAX_REVIEW_LENGTH],
                        "author": "Unknown",
                        "rating": rating,
                        "source": "regex_fallback"
                    })
        return reviews

# =========================================================
# PHASE 6: MAIN SCRAPER (unchanged signature)
# =========================================================

class UltimateGoogleScraper:
    """Production scraper with all improvements - signature intact"""
    
    def __init__(self):
        self._semaphore = SCRAPER_SEMAPHORE
        self.proxy_pool = self._init_proxy_pool()
    
    def _init_proxy_pool(self) -> List[Dict]:
        """Initialize proxy pool from environment"""
        proxy_server = os.getenv("PROXY_SERVER", "").strip()
        proxy_username = os.getenv("PROXY_USERNAME", "").strip()
        proxy_password = os.getenv("PROXY_PASSWORD", "").strip()
        
        proxies = []
        if proxy_server:
            servers = proxy_server.split(",") if "," in proxy_server else [proxy_server]
            for server in servers:
                server = server.strip()
                if server:
                    if not server.startswith(("http://", "https://")):
                        server = f"http://{server}"
                    
                    proxy_config = {"server": server}
                    if proxy_username and proxy_password:
                        proxy_config["username"] = proxy_username
                        proxy_config["password"] = proxy_password
                    
                    proxies.append(proxy_config)
            
            logger.info(f"✅ Initialized {len(proxies)} proxies")
        
        return proxies
    
    async def scrape(self, place_id: str) -> List[Dict]:
        """Main scrape method - signature unchanged"""
        async with self._semaphore:
            logger.info("=" * 80)
            logger.info(f"🚀 Starting scrape: {place_id}")
            start_time = time.time()
            
            for attempt, proxy in enumerate(self.proxy_pool or [None]):
                logger.info(f"📡 Attempt {attempt + 1}/{max(1, len(self.proxy_pool) or 1)}")
                if proxy:
                    logger.info(f"🌐 Verifying proxy: {proxy.get('server', 'unknown')[:50]}")
                
                reviews = await self._scrape_with_playwright(place_id, proxy)
                
                if reviews and len(reviews) >= 10:
                    duration = time.time() - start_time
                    logger.info("=" * 80)
                    logger.info(f"✅ SUCCESS: {len(reviews)} reviews in {duration:.2f}s")
                    logger.info("=" * 80)
                    return reviews
                
                if proxy and attempt < len(self.proxy_pool) - 1:
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed, rotating proxy...")
                    await asyncio.sleep(2)
            
            logger.error(f"❌ All attempts failed for {place_id}")
            return []
    
    async def _scrape_with_playwright(self, place_id: str, proxy: Dict) -> List[Dict]:
        """Scrape with multi-strategy extraction"""
        playwright = None
        context = None
        session_id = None
        
        try:
            # Create session
            playwright, context, page, session_id = await BrowserSessionManager.create_isolated_session(proxy)
            
            # Setup RPC sniffer
            rpc = RPCSniffer()
            await rpc.setup(page)
            
            # Navigate
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            logger.info(f"🌐 Navigating to: {url[:80]}")
            await page.goto(url, wait_until="networkidle", timeout=ScraperConfig.NAVIGATION_TIMEOUT)
            await asyncio.sleep(random.uniform(1, 2))
            
            # Find and click reviews button (multiple selectors)
            button_clicked = False
            for selector in [
                'button[data-tab-index="1"]',
                'button[aria-label*="reviews" i]',
                'button[aria-label*="Reviews"]',
                'button[jsaction*="review"]',
                'button[aria-label*="stars"]'
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click()
                        logger.info(f"✅ Clicked reviews button: {selector[:50]}")
                        button_clicked = True
                        break
                except:
                    continue
            
            if not button_clicked:
                logger.error("❌ Could not find reviews button")
                return []
            
            await asyncio.sleep(random.uniform(2, 3))
            
            # ---- EXTRACTION PHASE ----
            all_reviews = []
            
            # 1. Try RPC captured reviews
            await asyncio.sleep(3)  # Give RPC time
            rpc_reviews = rpc.get_captured()
            if rpc_reviews:
                logger.info(f"📡 RPC yielded {len(rpc_reviews)} reviews")
                all_reviews.extend(rpc_reviews)
            
            # 2. Adaptive scroll + DOM extraction
            scroll_count, card_count = await AdaptiveScrollEngine.scroll_until_exhaustion(page)
            logger.info(f"📜 Scrolled {scroll_count} times, {card_count} cards visible")
            
            dom_reviews = await DOMExtractor.extract_reviews(page)
            logger.info(f"📝 DOM extraction: {len(dom_reviews)} reviews")
            all_reviews.extend(dom_reviews)
            
            # 3. If we have few or none, try regex fallback on full HTML
            if len(all_reviews) < 5:
                html = await page.content()
                regex_reviews = RegexFallback.extract_from_html(html)
                logger.info(f"🔍 Regex fallback: {len(regex_reviews)} reviews")
                all_reviews.extend(regex_reviews)
            
            # 4. Deduplicate and normalize
            final_reviews = self._normalize_reviews(all_reviews, place_id)
            logger.info(f"✅ Final normalized: {len(final_reviews)} reviews")
            
            if not final_reviews and ScraperConfig.SCREENSHOT_ON_FAILURE:
                screenshot_path = ScraperConfig.SCREENSHOT_DIR / f"no_reviews_{place_id}_{int(time.time())}.png"
                await page.screenshot(path=str(screenshot_path))
                logger.warning(f"📸 No reviews, screenshot: {screenshot_path}")
            
            return final_reviews
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            if playwright and context:
                await BrowserSessionManager.cleanup_session(playwright, context, session_id)
    
    def _normalize_reviews(self, reviews: List[Dict], place_id: str) -> List[Dict]:
        """Normalize and deduplicate - signature unchanged"""
        normalized = []
        seen = set()
        
        for review in reviews[:ScraperConfig.MAX_REVIEWS]:
            text = review.get("text", "").strip()
            if not text or len(text) < ScraperConfig.MIN_REVIEW_LENGTH:
                continue
            
            # Create unique signature
            signature = hashlib.sha256(
                f"{review.get('author', '')}:{text[:100]}".encode()
            ).hexdigest()
            
            if signature in seen:
                continue
            seen.add(signature)
            
            review_id = hashlib.sha256(f"{place_id}:{signature}".encode()).hexdigest()
            
            normalized.append({
                "google_review_id": review_id,
                "author": review.get("author", "Anonymous")[:100],
                "author_name": review.get("author", "Anonymous")[:100],
                "rating": min(5, max(1, int(review.get("rating", 5)))),
                "review_text": text[:ScraperConfig.MAX_REVIEW_LENGTH],
                "content": text[:ScraperConfig.MAX_REVIEW_LENGTH],
                "sentiment_score": 0.5,
                "google_review_time": datetime.utcnow(),
                "scraped_at": datetime.utcnow(),
                "extraction_source": review.get("source", "unknown")
            })
        
        return normalized

# =========================================================
# GLOBAL SCRAPER INSTANCE (unchanged)
# =========================================================

_scraper_instance = None

def get_scraper() -> UltimateGoogleScraper:
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = UltimateGoogleScraper()
    return _scraper_instance

# =========================================================
# PUBLIC API (unchanged)
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Main entry point for scraping Google reviews"""
    scraper = get_scraper()
    return await scraper.scrape(place_id)

async def run_scraper(place_id: str) -> List[Dict]:
    """Alias for compatibility"""
    return await scrape_google_reviews(place_id)

# =========================================================
# READY
# =========================================================

print("=" * 80)
print("✅ PRODUCTION SCRAPER V34.0 (PHOENIX) READY")
print(f"   Concurrency: {MAX_CONCURRENT_BROWSERS} (semaphore protected)")
print(f"   Proxy Pool: {len(get_scraper().proxy_pool)} proxies")
print(f"   Adaptive Scroll: dynamic waiting, change detection")
print(f"   Extraction: RPC + DOM + Regex (multi-strategy)")
print(f"   Screenshot on Failure: {ScraperConfig.SCREENSHOT_ON_FAILURE}")
print("=" * 80)
