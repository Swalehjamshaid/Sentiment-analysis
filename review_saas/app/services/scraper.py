# =========================================================
# FILE: app/services/scraper.py
# QUANTUM ENTERPRISE SCRAPER - V30.0
# PRODUCTION GRADE - ENHANCED RELIABILITY
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
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# CONSTANTS SECTION - EASY TUNING
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
    SCROLL_DELAY = 1.2
    
    # Timeouts
    RPC_TIMEOUT = 12
    PAGE_LOAD_TIMEOUT = 60000
    NAVIGATION_TIMEOUT = 60000
    BROWSER_LAUNCH_TIMEOUT = 30000
    
    # Selector Brain
    SELECTOR_SAVE_INTERVAL = 50
    SELECTOR_EXPIRY_DAYS = 90
    
    # Proxy Brain
    PROXY_COOLDOWN_BASE = 600  # 10 minutes
    PROXY_COOLDOWN_MAX = 3600  # 60 minutes
    PROXY_RECENT_WEIGHT = 0.7  # 70% weight on recent performance
    
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
print("🚀 QUANTUM ENTERPRISE SCRAPER V30.0 - PRODUCTION GRADE")
print("┌─────────────────────────────────────────────────────────────────┐")
print("│ ENHANCED RPC DECODER │ SMART NETWORK INTERCEPTOR                │")
print("│ ADAPTIVE SCROLLING │ VALIDATION LAYER │ CONFIDENCE SCORING      │")
print("│ HEALTH CHECKS │ METRICS COLLECTION │ AUTO-RECOVERY              │")
print("└─────────────────────────────────────────────────────────────────┘")
print("=" * 80)

# =========================================================
# PHASE 1: ENHANCED RPC DECODER WITH VALIDATION
# =========================================================

class ReviewValidator:
    """Structured review validation with spam detection"""
    
    SPAM_PATTERNS = [
        r'click.*link',
        r'visit.*website',
        r'www\..*\.com',
        r'http://',
        r'https://',
        r'check.*bio',
        r'follow.*instagram',
        r'subscribe.*channel'
    ]
    
    @classmethod
    def is_valid(cls, review: Dict) -> Tuple[bool, Optional[str]]:
        """Validate review quality and return (is_valid, reason)"""
        
        text = review.get("text", "").strip()
        author = review.get("author", "").strip()
        
        # Check minimum length
        if len(text) < ScraperConfig.MIN_REVIEW_LENGTH:
            return False, f"Too short ({len(text)} chars)"
        
        # Check maximum length
        if len(text) > ScraperConfig.MAX_REVIEW_LENGTH:
            return False, f"Too long ({len(text)} chars)"
        
        # Check if rating exists
        rating = review.get("rating")
        if rating is None:
            return False, "Missing rating"
        
        try:
            rating_int = int(rating)
            if rating_int < 1 or rating_int > 5:
                return False, f"Invalid rating: {rating_int}"
        except:
            return False, f"Non-numeric rating: {rating}"
        
        # Check spam patterns
        text_lower = text.lower()
        for pattern in cls.SPAM_PATTERNS:
            if re.search(pattern, text_lower):
                return False, f"Spam pattern detected: {pattern}"
        
        # Check for gibberish (excessive repeated characters)
        if re.search(r'(.)\1{10,}', text):
            return False, "Gibberish detected (repeated chars)"
        
        # Valid review
        return True, None

