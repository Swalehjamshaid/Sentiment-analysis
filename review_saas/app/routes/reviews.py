# =========================================================
# FILE: app/routes/reviews.py
# TRUSTLYTICS AI - ENTERPRISE REVIEWS ROUTER
# FULLY ALIGNED WITH scraper.py
# FASTAPI + ASYNC + FRONTEND SAFE
# =========================================================

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import (
    select,
    desc,
    and_,
    func
)

from typing import Optional

from datetime import datetime

import traceback
import logging
import hashlib

# =========================================================
# DATABASE
# =========================================================

from app.core.db import get_db

# =========================================================
# MODELS
# =========================================================

from app.core.models import (
    Company,
    Review
)

# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

print("✅ REVIEWS LOGGER READY")

# =========================================================
# SCRAPER IMPORT
# =========================================================

SCRAPER_AVAILABLE = True

try:

    from app.services.scraper import scrape_google_reviews

    print(
        "✅ SCRAPER IMPORT SUCCESS"
    )

except Exception as scraper_error:

    print(
        f"❌ SCRAPER IMPORT FAILED => {scraper_error}"
    )

    print(
        traceback.format_exc()
    )

    SCRAPER_AVAILABLE = False

    async def scrape_google_reviews(
        place_id: str
    ):
        return []

# =========================================================
# ROUTER
# =========================================================

router = APIRouter(

    prefix="/api/reviews",

    tags=["Reviews"]
)

print("✅ REVIEWS ROUTER LOADED")

# =========================================================
# HELPERS
# =========================================================

def serialize_datetime(value):

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def normalize_datetime(value):

    if isinstance(value, datetime):
        return value

    return datetime.utcnow()


def safe_float(
    value,
    default=0.5
):

    try:
        return float(value)

    except Exception:
        return default


def safe_rating(
    value,
    default=5
):

    try:

        rating = int(float(value))

    except Exception:

        rating = default

    if rating < 1:
        rating = 1

    if rating > 5:
        rating = 5

    return rating


def generate_google_review_id(
    company_id: int,
    author: str,
    review_text: str
):

    raw_value = (
        f"{company_id}:{author}:{review_text}"
    )

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()

# =========================================================
# SCRAPER EXECUTION
# =========================================================

