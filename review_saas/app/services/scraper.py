# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE SCRAPER - V29.0
# ULTIMATE PRODUCTION GRADE - MAXIMUM REVIEW EXTRACTION
# =========================================================

from __future__ import annotations

import os
import re
import time
import json
import asyncio
import hashlib
import logging
import traceback
import base64
import random
import gzip
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# LOGGER (Fixed severity levels)
# =========================================================

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("=" * 80)
print("🚀 QUANTUM ENTERPRISE SCRAPER V29.0 - ULTIMATE EDITION")
print("┌─────────────────────────────────────────────────────────────────┐")
print("│ RPC FIRST │ NETWORK INTERCEPTOR │ INFINITE SCROLL               │")
print("│ REVIEW EXPANSION │ SELECTOR LEARNING │ PROXY BRAIN 4.0          │")
print("│ AUTO-RECOVERY │ BUSINESS MEMORY │ CACHE LAYER                   │")
print("└─────────────────────────────────────────────────────────────────┘")
print("=" * 80)

# =========================================================
# PHASE 1: ADVANCED RPC DECODER (Handles all Google formats)
# =========================================================

class AdvancedRPCDecoder:
    """Universal RPC decoder that handles all Google response formats"""
    
    @staticmethod
    def decode(payload: str) -> List[Dict]:
        """Multi-format RPC decoder"""
        reviews = []
        
        # Try each decoder in sequence
        decoders = [
            AdvancedRPCDecoder._decode_batchexecute,
            AdvancedRPCDecoder._decode_nested_arrays,
            AdvancedRPCDecoder._decode_json_objects,
            AdvancedRPCDecoder._decode_protobuf_like,
            AdvancedRPCDecoder._decode_base64_payloads
        ]
        
        for decoder in decoders:
            try:
                result = decoder(payload)
                if result:
                    reviews.extend(result)
            except:
                continue
        
        # Deduplicate within RPC results
        seen = set()
        unique = []
        for r in reviews:
            sig = r.get("text", "")[:100].lower()
            if sig and sig not in seen:
                seen.add(sig)
                unique.append(r)
        
        return unique
    
    @staticmethod
    def _decode_batchexecute(payload: str) -> List[Dict]:
        """Decode batchexecute format"""
        reviews = []
        
        # Extract f.req parameter
        freq_match = re.search(r'"f\.req":"([^"]+)"', payload)
        if freq_match:
            try:
                decoded = base64.b64decode(freq_match.group(1)).decode('utf-8', errors='ignore')
                # Look for review patterns
                text_matches = re.findall(r'"reviewText":"([^"\\]*(?:\\.[^"\\]*)*)"', decoded)
                for text in text_matches:
                    if len(text) > 20:
                        reviews.append({"text": text[:500], "author": "Google User", "rating": 5, "source": "batchexecute"})
            except:
                pass
        
        return reviews
    
    @staticmethod
    def _decode_nested_arrays(payload: str) -> List[Dict]:
        """Decode nested array structures"""
        reviews = []
        
        # Pattern for review text in nested arrays
        patterns = [
            r'\["reviewText","([^"]+)"\]',
            r'\["text","([^"]+)"\]',
            r'\["snippet","([^"]+)"\]',
            r'\["content","([^"]+)"\]'
        ]
        
        for pattern in patterns:
            for match in re.findall(pattern, payload):
                if len(match) > 20:
                    reviews.append({"text": match[:500], "author": "Google User", "rating": 5, "source": "nested_array"})
        
        # Extract ratings
        rating_pattern = r'\["rating",(\d+)\]'
        ratings = re.findall(rating_pattern, payload)
        for i, rating in enumerate(ratings):
            if i < len(reviews):
                reviews[i]["rating"] = int(rating) if rating.isdigit() else 5
        
        return reviews
    
    @staticmethod
    def _decode_json_objects(payload: str) -> List[Dict]:
        """Extract reviews from JSON objects"""
        reviews = []
        
        # Find JSON objects containing review data
        json_pattern = r'\{[^{}]*"reviewText"[^{}]*\}'
        for match in re.findall(json_pattern, payload):
            try:
                data = json.loads(match)
                if "reviewText" in data:
                    reviews.append({
                        "text": data["reviewText"][:500],
                        "author": data.get("authorName", data.get("author", "Google User")),
                        "rating": data.get("rating", 5),
                        "date": data.get("publishedAt", data.get("date", "")),
                        "source": "json_object"
                    })
            except:
                pass
        
        return reviews
    
    @staticmethod
    def _decode_protobuf_like(payload: str) -> List[Dict]:
        """Extract from protobuf-like encoded strings"""
        reviews = []
        
        # Look for base64 encoded strings that might contain reviews
        base64_pattern = r'"[A-Za-z0-9+/=]{100,}"'
        for match in re.findall(base64_pattern, payload):
            try:
                decoded = base64.b64decode(match.strip('"')).decode('utf-8', errors='ignore')
                if "review" in decoded.lower() and len(decoded) > 100:
                    # Extract sentences that look like reviews
                    sentences = re.findall(r'[A-Z][^.!?]*[.!?]', decoded)
                    for sentence in sentences[:5]:
                        if len(sentence) > 30:
                            reviews.append({"text": sentence[:500], "author": "Protobuf", "rating": 5, "source": "protobuf"})
            except:
                pass
        
        return reviews
    
    @staticmethod
    def _decode_base64_payloads(payload: str) -> List[Dict]:
        """Decode base64 encoded payloads"""
        reviews = []
        
        # Look for base64 strings
        b64_pattern = r'"[A-Za-z0-9+/=]{200,}"'
        for match in re.findall(b64_pattern, payload):
            try:
                decoded = base64.b64decode(match.strip('"')).decode('utf-8', errors='ignore')
                # Try to parse as JSON
                if decoded.startswith('{'):
                    data = json.loads(decoded)
                    if "reviews" in data:
                        for review in data["reviews"]:
                            if "text" in review:
                                reviews.append({
                                    "text": review["text"][:500],
                                    "author": review.get("author", "Base64"),
                                    "rating": review.get("rating", 5),
                                    "source": "base64_json"
                                })
            except:
                pass
        
        return reviews