class AdvancedRPCDecoder:
    """Universal RPC decoder with confidence scoring and validation"""
    
    @staticmethod
    def decode(payload: str, max_results: int = 150) -> List[Dict]:
        """Multi-format RPC decoder with early termination"""
        reviews = []
        confidence_scores = []
        
        # Decoders with their confidence thresholds
        decoders = [
            ("batchexecute", AdvancedRPCDecoder._decode_batchexecute, 30),
            ("nested_arrays", AdvancedRPCDecoder._decode_nested_arrays, 20),
            ("json_objects", AdvancedRPCDecoder._decode_json_objects, 15),
            ("protobuf", AdvancedRPCDecoder._decode_protobuf_like, 10),
            ("base64", AdvancedRPCDecoder._decode_base64_payloads, 5)
        ]
        
        for decoder_name, decoder_func, confidence_threshold in decoders:
            try:
                result = decoder_func(payload)
                if result:
                    # Validate each review
                    valid_results = []
                    for r in result:
                        is_valid, reason = ReviewValidator.is_valid(r)
                        if is_valid:
                            valid_results.append(r)
                        else:
                            logger.debug(f"Invalid review in {decoder_name}: {reason}")
                    
                    if valid_results:
                        reviews.extend(valid_results)
                        confidence_scores.extend([confidence_threshold] * len(valid_results))
                        
                        # Early termination if we have high-confidence results
                        if len(valid_results) >= confidence_threshold:
                            logger.info(f"✅ {decoder_name} gave {len(valid_results)} valid reviews - stopping")
                            break
            except Exception as e:
                logger.debug(f"Decoder {decoder_name} failed: {e}")
                continue
        
        # Deduplicate within RPC results with text normalization
        seen = set()
        unique = []
        for r, conf in zip(reviews, confidence_scores):
            normalized_text = AdvancedRPCDecoder._normalize_text(r.get("text", ""))
            sig = hashlib.md5(normalized_text.encode()).hexdigest()
            if sig not in seen:
                seen.add(sig)
                r["decoder_confidence"] = conf
                unique.append(r)
        
        return unique[:max_results]
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for better deduplication"""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation variations
        text = re.sub(r'[.!?]+$', '', text)
        return text.strip()
    
    @staticmethod
    def _decode_batchexecute(payload: str) -> List[Dict]:
        """Decode batchexecute format with error handling"""
        reviews = []
        
        try:
            # Extract f.req parameter
            freq_match = re.search(r'"f\.req":"([^"]+)"', payload)
            if freq_match:
                try:
                    decoded = base64.b64decode(freq_match.group(1)).decode('utf-8', errors='ignore')
                    # Look for review patterns
                    text_matches = re.findall(r'"reviewText":"([^"\\]*(?:\\.[^"\\]*)*)"', decoded)
                    rating_matches = re.findall(r'"rating":(\d+)', decoded)
                    
                    for i, text in enumerate(text_matches):
                        if len(text) >= ScraperConfig.MIN_REVIEW_LENGTH:
                            review = {
                                "text": text[:ScraperConfig.MAX_REVIEW_LENGTH],
                                "author": "Google User",
                                "rating": int(rating_matches[i]) if i < len(rating_matches) else 5,
                                "source": "batchexecute",
                                "extraction_method": "rpc"
                            }
                            reviews.append(review)
                except Exception as e:
                    logger.debug(f"Batchexecute base64 decode failed: {e}")
        except Exception as e:
            logger.debug(f"Batchexecute decoder error: {e}")
        
        return reviews
    
    @staticmethod
    def _decode_nested_arrays(payload: str) -> List[Dict]:
        """Decode nested array structures with validation"""
        reviews = []
        
        try:
            # Pattern for review text in nested arrays
            patterns = [
                r'\["reviewText","([^"]+)"\]',
                r'\["text","([^"]+)"\]',
                r'\["snippet","([^"]+)"\]',
                r'\["content","([^"]+)"\]'
            ]
            
            for pattern in patterns:
                for match in re.findall(pattern, payload):
                    if len(match) >= ScraperConfig.MIN_REVIEW_LENGTH:
                        reviews.append({
                            "text": match[:ScraperConfig.MAX_REVIEW_LENGTH],
                            "author": "Google User",
                            "rating": 5,
                            "source": "nested_array",
                            "extraction_method": "rpc"
                        })
            
            # Extract ratings
            rating_pattern = r'\["rating",(\d+)\]'
            ratings = re.findall(rating_pattern, payload)
            for i, rating in enumerate(ratings):
                if i < len(reviews) and rating.isdigit():
                    reviews[i]["rating"] = int(rating)
        except Exception as e:
            logger.debug(f"Nested array decoder error: {e}")
        
        return reviews
    
    @staticmethod
    def _decode_json_objects(payload: str) -> List[Dict]:
        """Extract reviews from JSON objects with proper parsing"""
        reviews = []
        
        try:
            # Find JSON objects containing review data
            json_pattern = r'\{[^{}]*"reviewText"[^{}]*\}'
            for match in re.findall(json_pattern, payload):
                try:
                    # Clean up the JSON string
                    clean_match = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', match)
                    data = json.loads(clean_match)
                    
                    if "reviewText" in data:
                        review = {
                            "text": data["reviewText"][:ScraperConfig.MAX_REVIEW_LENGTH],
                            "author": data.get("authorName", data.get("author", "Google User")),
                            "rating": data.get("rating", 5),
                            "date": data.get("publishedAt", data.get("date", "")),
                            "source": "json_object",
                            "extraction_method": "rpc"
                        }
                        
                        # Extract additional metadata if available
                        if "reviewImageUrls" in data:
                            review["image_urls"] = data["reviewImageUrls"]
                        if "responseFromOwner" in data:
                            review["owner_response"] = data["responseFromOwner"]
                        if "helpfulVotes" in data:
                            review["helpful_votes"] = data["helpfulVotes"]
                        
                        reviews.append(review)
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON parsing failed: {e}")
                except Exception as e:
                    logger.debug(f"JSON object processing error: {e}")
        except Exception as e:
            logger.debug(f"JSON decoder error: {e}")
        
        return reviews
    
    @staticmethod
    def _decode_protobuf_like(payload: str) -> List[Dict]:
        """Extract from protobuf-like encoded strings with validation"""
        reviews = []
        
        try:
            # Look for base64 encoded strings that might contain reviews
            base64_pattern = r'"[A-Za-z0-9+/=]{100,}"'
            for match in re.findall(base64_pattern, payload):
                b64_string = match.strip('"')
                
                # Validate base64 before decoding
                if len(b64_string) % 4 == 0 and re.match(r'^[A-Za-z0-9+/=]+$', b64_string):
                    try:
                        decoded = base64.b64decode(b64_string, validate=True).decode('utf-8', errors='ignore')
                        if "review" in decoded.lower() and len(decoded) > 100:
                            # Extract sentences that look like reviews
                            sentences = re.findall(r'[A-Z][^.!?]*[.!?]', decoded)
                            for sentence in sentences[:5]:
                                if len(sentence) >= ScraperConfig.MIN_REVIEW_LENGTH:
                                    reviews.append({
                                        "text": sentence[:ScraperConfig.MAX_REVIEW_LENGTH],
                                        "author": "Protobuf User",
                                        "rating": 5,
                                        "source": "protobuf",
                                        "extraction_method": "rpc"
                                    })
                    except (base64.binascii.Error, UnicodeDecodeError) as e:
                        logger.debug(f"Base64 validation failed: {e}")
        except Exception as e:
            logger.debug(f"Protobuf decoder error: {e}")
        
        return reviews
    
    @staticmethod
    def _decode_base64_payloads(payload: str) -> List[Dict]:
        """Decode base64 encoded payloads with validation"""
        reviews = []
        
        try:
            # Look for base64 strings with proper validation
            b64_pattern = r'"[A-Za-z0-9+/=]{200,}"'
            for match in re.findall(b64_pattern, payload):
                b64_string = match.strip('"')
                
                # Validate base64 format
                if len(b64_string) % 4 == 0 and re.match(r'^[A-Za-z0-9+/=]+$', b64_string):
                    try:
                        decoded = base64.b64decode(b64_string, validate=True).decode('utf-8', errors='ignore')
                        
                        # Try to parse as JSON
                        if decoded.startswith('{'):
                            data = json.loads(decoded)
                            if "reviews" in data:
                                for review in data["reviews"]:
                                    if "text" in review and len(review["text"]) >= ScraperConfig.MIN_REVIEW_LENGTH:
                                        reviews.append({
                                            "text": review["text"][:ScraperConfig.MAX_REVIEW_LENGTH],
                                            "author": review.get("author", "Base64 User"),
                                            "rating": review.get("rating", 5),
                                            "source": "base64_json",
                                            "extraction_method": "rpc"
                                        })
                    except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.debug(f"Base64 payload validation failed: {e}")
        except Exception as e:
            logger.debug(f"Base64 decoder error: {e}")
        
        return reviews

# =========================================================
# PHASE 2: ENHANCED NETWORK INTERCEPTOR
# =========================================================

class NetworkInterceptor:
    """Advanced network interceptor with memory limits and metrics"""
    
    def __init__(self):
        self.captured_reviews = deque(maxlen=1000)  # Limit memory usage
        self.captured_urls: Set[str] = set()  # Prevent duplicates
        self.rpc_received = asyncio.Event()
        self.start_time = None
        self.place_id = None
        self.response_metrics: List[Dict] = []
    
    async def setup(self, page, place_id: str):
        self.place_id = place_id
        self.start_time = time.time()
        
        def on_response(response):
            asyncio.create_task(self._process_response(response))
        
        page.on("response", on_response)
        logger.info("📡 Enhanced network interceptor active")
    
    async def _process_response(self, response):
        try:
            url = response.url
            
            # Target all Google review-related endpoints
            targets = ['batchexecute', 'GetPlaceReviews', 'review', 'rpc', 'listugcposts', 'GetReviews']
            
            if any(t in url.lower() for t in targets):
                self.captured_urls.add(url)
                
                if response.status == 200:
                    try:
                        body = await response.text()
                        body_size = len(body)
                        
                        if body and body_size > 100:
                            # Store metrics
                            self.response_metrics.append({
                                "endpoint": url.split('/')[-1][:50],
                                "status": response.status,
                                "size_mb": body_size / (1024 * 1024),
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            
                            # Decode using enhanced RPC decoder
                            decoded = AdvancedRPCDecoder.decode(body)
                            if decoded:
                                self.captured_reviews.extend(decoded)
                                self.rpc_received.set()
                                logger.info(f"📡 RPC captured: {len(decoded)} reviews from {url.split('/')[-1][:30]}")
                    except Exception as e:
                        logger.debug(f"Response processing failed: {e}")
        except Exception as e:
            logger.debug(f"Response handler error: {e}")
    
    async def wait_for_reviews(self, timeout: int = None) -> List[Dict]:
        """Wait for RPC reviews with adaptive timeout"""
        timeout = timeout or ScraperConfig.RPC_TIMEOUT
        
        try:
            await asyncio.wait_for(self.rpc_received.wait(), timeout=timeout)
            elapsed = time.time() - self.start_time
            logger.info(f"📡 RPC received after {elapsed:.1f}s - {len(self.captured_reviews)} reviews")
        except asyncio.TimeoutError:
            logger.info("📡 RPC timeout - falling back to DOM extraction")
        
        return list(self.captured_reviews)
    
    def has_reviews(self) -> bool:
        return len(self.captured_reviews) > 0
    
    def get_metrics(self) -> Dict:
        """Return interceptor performance metrics"""
        return {
            "total_reviews": len(self.captured_reviews),
            "unique_urls": len(self.captured_urls),
            "response_metrics": self.response_metrics[-10:],  # Last 10 responses
            "rpc_received": self.rpc_received.is_set()
        }

# =========================================================
# PHASE 3: ADAPTIVE INFINITE SCROLL
# =========================================================

class InfiniteScroll:
    @staticmethod
    async def execute(page, max_scrolls: int = None) -> Tuple[int, int, List[str]]:
        """Scroll with adaptive distance and last review detection"""
        max_scrolls = max_scrolls or ScraperConfig.MAX_SCROLLS
        scroll_count = 0
        stagnant = 0
        last_count = 0
        final_count = 0
        last_review_ids = []
        scroll_distances = [
            ScraperConfig.SCROLL_DISTANCE_START,
            ScraperConfig.SCROLL_DISTANCE_START + 500,
            ScraperConfig.SCROLL_DISTANCE_MAX
        ]
        
        for scroll_iter in range(max_scrolls):
            # Adaptive scroll distance based on content growth
            scroll_distance = scroll_distances[min(scroll_iter // 10, len(scroll_distances) - 1)]
            
            # Scroll with adaptive distance
            await page.evaluate(f"""
                const panel = document.querySelector('.m6QErb, [role="main"], .section-scrollbox');
                if (panel) {{
                    panel.scrollTop += {scroll_distance};
                }} else {{
                    window.scrollBy(0, {scroll_distance});
                }}
            """)
            await asyncio.sleep(ScraperConfig.SCROLL_DELAY)
            
            # Get current review IDs for better stagnation detection
            current_review_ids = await page.locator('div[data-review-id]').all()
            current_ids = []
            for rid in current_review_ids[:10]:  # Check first 10 IDs
                try:
                    review_id = await rid.get_attribute('data-review-id')
                    if review_id:
                        current_ids.append(review_id)
                except:
                    pass
            
            # Check if we've seen new reviews
            new_reviews_detected = len(set(current_ids) - set(last_review_ids)) > 0
            
            if not new_reviews_detected and len(current_ids) > 0:
                stagnant += 1
                if stagnant >= ScraperConfig.SCROLL_STAGNANT_LIMIT:
                    logger.info(f"📜 Scroll complete: {scroll_count} scrolls, {len(current_ids)} reviews")
                    final_count = len(current_ids)
                    break
            else:
                stagnant = 0
                last_review_ids = current_ids
                if scroll_count % 5 == 0:
                    logger.info(f"📜 Scroll {scroll_count}: {len(current_ids)} reviews loaded")
            
            scroll_count += 1
        
        return scroll_count, final_count, last_review_ids

# =========================================================
# PHASE 4: ENHANCED REVIEW EXPANSION WITH METADATA
# =========================================================

class ReviewExpander:
    @staticmethod
    async def expand_all(page) -> Tuple[int, List[Dict]]:
        """Click all expand buttons and capture metadata"""
        expanded = 0
        metadata = []
        
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
                        # Capture button state before click
                        button_text = await button.text_content()
                        await button.click()
                        expanded += 1
                        metadata.append({
                            "selector": selector,
                            "text": button_text[:50] if button_text else "",
                            "expanded_at": datetime.utcnow().isoformat()
                        })
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.debug(f"Button click failed: {e}")
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
        
        if expanded:
            logger.info(f"✅ Expanded {expanded} truncated reviews")
        return expanded, metadata

# =========================================================
# PHASE 5: ENHANCED SELECTOR BRAIN WITH EXPIRY
# =========================================================

class SelectorBrain:
    def __init__(self):
        self.memory_file = Path("/app/data/selector_brain.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
        self.update_counter = 0
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load selector brain: {e}")
        return {"selectors": {}, "version": "2.0"}
    
    def _save(self):
        """Save with batching to reduce disk writes"""
        self.update_counter += 1
        if self.update_counter >= ScraperConfig.SELECTOR_SAVE_INTERVAL:
            try:
                with open(self.memory_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
                self.update_counter = 0
            except Exception as e:
                logger.warning(f"Failed to save selector brain: {e}")
    
    def update(self, selector: str, success: bool, reviews: int = 0):
        if selector not in self.data["selectors"]:
            self.data["selectors"][selector] = {
                "success": 0,
                "fail": 0,
                "reviews": 0,
                "last_success": None,
                "last_fail": None,
                "created_at": datetime.utcnow().isoformat()
            }
        
        stats = self.data["selectors"][selector]
        now = datetime.utcnow().isoformat()
        
        if success:
            stats["success"] += 1
            stats["reviews"] += reviews
            stats["last_success"] = now
        else:
            stats["fail"] += 1
            stats["last_fail"] = now
        
        self._save()
    
    def _is_expired(self, selector_data: Dict) -> bool:
        """Check if selector is older than expiry days"""
        created_at = selector_data.get("created_at")
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at)
                age_days = (datetime.utcnow() - created_date).days
                return age_days > ScraperConfig.SELECTOR_EXPIRY_DAYS
            except:
                pass
        return False
    
    def get_best(self, selectors: List[str]) -> str:
        best = selectors[0]
        best_score = -1
        
        for sel in selectors:
            stats = self.data["selectors"].get(sel, {"success": 1, "fail": 1, "reviews": 0})
            
            # Skip expired selectors
            if self._is_expired(stats):
                continue
            
            success_rate = stats["success"] / max(1, stats["success"] + stats["fail"])
            review_bonus = min(stats["reviews"] / 500, 0.3)
            
            # Recency bonus for recent successes
            recency_bonus = 0
            if stats.get("last_success"):
                try:
                    last_success = datetime.fromisoformat(stats["last_success"])
                    days_since = (datetime.utcnow() - last_success).days
                    recency_bonus = max(0, 0.2 - (days_since * 0.01))
                except:
                    pass
            
            score = success_rate + review_bonus + recency_bonus
            
            if score > best_score:
                best_score = score
                best = sel
        
        return best

selector_brain = SelectorBrain()

# =========================================================
# PHASE 6: ENHANCED PROXY BRAIN WITH COOLDOWN
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
            except Exception as e:
                logger.warning(f"Failed to load proxy brain: {e}")
        return {"proxies": {}, "blacklist": {}, "version": "3.0"}
    
    def _save(self):
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save proxy brain: {e}")
    
    def _calculate_cooldown(self, captcha_count: int) -> int:
        """Calculate cooldown duration based on captcha frequency"""
        cooldown = ScraperConfig.PROXY_COOLDOWN_BASE * (2 ** (captcha_count - 1))
        return min(cooldown, ScraperConfig.PROXY_COOLDOWN_MAX)
    
    def calculate_score(self, stats: Dict) -> float:
        """Calculate proxy score with recency weighting"""
        # Calculate recent performance (last 10 attempts)
        recent_attempts = stats.get("recent_attempts", [])[-10:]
        recent_success = sum(1 for a in recent_attempts if a["success"])
        recent_total = len(recent_attempts) or 1
        recent_rate = recent_success / recent_total
        
        # Overall performance
        total = stats.get("success", 1) + stats.get("fail", 1)
        overall_rate = stats.get("success", 1) / total
        
        # Weighted score (70% recent, 30% overall)
        success_rate = (recent_rate * ScraperConfig.PROXY_RECENT_WEIGHT) + \
                      (overall_rate * (1 - ScraperConfig.PROXY_RECENT_WEIGHT))
        
        review_yield = min(stats.get("reviews", 0) / max(1, stats.get("success", 1)) / 50, 1.0)
        captcha_rate = stats.get("captcha", 0) / max(1, total + stats.get("captcha", 0))
        latency = min(stats.get("avg_latency", 5) / 10, 1.0)
        
        return (success_rate * 0.4) + (review_yield * 0.3) - (captcha_rate * 0.2) - (latency * 0.1)
    
    def is_blacklisted(self, proxy: str) -> Tuple[bool, int]:
        """Check if proxy is blacklisted and return cooldown remaining"""
        if proxy in self.data["blacklist"]:
            cooldown_until = self.data["blacklist"][proxy]
            if time.time() < cooldown_until:
                remaining = int(cooldown_until - time.time())
                return True, remaining
            del self.data["blacklist"][proxy]
        return False, 0
    
    def report(self, proxy: str, success: bool, captcha: bool = False, reviews: int = 0, latency: float = 0):
        if proxy not in self.data["proxies"]:
            self.data["proxies"][proxy] = {
                "success": 0,
                "fail": 0,
                "captcha": 0,
                "reviews": 0,
                "latencies": [],
                "recent_attempts": []
            }
        
        stats = self.data["proxies"][proxy]
        
        # Record attempt
        attempt = {
            "success": success,
            "timestamp": time.time(),
            "reviews": reviews,
            "latency": latency
        }
        stats["recent_attempts"].append(attempt)
        
        # Keep only last 50 attempts
        if len(stats["recent_attempts"]) > 50:
            stats["recent_attempts"] = stats["recent_attempts"][-50:]
        
        # Update stats
        if success:
            stats["success"] += 1
            stats["reviews"] += reviews
        else:
            stats["fail"] += 1
        
        if captcha:
            stats["captcha"] += 1
            cooldown = self._calculate_cooldown(stats["captcha"])
            self.data["blacklist"][proxy] = time.time() + cooldown
            logger.warning(f"Proxy {proxy} blacklisted for {cooldown // 60} minutes")
        
        if latency > 0:
            stats["latencies"].append(latency)
            stats["avg_latency"] = sum(stats["latencies"]) / len(stats["latencies"])
        
        # Update per-country tracking if country available
        if "country" in stats:
            stats["country_performance"] = stats.get("country_performance", {})
            country = stats["country"]
            if country not in stats["country_performance"]:
                stats["country_performance"][country] = {"success": 0, "fail": 0}
            
            if success:
                stats["country_performance"][country]["success"] += 1
            else:
                stats["country_performance"][country]["fail"] += 1
        
        stats["score"] = self.calculate_score(stats)
        self._save()
    
    def get_best(self, proxies: List[Dict], country: str = None) -> Optional[Dict]:
        """Get best proxy, optionally filtered by country"""
        available = []
        for p in proxies:
            server = p.get("server", "")
            is_blacklisted, cooldown = self.is_blacklisted(server)
            
            if not is_blacklisted:
                stats = self.data["proxies"].get(server, {"score": 0.5})
                
                # Filter by country if specified
                if country and "country_performance" in stats:
                    country_stats = stats["country_performance"].get(country, {"success": 1, "fail": 1})
                    country_rate = country_stats["success"] / max(1, country_stats["success"] + country_stats["fail"])
                    score = stats.get("score", 0.5) * country_rate
                else:
                    score = stats.get("score", 0.5)
                
                available.append((score, p))
        
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
# PHASE 7: METRICS COLLECTOR
# =========================================================

class MetricsCollector:
    """Collect and store scraper performance metrics"""
    
    def __init__(self):
        self.metrics = {
            "scrapes": [],
            "last_scrape": None
        }
        self.load()
    
    def load(self):
        """Load metrics from file"""
        if ScraperConfig.METRICS_FILE.exists():
            try:
                with open(ScraperConfig.METRICS_FILE, 'r') as f:
                    self.metrics = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")
    
    def save(self):
        """Save metrics to file"""
        try:
            ScraperConfig.METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ScraperConfig.METRICS_FILE, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def record(self, place_id: str, metrics: Dict):
        """Record a scrape attempt"""
        record = {
            "place_id": place_id,
            "timestamp": datetime.utcnow().isoformat(),
            **metrics
        }
        
        self.metrics["scrapes"].append(record)
        self.metrics["last_scrape"] = record
        
        # Keep only last 1000 records
        if len(self.metrics["scrapes"]) > 1000:
            self.metrics["scrapes"] = self.metrics["scrapes"][-1000:]
        
        self.save()
    
    def get_stats(self) -> Dict:
        """Get aggregate statistics"""
        if not self.metrics["scrapes"]:
            return {}
        
        recent = self.metrics["scrapes"][-100:]
        
        return {
            "total_scrapes": len(self.metrics["scrapes"]),
            "recent_scrapes": len(recent),
            "avg_reviews": sum(r.get("reviews_found", 0) for r in recent) / max(1, len(recent)),
            "success_rate": sum(1 for r in recent if r.get("reviews_found", 0) > 0) / max(1, len(recent)),
            "avg_duration": sum(r.get("duration", 0) for r in recent) / max(1, len(recent)),
            "rpc_success_rate": sum(1 for r in recent if r.get("source") == "RPC") / max(1, len(recent))
        }

metrics_collector = MetricsCollector()

# =========================================================
# MAIN SCRAPER - V30.0 ENHANCED EDITION
# =========================================================

async def scrape_google_reviews(place_id: str) -> List[Dict]:
    """Enhanced scraper with reliability improvements"""
    
    logger.info("=" * 80)
    logger.info(f"🚀 V30.0 ENHANCED SCRAPER: {place_id}")
    start_time = time.time()
    
    if not place_id or len(place_id) < 10:
        logger.error(f"❌ Invalid place_id: {place_id}")
        return []
    
    reviews = []
    source = None
    context = None
    extraction_metadata = {
        "rpc_reviews": 0,
        "dom_reviews": 0,
        "scrolls": 0,
        "expansions": 0,
        "decoders_used": []
    }
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Get best proxy (with country detection)
            proxy = proxy_brain.get_best(PROXY_POOL)
            
            # Launch browser with timeout
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir="/tmp/chrome_profile",
                    headless=True,
                    proxy=proxy,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    timeout=ScraperConfig.BROWSER_LAUNCH_TIMEOUT
                )
            except Exception as e:
                logger.error(f"Browser launch failed: {e}")
                return []
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Health check - verify browser works
            try:
                await page.goto(ScraperConfig.HEALTH_CHECK_URL, 
                              wait_until="domcontentloaded", 
                              timeout=ScraperConfig.NAVIGATION_TIMEOUT)
                logger.info("✅ Browser health check passed")
            except Exception as e:
                logger.error(f"Browser health check failed: {e}")
                await context.close()
                return []
            
            # Setup network interceptor
            interceptor = NetworkInterceptor()
            await interceptor.setup(page, place_id)
            
            # Navigate to page
            url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            try:
                await page.goto(url, wait_until="networkidle", timeout=ScraperConfig.NAVIGATION_TIMEOUT)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                await context.close()
                return []
            
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
            try:
                if await page.locator(best_button).first.count() > 0:
                    await page.locator(best_button).first.click()
                    selector_brain.update(best_button, True)
                    button_clicked = True
                    logger.info(f"✅ Clicked: {best_button[:50]}")
                    await asyncio.sleep(2)
                else:
                    selector_brain.update(best_button, False)
                    logger.warning(f"❌ Button not found: {best_button}")
            except Exception as e:
                logger.error(f"Button click failed: {e}")
            
            if not button_clicked:
                await context.close()
                return []
            
            # WAIT FOR RPC REVIEWS
            rpc_reviews = await interceptor.wait_for_reviews(timeout=ScraperConfig.RPC_TIMEOUT)
            
            if rpc_reviews and len(rpc_reviews) > 0:
                reviews = rpc_reviews
                source = "RPC"
                extraction_metadata["rpc_reviews"] = len(reviews)
                extraction_metadata["decoders_used"] = list(set(r.get("decoder_confidence", 0) for r in reviews))
                logger.info(f"📡 RPC FIRST: {len(reviews)} reviews captured without scrolling!")
            else:
                # FALLBACK: DOM extraction
                logger.info("🔄 RPC empty - using DOM extraction")
                source = "DOM"
                
                # Wait for panel to load
                await asyncio.sleep(2)
                
                # Expand all truncated reviews
                expanded, expand_metadata = await ReviewExpander.expand_all(page)
                extraction_metadata["expansions"] = expanded
                if expanded:
                    logger.info(f"✅ Expanded {expanded} reviews")
                
                # Infinite scroll to load all reviews
                scrolls, total_cards, review_ids = await InfiniteScroll.execute(page, max_scrolls=ScraperConfig.MAX_SCROLLS)
                extraction_metadata["scrolls"] = scrolls
                logger.info(f"📜 Scrolled {scrolls} times, found {total_cards} cards")
                
                # Extract from DOM with metadata
                cards = await page.locator('div[data-review-id], div.jftiEf, div.MyEned').all()
                for card in cards[:ScraperConfig.MAX_REVIEWS]:
                    try:
                        review_data = {}
                        
                        # Extract text
                        for sel in ['.wiI7pd', '.MyEned', 'span[jsname]']:
                            if await card.locator(sel).count() > 0:
                                review_data["text"] = (await card.locator(sel).first.inner_text()).strip()
                                break
                        
                        if review_data.get("text") and len(review_data["text"]) >= ScraperConfig.MIN_REVIEW_LENGTH:
                            # Extract author
                            for sel in ['.d4r55', '.TSUbDb']:
                                if await card.locator(sel).count() > 0:
                                    review_data["author"] = (await card.locator(sel).first.inner_text()).strip()
                                    break
                            else:
                                review_data["author"] = "Anonymous"
                            
                            # Extract rating
                            review_data["rating"] = 5
                            if await card.locator('span.kvMYJc').count() > 0:
                                aria = await card.locator('span.kvMYJc').first.get_attribute('aria-label')
                                if aria:
                                    match = re.search(r'(\d)', aria)
                                    if match:
                                        review_data["rating"] = int(match.group(1))
                            
                            # Extract date if available
                            for sel in ['.rsqaWe', '.dehysf']:
                                if await card.locator(sel).count() > 0:
                                    review_data["date"] = (await card.locator(sel).first.inner_text()).strip()
                                    break
                            
                            # Extract helpful votes if available
                            if await card.locator('button[aria-label*="helpful"]').count() > 0:
                                helpful_text = await card.locator('button[aria-label*="helpful"]').first.get_attribute('aria-label')
                                if helpful_text:
                                    vote_match = re.search(r'(\d+)', helpful_text)
                                    if vote_match:
                                        review_data["helpful_votes"] = int(vote_match.group(1))
                            
                            review_data["source"] = "dom"
                            review_data["extraction_method"] = "dom"
                            reviews.append(review_data)
                    except Exception as e:
                        logger.debug(f"DOM extraction failed: {e}")
                        continue
                
                extraction_metadata["dom_reviews"] = len(reviews)
            
            # Capture interceptor metrics
            extraction_metadata["network_metrics"] = interceptor.get_metrics()
            
    except asyncio.TimeoutError:
        logger.error("❌ Scraper timeout")
        if ScraperConfig.SCREENSHOT_ON_ERROR and context:
            try:
                page = context.pages[0] if context.pages else None
                if page:
                    ScraperConfig.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                    screenshot_path = ScraperConfig.SCREENSHOT_DIR / f"error_{place_id}_{int(time.time())}.png"
                    await page.screenshot(path=str(screenshot_path))
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
            except:
                pass
    except Exception as e:
        logger.error(f"❌ Scraper error: {e}")
        logger.error(traceback.format_exc())
        if ScraperConfig.SCREENSHOT_ON_ERROR and context:
            try:
                page = context.pages[0] if context.pages else None
                if page:
                    ScraperConfig.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                    screenshot_path = ScraperConfig.SCREENSHOT_DIR / f"error_{place_id}_{int(time.time())}.png"
                    await page.screenshot(path=str(screenshot_path))
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
            except:
                pass
    finally:
        # ALWAYS close browser in finally block
        if context:
            await context.close()
        
        # Report proxy result
        if proxy:
            proxy_brain.report(proxy.get("server", ""), len(reviews) > 0, reviews=len(reviews))
    
    # Enhanced deduplication with normalization
    seen = set()
    unique_reviews = []
    for r in reviews:
        # Normalize text for better deduplication
        normalized_text = AdvancedRPCDecoder._normalize_text(r.get("text", ""))
        # Create signature using author, rating, and text
        signature = hashlib.md5(
            f"{r.get('author', '')}:{r.get('rating', 0)}:{normalized_text[:ScraperConfig.DEDUP_CHAR_LIMIT]}".encode()
        ).hexdigest()
        
        if signature not in seen and len(normalized_text) >= ScraperConfig.MIN_REVIEW_LENGTH:
            seen.add(signature)
            unique_reviews.append(r)
    
    # Normalize output format with confidence scores
    normalized = []
    for r in unique_reviews[:ScraperConfig.MAX_REVIEWS]:
        # Validate again before output
        is_valid, reason = ReviewValidator.is_valid(r)
        if not is_valid:
            logger.debug(f"Skipping invalid review: {reason}")
            continue
        
        review_id = hashlib.sha256(f"{place_id}:{r.get('author', '')}:{r.get('text', '')[:100]}".encode()).hexdigest()
        
        # Parse date if available
        review_date = datetime.utcnow()
        date_str = r.get("date", "")
        if date_str:
            # Simple date parsing - can be enhanced
            if "day" in date_str or "days" in date_str:
                days = int(re.search(r'(\d+)', date_str).group(1)) if re.search(r'(\d+)', date_str) else 0
                from datetime import timedelta
                review_date = datetime.utcnow() - timedelta(days=days)
        
        normalized_review = {
            "google_review_id": review_id,
            "author": r.get("author", "Anonymous")[:100],
            "author_name": r.get("author", "Anonymous")[:100],
            "rating": min(5, max(1, int(r.get("rating", 5)))),
            "review_text": r.get("text", "")[:ScraperConfig.MAX_REVIEW_LENGTH],
            "content": r.get("text", "")[:ScraperConfig.MAX_REVIEW_LENGTH],
            "text": r.get("text", "")[:ScraperConfig.MAX_REVIEW_LENGTH],
            "sentiment_score": 0.5,
            "google_review_time": review_date,
            "scraped_at": datetime.utcnow(),
            "extraction_source": r.get("source", source or "unknown"),
            "extraction_method": r.get("extraction_method", source or "unknown"),
            "confidence_score": r.get("decoder_confidence", 0.7 if source == "RPC" else 0.5),
            "extraction_metadata": {
                "decoder_confidence": r.get("decoder_confidence", 0),
                "helpful_votes": r.get("helpful_votes", 0),
                "has_owner_response": bool(r.get("owner_response")),
                "has_images": bool(r.get("image_urls"))
            }
        }
        
        # Add optional fields if available
        if r.get("image_urls"):
            normalized_review["image_urls"] = r["image_urls"]
        if r.get("owner_response"):
            normalized_review["owner_response"] = r["owner_response"]
        if r.get("helpful_votes"):
            normalized_review["helpful_votes"] = r["helpful_votes"]
        if r.get("date"):
            normalized_review["raw_date"] = r["date"]
        
        normalized.append(normalized_review)
    
    duration = time.time() - start_time
    
    # Record metrics
    metrics_collector.record(place_id, {
        "reviews_found": len(normalized),
        "source": source or "unknown",
        "duration": duration,
        "scrolls": extraction_metadata["scrolls"],
        "expansions": extraction_metadata["expansions"],
        "rpc_reviews": extraction_metadata["rpc_reviews"],
        "dom_reviews": extraction_metadata["dom_reviews"]
    })
    
    logger.info("=" * 80)
    logger.info(f"✅ FINAL REVIEWS: {len(normalized)}")
    logger.info(f"📊 Source: {source if source else 'RPC'}")
    logger.info(f"⏱️  Duration: {duration:.2f}s")
    logger.info(f"📈 Metrics: RPC={extraction_metadata['rpc_reviews']}, DOM={extraction_metadata['dom_reviews']}")
    
    if len(normalized) >= 50:
        logger.info("🎯 SUCCESS: 50+ reviews fetched!")
    elif len(normalized) > 0:
        logger.info(f"📈 Progress: {len(normalized)}/50 reviews")
    else:
        logger.warning("⚠️ No reviews found - check place_id or try again")
    
    # Log selector rankings for debugging
    top_selectors = selector_brain.data.get("selectors", {})
    if top_selectors:
        best = max(top_selectors.items(), 
                  key=lambda x: x[1].get("success", 0) / max(1, x[1].get("success", 0) + x[1].get("fail", 0)))
        logger.info(f"📊 Best selector: {best[0][:50]} ({best[1].get('success', 0)} wins)")
    
    # Log proxy performance
    proxy_stats = proxy_brain.data.get("proxies", {})
    if proxy_stats:
        best_proxy = max(proxy_stats.items(), key=lambda x: x[1].get("score", 0))
        logger.info(f"🌐 Best proxy: {best_proxy[0][:30]} (score: {best_proxy[1].get('score', 0):.2f})")
    
    logger.info("=" * 80)
    
    return normalized

async def run_scraper(place_id: str) -> List[Dict]:
    """Alias for compatibility"""
    return await scrape_google_reviews(place_id)

# =========================================================
# READY
# =========================================================

print("=" * 80)
print("✅ QUANTUM ENTERPRISE SCRAPER V30.0 READY")
print(f"   RPC Decoder: ENHANCED (5 formats, confidence scoring)")
print(f"   Network Interceptor: ACTIVE (memory limited, metrics)")
print(f"   Adaptive Scroll: ACTIVE ({ScraperConfig.MAX_SCROLLS} max, dynamic distance)")
print(f"   Review Expansion: ACTIVE (metadata capture)")
print(f"   Selector Brain: {len(selector_brain.data.get('selectors', {}))} selectors (expiry: {ScraperConfig.SELECTOR_EXPIRY_DAYS}d)")
print(f"   Proxy Brain: {len(proxy_brain.data.get('proxies', {}))} proxies (cooldown enabled)")
print(f"   Proxy Pool: {len(PROXY_POOL)} proxies")
print(f"   Metrics Collection: ACTIVE")
print(f"   Screenshot on Error: {ScraperConfig.SCREENSHOT_ON_ERROR}")
print("=" * 80)