async def run_scraper(
    google_place_id: str
):

    try:

        logger.info(
            f"🚀 RUNNING SCRAPER => {google_place_id}"
        )

        result = await scrape_google_reviews(
            google_place_id
        )

        if not isinstance(
            result,
            list
        ):

            logger.error(
                f"❌ INVALID SCRAPER RESPONSE => {type(result)}"
            )

            return []

        logger.info(
            f"✅ SCRAPER REVIEWS => {len(result)}"
        )

        return result

    except Exception as e:

        logger.error(
            f"❌ SCRAPER EXECUTION ERROR => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return []

# =========================================================
# RESPONSE BUILDER
# =========================================================

def build_sync_response(

    success: bool,

    message: str,

    company_id: int,

    company_name: Optional[str] = None,

    inserted_reviews: int = 0,

    duplicate_reviews: int = 0,

    failed_reviews: int = 0,

    scraped_reviews=None,
):

    scraped_reviews = scraped_reviews or []

    total_scraped = len(scraped_reviews)

    return {

        "success":
            success,

        "message":
            message,

        "company_id":
            company_id,

        "company_name":
            company_name,

        "inserted_reviews":
            inserted_reviews,

        "duplicate_reviews":
            duplicate_reviews,

        "failed_reviews":
            failed_reviews,

        "total_scraped":
            total_scraped,

        "scraped_reviews":
            scraped_reviews,

        # FRONTEND SAFE
        "reviews_collected":
            inserted_reviews,

        "reviewsCollected":
            inserted_reviews,

        "insertedReviews":
            inserted_reviews,

        "duplicateReviews":
            duplicate_reviews,

        "failedReviews":
            failed_reviews,

        "totalScraped":
            total_scraped,

        "scrapedReviews":
            scraped_reviews
    }

# =========================================================
# HEALTH ROUTE
# =========================================================

@router.get("/health")
async def reviews_health():

    return {

        "success": True,

        "service": "reviews",

        "status": "healthy",

        "scraper_available": SCRAPER_AVAILABLE,

        "timestamp": datetime.utcnow().isoformat()
    }

# =========================================================
# GET COMPANY REVIEWS
# =========================================================

@router.get("/company/{company_id}")
async def get_company_reviews(

    company_id: int,

    limit: int = Query(
        100,
        ge=1,
        le=1000
    ),

    skip: int = Query(
        0,
        ge=0
    ),

    rating: Optional[int] = Query(
        None,
        ge=1,
        le=5
    ),

    db: AsyncSession = Depends(get_db)
):

    try:

        logger.info(
            f"📊 FETCHING REVIEWS => {company_id}"
        )

        company_result = await db.execute(

            select(Company).where(
                Company.id == company_id
            )
        )

        company = company_result.scalar_one_or_none()

        if not company:

            raise HTTPException(

                status_code=404,

                detail="Company not found"
            )

        query = select(Review).where(
            Review.company_id == company_id
        )

        count_query = select(
            func.count(Review.id)
        ).where(
            Review.company_id == company_id
        )

        if rating is not None:

            query = query.where(
                Review.rating == rating
            )

            count_query = count_query.where(
                Review.rating == rating
            )

        total_result = await db.execute(
            count_query
        )

        total_reviews = total_result.scalar() or 0

        reviews_result = await db.execute(

            query.order_by(
                desc(Review.created_at)
            ).offset(skip).limit(limit)
        )

        reviews = reviews_result.scalars().all()

        response_reviews = []

        for review in reviews:

            response_reviews.append({

                "id":
                    review.id,

                "company_id":
                    review.company_id,

                "author":
                    review.author_name,

                "author_name":
                    review.author_name,

                "rating":
                    review.rating,

                "content":
                    review.text,

                "review_text":
                    review.text,

                "text":
                    review.text,

                "sentiment_score":
                    review.sentiment_score,

                "google_review_time":
                    serialize_datetime(
                        review.google_review_time
                    ),

                "created_at":
                    serialize_datetime(
                        review.created_at
                    )
            })

        logger.info(
            f"✅ REVIEWS FETCHED => {len(response_reviews)}"
        )

        return {

            "success": True,

            "company_id": company_id,

            "company_name": company.name,

            "total_reviews": total_reviews,

            "reviews": response_reviews
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.error(
            f"❌ GET REVIEWS ERROR => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# SYNC REVIEWS
# =========================================================

print("🔥 SYNC ROUTE REGISTERED")

@router.post("/sync/{company_id}")
@router.post("/sync/{company_id}/")
async def sync_reviews(

    company_id: int,

    db: AsyncSession = Depends(get_db)
):

    try:

        logger.info(
            f"🚀 SYNC STARTED => {company_id}"
        )

        company_result = await db.execute(

            select(Company).where(
                Company.id == company_id
            )
        )

        company = company_result.scalar_one_or_none()

        if not company:

            raise HTTPException(

                status_code=404,

                detail="Company not found"
            )

        if not SCRAPER_AVAILABLE:

            return build_sync_response(

                success=False,

                message="scraper.py unavailable",

                company_id=company_id,

                company_name=company.name
            )

        google_place_id = getattr(
            company,
            "google_place_id",
            None
        )

        if not google_place_id:

            return build_sync_response(

                success=False,

                message="Google Place ID missing",

                company_id=company_id,

                company_name=company.name
            )

        logger.info(
            f"🌍 SCRAPING REVIEWS => {google_place_id}"
        )

        scraped_reviews = await run_scraper(
            google_place_id
        )

        logger.info(
            f"🔥 SCRAPED REVIEWS => {len(scraped_reviews)}"
        )

        if not scraped_reviews:

            return build_sync_response(

                success=False,

                message="No reviews fetched",

                company_id=company_id,

                company_name=company.name,

                scraped_reviews=[]
            )

        inserted_reviews = 0
        duplicate_reviews = 0
        failed_reviews = 0

        for item in scraped_reviews:

            try:

                review_text = str(

                    item.get(
                        "review_text",

                        item.get(
                            "content",

                            item.get(
                                "text",
                                ""
                            )
                        )
                    )

                ).strip()

                if not review_text:

                    failed_reviews += 1

                    continue

                author = str(

                    item.get(
                        "author",

                        item.get(
                            "author_name",
                            "Anonymous"
                        )
                    )

                ).strip()

                if not author:

                    author = "Anonymous"

                rating = safe_rating(

                    item.get(
                        "rating",
                        5
                    )
                )

                duplicate_result = await db.execute(

                    select(Review).where(

                        and_(

                            Review.company_id
                            == company_id,

                            Review.text
                            == review_text,

                            Review.author_name
                            == author
                        )
                    )
                )

                existing_review = (
                    duplicate_result
                    .scalar_one_or_none()
                )

                if existing_review:

                    duplicate_reviews += 1

                    continue

                google_review_id = str(

                    item.get(
                        "google_review_id",
                        ""
                    )

                ).strip()

                if not google_review_id:

                    google_review_id = (
                        generate_google_review_id(

                            company_id,

                            author,

                            review_text
                        )
                    )

                review = Review(

                    company_id=company_id,

                    google_review_id=google_review_id,

                    author_name=author,

                    rating=rating,

                    text=review_text,

                    sentiment_score=safe_float(

                        item.get(
                            "sentiment_score",
                            0.5
                        )
                    ),

                    google_review_time=normalize_datetime(

                        item.get(
                            "google_review_time"
                        )
                    ),

                    created_at=datetime.utcnow()
                )

                db.add(review)

                inserted_reviews += 1

            except Exception as review_error:

                failed_reviews += 1

                logger.error(
                    f"❌ REVIEW INSERT ERROR => {review_error}"
                )

                logger.error(
                    traceback.format_exc()
                )

        await db.commit()

        logger.info(
            f"✅ SYNC COMPLETE => {inserted_reviews}"
        )

        return build_sync_response(

            success=True,

            message="Reviews synced successfully",

            company_id=company_id,

            company_name=company.name,

            inserted_reviews=inserted_reviews,

            duplicate_reviews=duplicate_reviews,

            failed_reviews=failed_reviews,

            scraped_reviews=scraped_reviews
        )

    except HTTPException:
        raise

    except Exception as e:

        await db.rollback()

        logger.error(
            f"❌ SYNC ERROR => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# ROUTER READY
# =========================================================

logger.info(
    f"✅ SCRAPER AVAILABLE => {SCRAPER_AVAILABLE}"
)

print(
    "✅ REVIEWS ROUTER FULLY READY"
)