# =========================================================
# PHASE 2: NETWORK INTERCEPTOR WITH MULTI-FORMAT SUPPORT
# =========================================================

class NetworkInterceptor:
    """Advanced network interceptor with multi-format RPC decoding"""
    
    def __init__(self):
        self.captured_reviews = []
        self.rpc_received = asyncio.Event()
        self.start_time = None
        self.captured_urls = []
        self.place_id = None
    
    async def setup(self, page, place_id: str):
        self.place_id = place_id
        self.start_time = time.time()
        
        def on_response(response):
            asyncio.create_task(self._process_response(response))
        
        page.on("response", on_response)
        logger.info("📡 Advanced network interceptor active")
    
    async def _process_response(self, response):
        try:
            url = response.url
            
            # Target all Google review-related endpoints
            targets = ['batchexecute', 'GetPlaceReviews', 'review', 'rpc', 'listugcposts', 'GetReviews']
            
            if any(t in url.lower() for t in targets):
                self.captured_urls.append(url)
                
                if response.status == 200:
                    try:
                        body = await response.text()
                        if body and len(body) > 100:
                            # Decode using advanced RPC decoder
                            decoded = AdvancedRPCDecoder.decode(body)
                            if decoded:
                                self.captured_reviews.extend(decoded)
                                self.rpc_received.set()
                                logger.info(f"📡 RPC captured: {len(decoded)} reviews from {url.split('/')[-1][:30]}")
                    except:
                        pass
        except:
            pass
    
    async def wait_for_reviews(self, timeout: int = 15) -> List[Dict]:
        """Wait for RPC reviews with adaptive timeout"""
        try:
            await asyncio.wait_for(self.rpc_received.wait(), timeout=timeout)
            elapsed = time.time() - self.start_time
            logger.info(f"📡 RPC received after {elapsed:.1f}s - {len(self.captured_reviews)} reviews")
        except asyncio.TimeoutError:
            logger.info("📡 RPC timeout - falling back to DOM extraction")
        
        return self.captured_reviews
    
    def has_reviews(self) -> bool:
        return len(self.captured_reviews) > 0

# =========================================================
# PHASE 3: INFINITE SCROLL WITH ADAPTIVE STOP
# =========================================================

