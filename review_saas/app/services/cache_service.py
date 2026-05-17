# ==========================================================
# FILE: app/services/cache_service.py
# WORLD-CLASS ENTERPRISE CACHE ENGINE
# REDIS + IN-MEMORY HYBRID CACHING SYSTEM
# ==========================================================

import os
import json
import time
import hashlib
import logging
from typing import Any, Dict, Optional

try:
    import redis
except Exception:
    redis = None


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(__name__)


# ==========================================================
# CACHE SERVICE
# ==========================================================

class CacheService:

    """
    ======================================================
    ENTERPRISE AI CACHE ENGINE
    ======================================================

    FEATURES:
    - Redis caching
    - In-memory fallback cache
    - Ultra-fast repeated responses
    - AI cost reduction
    - Smart expiration system
    - Railway optimized
    - Hybrid cache architecture
    - Safe serialization
    """

    def __init__(self):

        # ==================================================
        # REDIS CONFIG
        # ==================================================

        self.redis_url = os.getenv(
            "REDIS_URL",
            None
        )

        self.redis_client = None

        self.default_ttl = 3600

        self.memory_cache = {}

        self.cache_stats = {

            "hits": 0,
            "misses": 0,
            "writes": 0

        }

        # ==================================================
        # INITIALIZE REDIS
        # ==================================================

        self.initialize_redis()

    # ======================================================
    # INITIALIZE REDIS
    # ======================================================

    def initialize_redis(self):

        try:

            if not redis:

                logger.warning(
                    "⚠️ Redis package not installed. Using memory cache only."
                )

                return

            if not self.redis_url:

                logger.warning(
                    "⚠️ REDIS_URL not found. Using memory cache only."
                )

                return

            self.redis_client = redis.Redis.from_url(

                self.redis_url,

                decode_responses=True

            )

            self.redis_client.ping()

            logger.info(
                "✅ Redis Cache Connected"
            )

        except Exception as e:

            logger.error(
                f"❌ Redis Connection Error: {e}"
            )

            self.redis_client = None

    # ======================================================
    # CACHE KEY GENERATOR
    # ======================================================

    def generate_key(
        self,
        prefix: str,
        data: str
    ) -> str:

        try:

            raw_key = f"{prefix}:{data}"

            hashed = hashlib.md5(
                raw_key.encode()
            ).hexdigest()

            return f"{prefix}:{hashed}"

        except Exception as e:

            logger.error(
                f"❌ Cache Key Error: {e}"
            )

            return f"{prefix}:fallback"

    # ======================================================
    # SET CACHE
    # ======================================================

    def set(

        self,
        key: str,
        value: Any,
        ttl: int = None

    ) -> bool:

        try:

            if ttl is None:
                ttl = self.default_ttl

            serialized = json.dumps(value)

            # ==============================================
            # REDIS CACHE
            # ==============================================

            if self.redis_client:

                self.redis_client.setex(

                    key,
                    ttl,
                    serialized

                )

            # ==============================================
            # MEMORY CACHE
            # ==============================================

            self.memory_cache[key] = {

                "value": value,

                "expires_at":
                    time.time() + ttl

            }

            self.cache_stats["writes"] += 1

            return True

        except Exception as e:

            logger.error(
                f"❌ Cache Set Error: {e}"
            )

            return False

    # ======================================================
    # GET CACHE
    # ======================================================

    def get(
        self,
        key: str
    ) -> Optional[Any]:

        try:

            # ==============================================
            # REDIS CACHE
            # ==============================================

            if self.redis_client:

                cached = self.redis_client.get(
                    key
                )

                if cached:

                    self.cache_stats["hits"] += 1

                    return json.loads(cached)

            # ==============================================
            # MEMORY CACHE
            # ==============================================

            memory_item = self.memory_cache.get(
                key
            )

            if memory_item:

                expires_at = memory_item.get(
                    "expires_at",
                    0
                )

                if time.time() < expires_at:

                    self.cache_stats["hits"] += 1

                    return memory_item["value"]

                else:

                    del self.memory_cache[key]

            self.cache_stats["misses"] += 1

            return None

        except Exception as e:

            logger.error(
                f"❌ Cache Get Error: {e}"
            )

            return None

    # ======================================================
    # DELETE CACHE
    # ======================================================

    def delete(
        self,
        key: str
    ) -> bool:

        try:

            if self.redis_client:

                self.redis_client.delete(
                    key
                )

            if key in self.memory_cache:

                del self.memory_cache[key]

            return True

        except Exception as e:

            logger.error(
                f"❌ Cache Delete Error: {e}"
            )

            return False

    # ======================================================
    # EXISTS
    # ======================================================

    def exists(
        self,
        key: str
    ) -> bool:

        try:

            if self.get(key) is not None:
                return True

            return False

        except Exception as e:

            logger.error(
                f"❌ Cache Exists Error: {e}"
            )

            return False

    # ======================================================
    # CLEAR CACHE
    # ======================================================

    def clear(self) -> bool:

        try:

            # ==============================================
            # REDIS CLEAR
            # ==============================================

            if self.redis_client:

                self.redis_client.flushdb()

            # ==============================================
            # MEMORY CLEAR
            # ==============================================

            self.memory_cache.clear()

            logger.info(
                "✅ Cache Cleared"
            )

            return True

        except Exception as e:

            logger.error(
                f"❌ Cache Clear Error: {e}"
            )

            return False

    # ======================================================
    # CLEAN EXPIRED MEMORY CACHE
    # ======================================================

    def cleanup_expired(self):

        try:

            current_time = time.time()

            expired_keys = []

            for key, item in self.memory_cache.items():

                expires_at = item.get(
                    "expires_at",
                    0
                )

                if current_time > expires_at:

                    expired_keys.append(
                        key
                    )

            for key in expired_keys:

                del self.memory_cache[key]

            logger.info(
                f"🧹 Cleaned {len(expired_keys)} expired cache items"
            )

        except Exception as e:

            logger.error(
                f"❌ Cache Cleanup Error: {e}"
            )

    # ======================================================
    # SMART CHATBOT CACHE
    # ======================================================

    def cache_chatbot_response(

        self,
        company_id: int,
        query: str,
        response: Dict[str, Any]

    ):

        try:

            cache_key = self.generate_key(

                "chatbot",

                f"{company_id}:{query}"

            )

            return self.set(

                cache_key,

                response,

                ttl=1800

            )

        except Exception as e:

            logger.error(
                f"❌ Chatbot Cache Error: {e}"
            )

            return False

    # ======================================================
    # GET CHATBOT CACHE
    # ======================================================

    def get_chatbot_response(

        self,
        company_id: int,
        query: str

    ):

        try:

            cache_key = self.generate_key(

                "chatbot",

                f"{company_id}:{query}"

            )

            return self.get(
                cache_key
            )

        except Exception as e:

            logger.error(
                f"❌ Chatbot Cache Fetch Error: {e}"
            )

            return None

    # ======================================================
    # CACHE ANALYTICS
    # ======================================================

    def cache_analytics(

        self,
        company_id: int,
        analytics: Dict[str, Any]

    ):

        try:

            cache_key = self.generate_key(

                "analytics",

                str(company_id)

            )

            return self.set(

                cache_key,

                analytics,

                ttl=3600

            )

        except Exception as e:

            logger.error(
                f"❌ Analytics Cache Error: {e}"
            )

            return False

    # ======================================================
    # GET ANALYTICS CACHE
    # ======================================================

    def get_analytics(

        self,
        company_id: int

    ):

        try:

            cache_key = self.generate_key(

                "analytics",

                str(company_id)

            )

            return self.get(
                cache_key
            )

        except Exception as e:

            logger.error(
                f"❌ Analytics Fetch Error: {e}"
            )

            return None

    # ======================================================
    # CACHE STATS
    # ======================================================

    def get_stats(self):

        try:

            total_requests = (

                self.cache_stats["hits"] +

                self.cache_stats["misses"]

            )

            hit_rate = 0

            if total_requests > 0:

                hit_rate = round(

                    (
                        self.cache_stats["hits"] /

                        total_requests
                    ) * 100,

                    2

                )

            return {

                "redis_enabled":
                    self.redis_client is not None,

                "memory_cache_size":
                    len(self.memory_cache),

                "cache_hits":
                    self.cache_stats["hits"],

                "cache_misses":
                    self.cache_stats["misses"],

                "cache_writes":
                    self.cache_stats["writes"],

                "hit_rate":
                    hit_rate

            }

        except Exception as e:

            logger.error(
                f"❌ Cache Stats Error: {e}"
            )

            return {}

    # ======================================================
    # HEALTH CHECK
    # ======================================================

    def health_check(self):

        try:

            redis_status = False

            if self.redis_client:

                self.redis_client.ping()

                redis_status = True

            return {

                "status": "healthy",

                "redis":
                    redis_status,

                "memory_cache":
                    True

            }

        except Exception as e:

            logger.error(
                f"❌ Cache Health Error: {e}"
            )

            return {

                "status": "unhealthy",

                "error":
                    str(e)

            }


# ==========================================================
# GLOBAL INSTANCE
# ==========================================================

cache_service = CacheService()