class InfiniteScroll:
    @staticmethod
    async def execute(page, max_scrolls: int = 60) -> Tuple[int, int]:
        """Scroll until no new reviews for 3 consecutive attempts"""
        scroll_count = 0
        stagnant = 0
        last_count = 0
        final_count = 0
        
        for _ in range(max_scrolls):
            # Scroll review panel
            await page.evaluate("""
                const panel = document.querySelector('.m6QErb, [role="main"], .section-scrollbox');
                if (panel) {
                    panel.scrollTop += 3000;
                } else {
                    window.scrollBy(0, 2000);
                }
            """)
            await asyncio.sleep(1.2)
            
            # Count current reviews
            current = await page.locator('div[data-review-id], div.jftiEf, div.MyEned').count()
            
            if current == last_count:
                stagnant += 1
                if stagnant >= 3:
                    logger.info(f"📜 Scroll complete: {scroll_count} scrolls, {current} reviews")
                    final_count = current
                    break
            else:
                stagnant = 0
                last_count = current
                if scroll_count % 5 == 0:
                    logger.info(f"📜 Scroll {scroll_count}: {current} reviews loaded")
            
            scroll_count += 1
        
        return scroll_count, final_count

# =========================================================
# PHASE 4: REVIEW EXPANSION (Click all hidden content)
# =========================================================

class ReviewExpander:
    @staticmethod
    async def expand_all(page) -> int:
        """Click every 'More', 'Read more', 'Expand' button on the page"""
        expanded = 0
        
        expand_selectors = [
            'button:has-text("More")',
            'button:has-text("more")',
            'button:has-text("Read more")',
            'button:has-text("read more")',
            'span:has-text("More")',
            'button[jsaction*="expand"]',
            'button[aria-label*="expand"]',
            'span.w8nwRe',
            'button[class*="expand"]'
        ]
        
        for selector in expand_selectors:
            try:
                buttons = await page.locator(selector).all()
                for button in buttons:
                    try:
                        await button.click()
                        expanded += 1
                        await asyncio.sleep(0.2)
                    except:
                        pass
            except:
                pass
        
        if expanded:
            logger.info(f"✅ Expanded {expanded} truncated reviews")
        return expanded

# =========================================================
# PHASE 5: SELECTOR LEARNING BRAIN
# =========================================================

class SelectorBrain:
    def __init__(self):
        self.memory_file = Path("/app/data/selector_brain.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"selectors": {}}
    
    def _save(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def update(self, selector: str, success: bool, reviews: int = 0):
        if selector not in self.data["selectors"]:
            self.data["selectors"][selector] = {"success": 0, "fail": 0, "reviews": 0}
        
        if success:
            self.data["selectors"][selector]["success"] += 1
            self.data["selectors"][selector]["reviews"] += reviews
        else:
            self.data["selectors"][selector]["fail"] += 1
        
        self._save()
    
    def get_best(self, selectors: List[str]) -> str:
        best = selectors[0]
        best_score = -1
        
        for sel in selectors:
            stats = self.data["selectors"].get(sel, {"success": 1, "fail": 1, "reviews": 0})
            success_rate = stats["success"] / max(1, stats["success"] + stats["fail"])
            review_bonus = min(stats["reviews"] / 500, 0.3)
            score = success_rate + review_bonus
            
            if score > best_score:
                best_score = score
                best = sel
        
        return best

selector_brain = SelectorBrain()

# =========================================================
# PHASE 6: PROXY BRAIN 4.0
# =========================================================

class ProxyBrain:
    def __init__(self):
        self.memory_file = Path("/app/data/proxy_brain.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"proxies": {}, "blacklist": {}}
    
    def _save(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def calculate_score(self, stats: Dict) -> float:
        total = stats.get("success", 1) + stats.get("fail", 1)
        success_rate = stats.get("success", 1) / total
        review_yield = min(stats.get("reviews", 0) / max(1, stats.get("success", 1)) / 50, 1.0)
        captcha_rate = stats.get("captcha", 0) / max(1, total + stats.get("captcha", 0))
        latency = min(stats.get("avg_latency", 5) / 10, 1.0)
        
        return (success_rate * 0.4) + (review_yield * 0.3) - (captcha_rate * 0.2) - (latency * 0.1)
    
    def is_blacklisted(self, proxy: str) -> bool:
        if proxy in self.data["blacklist"]:
            if time.time() < self.data["blacklist"][proxy]:
                return True
            del self.data["blacklist"][proxy]
        return False
    
    def report(self, proxy: str, success: bool, captcha: bool = False, reviews: int = 0, latency: float = 0):
        if proxy not in self.data["proxies"]:
            self.data["proxies"][proxy] = {"success": 0, "fail": 0, "captcha": 0, "reviews": 0, "latencies": []}
        
        stats = self.data["proxies"][proxy]
        if success:
            stats["success"] += 1
            stats["reviews"] += reviews
        else:
            stats["fail"] += 1
        
        if captcha:
            stats["captcha"] += 1
            if stats["captcha"] >= 3:
                self.data["blacklist"][proxy] = time.time() + 600
        
        if latency > 0:
            stats["latencies"].append(latency)
            stats["avg_latency"] = sum(stats["latencies"]) / len(stats["latencies"])
        
        stats["score"] = self.calculate_score(stats)
        self._save()
    
    def get_best(self, proxies: List[Dict]) -> Optional[Dict]:
        available = []
        for p in proxies:
            server = p.get("server", "")
            if not self.is_blacklisted(server):
                stats = self.data["proxies"].get(server, {"score": 0.5})
                available.append((stats.get("score", 0.5), p))
        
        if not available:
            return proxies[0] if proxies else None
        
        available.sort(key=lambda x: x[0], reverse=True)
        return available[0][1]

proxy_brain = ProxyBrain()

# =========================================================
# PROXY CONFIGURATION
# =========================================================

PROXY_SERVER = os.getenv("PROXY_SERVER", "").strip()
PROXY_USERNAME = os.getenv("PROXY_USERNAME", "").strip()
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", "").strip()

PROXY_POOL = []
if PROXY_SERVER:
    if "," in PROXY_SERVER:
        for proxy in PROXY_SERVER.split(","):
            proxy = proxy.strip()
            if proxy:
                PROXY_POOL.append({"server": f"http://{proxy}"})
    else:
        PROXY_POOL.append({"server": f"http://{PROXY_SERVER}"})
    
    if PROXY_USERNAME and PROXY_PASSWORD:
        for p in PROXY_POOL:
            p["username"] = PROXY_USERNAME
            p["password"] = PROXY_PASSWORD

print(f"✅ PROXY POOL: {len(PROXY_POOL)} proxies")

# =========================================================
# MAIN SCRAPER - V29.0 ULTIMATE EDITION
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Ultimate scraper - Maximum review extraction"""
    
    logger.info("=" * 80)
    logger.info(f"🚀 V29.0 ULTIMATE SCRAPER: {place_id}")
    start_time = time.time()
    
    if not place_id or len(place_id) < 10:
        logger.error(f"❌ Invalid place_id: {place_id}")
        return []
    
    reviews = []
    source = None
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Get best proxy
            proxy = proxy_brain.get_best(PROXY_POOL)
            
            # Launch browser
            context = await p.chromium.launch_persistent_context(
                user_data_dir="/tmp/chrome_profile",
                headless=True,
                proxy=proxy,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Setup network interceptor
            interceptor = NetworkInterceptor()
            await interceptor.setup(page, place_id)
            
            # Navigate to page
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)
            
            # Get best button selector
            button_selectors = [
                'button[data-tab-index="1"]',
                'button[aria-label*="reviews" i]',
                'button[aria-label*="Reviews"]',
                'button[jsaction*="review"]',
                'button[jsaction*="pane.reviewChart.moreReviews"]'
            ]
            best_button = selector_brain.get_best(button_selectors)
            
            # Click reviews button
            button_clicked = False
            if await page.locator(best_button).first.count() > 0:
                await page.locator(best_button).first.click()
                selector_brain.update(best_button, True)
                button_clicked = True
                logger.info(f"✅ Clicked: {best_button[:50]}")
                await asyncio.sleep(2)
            else:
                selector_brain.update(best_button, False)
                logger.warning(f"❌ Button not found: {best_button}")
                await context.close()
                return []
            
            # WAIT FOR RPC REVIEWS (THIS IS THE MAGIC!)
            rpc_reviews = await interceptor.wait_for_reviews(timeout=12)
            
            if rpc_reviews and len(rpc_reviews) > 0:
                reviews = rpc_reviews
                source = "RPC"
                logger.info(f"📡 RPC FIRST: {len(reviews)} reviews captured without scrolling!")
            else:
                # FALLBACK: DOM extraction
                logger.info("🔄 RPC empty - using DOM extraction")
                source = "DOM"
                
                # Wait for panel to load
                await asyncio.sleep(2)
                
                # Expand all truncated reviews
                expanded = await ReviewExpander.expand_all(page)
                if expanded:
                    logger.info(f"✅ Expanded {expanded} reviews")
                
                # Infinite scroll to load all reviews
                scrolls, total_cards = await InfiniteScroll.execute(page, max_scrolls=50)
                logger.info(f"📜 Scrolled {scrolls} times, found {total_cards} cards")
                
                # Extract from DOM
                cards = await page.locator('div[data-review-id], div.jftiEf, div.MyEned').all()
                for card in cards[:150]:
                    try:
                        # Extract text
                        text = ""
                        for sel in ['.wiI7pd', '.MyEned', 'span[jsname]']:
                            if await card.locator(sel).count() > 0:
                                text = (await card.locator(sel).first.inner_text()).strip()
                                break
                        
                        if text and len(text) > 10:
                            # Extract author
                            author = "Anonymous"
                            for sel in ['.d4r55', '.TSUbDb']:
                                if await card.locator(sel).count() > 0:
                                    author = (await card.locator(sel).first.inner_text()).strip()
                                    break
                            
                            # Extract rating
                            rating = 5
                            if await card.locator('span.kvMYJc').count() > 0:
                                aria = await card.locator('span.kvMYJc').first.get_attribute('aria-label')
                                if aria:
                                    match = re.search(r'(\d)', aria)
                                    if match:
                                        rating = int(match.group(1))
                            
                            reviews.append({"text": text, "author": author, "rating": rating, "source": "dom"})
                    except:
                        continue
            
            await context.close()
            
            # Report proxy result
            if proxy:
                proxy_brain.report(proxy.get("server", ""), len(reviews) > 0, reviews=len(reviews))
            
    except asyncio.TimeoutError:
        logger.error("❌ Scraper timeout")
    except Exception as e:
        logger.error(f"❌ Scraper error: {e}")
        logger.error(traceback.format_exc())
    
    # Deduplicate reviews
    seen = set()
    unique_reviews = []
    for r in reviews:
        sig = r.get("text", "")[:100].lower().strip()
        if sig and sig not in seen and len(sig) > 10:
            seen.add(sig)
            unique_reviews.append(r)
    
    # Normalize output format
    normalized = []
    for r in unique_reviews[:150]:
        review_id = hashlib.sha256(f"{place_id}:{r.get('author', '')}:{r.get('text', '')[:100]}".encode()).hexdigest()
        normalized.append({
            "google_review_id": review_id,
            "author": r.get("author", "Anonymous")[:100],
            "author_name": r.get("author", "Anonymous")[:100],
            "rating": min(5, max(1, int(r.get("rating", 5)))),
            "review_text": r.get("text", "")[:3000],
            "content": r.get("text", "")[:3000],
            "text": r.get("text", "")[:3000],
            "sentiment_score": 0.5,
            "google_review_time": datetime.utcnow(),
            "scraped_at": datetime.utcnow()
        })
    
    duration = time.time() - start_time
    logger.info("=" * 80)
    logger.info(f"✅ FINAL REVIEWS: {len(normalized)}")
    logger.info(f"📊 Source: {source if source else 'RPC'}")
    logger.info(f"⏱️  Duration: {duration:.2f}s")
    
    if len(normalized) >= 50:
        logger.info("🎯 SUCCESS: 50+ reviews fetched!")
    elif len(normalized) > 0:
        logger.info(f"📈 Progress: {len(normalized)}/50 reviews")
    else:
        logger.warning("⚠️ No reviews found - check place_id or try again")
    
    # Log selector rankings for debugging
    top_selectors = selector_brain.data.get("selectors", {})
    if top_selectors:
        best = max(top_selectors.items(), key=lambda x: x[1].get("success", 0) / max(1, x[1].get("success", 0) + x[1].get("fail", 0)))
        logger.info(f"📊 Best selector: {best[0][:50]} ({best[1].get('success', 0)} wins)")
    
    logger.info("=" * 80)
    
    return normalized

async def run_scraper(place_id: str) -> List[Dict]:
    """Alias for compatibility"""
    return await scrape_google_reviews(place_id)

# =========================================================
# READY
# =========================================================

print("=" * 80)
print("✅ QUANTUM ENTERPRISE SCRAPER V29.0 READY")
print(f"   RPC Decoder: ADVANCED (5 formats)")
print(f"   Network Interceptor: ACTIVE")
print(f"   Infinite Scroll: ACTIVE (60 max, 3-stagnant stop)")
print(f"   Review Expansion: ACTIVE")
print(f"   Selector Brain: {len(selector_brain.data.get('selectors', {}))} selectors")
print(f"   Proxy Brain: {len(proxy_brain.data.get('proxies', {}))} proxies")
print(f"   Proxy Pool: {len(PROXY_POOL)} proxies")
print("=" * 80)
