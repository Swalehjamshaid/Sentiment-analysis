# ==========================================================
# FILE: app/routes/reviews.py
# REVIEW INTEL AI — ENTERPRISE REVIEW ENGINE
# FINAL STABLE VERSION — MAY 2026
#
# FULLY SYNCHRONIZED WITH:
# ✅ dashboard.py
# ✅ scraper.py
# ✅ chatbot.py
# ✅ PostgreSQL
# ✅ Railway
# ✅ Frontend Dashboard
# ✅ Incremental Sync
# ✅ Duplicate Protection
# ==========================================================

import logging

from datetime import datetime

from fastapi import (
    APIRouter,
    HTTPException,
    Request
)

from sqlalchemy import (
    select,
    desc
)

# ==========================================================
# DATABASE
# ==========================================================

from app.core.db import (
    AsyncSessionLocal
)

# ==========================================================
# MODELS
# ==========================================================

from app.core.models import (
    Review,
    Company
)

# ==========================================================
# SCRAPER
# ==========================================================

from app.services.scraper import (
    scrape_serpapi_reviews,
    playwright_backup,
    load_existing_review_ids
)

# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(
    "app.routes.reviews"
)

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(

    prefix="/api/reviews",

    tags=["Reviews"]
)

# ==========================================================
# SAFE HELPERS
# ==========================================================

def safe_int(value):

    try:
        return int(value)
    except:
        return 0

# ==========================================================

def calculate_sentiment(rating):

    try:

        rating = safe_int(rating)

        if rating >= 4:
            return "positive"

        elif rating <= 2:
            return "negative"

        return "neutral"

    except:

        return "neutral"

# ==========================================================
# GET REVIEWS
# ==========================================================

@router.get("/company/{company_id}")

async def get_company_reviews(

    company_id: int,

    limit: int = 100
):

    try:

        logger.info(
            f"🚀 LOADING REVIEWS => {company_id}"
        )

        async with AsyncSessionLocal() as db:

            company_stmt = select(
                Company
            ).where(
                Company.id == company_id
            )

            company_result = await db.execute(
                company_stmt
            )

            company = company_result.scalar_one_or_none()

            if not company:

                raise HTTPException(

                    status_code=404,

                    detail="Company not found"
                )

            stmt = (

                select(Review)

                .where(
                    Review.company_id == company_id
                )

                .order_by(
                    desc(
                        Review.google_review_time
                    )
                )

                .limit(limit)
            )

            result = await db.execute(stmt)

            reviews = result.scalars().all()

            logger.info(
                f"✅ REVIEWS FETCHED => {len(reviews)}"
            )

            formatted_reviews = []

            for review in reviews:

                formatted_reviews.append({

                    "id":
                        review.id,

                    "author_name":
                        review.author_name,

                    "rating":
                        review.rating,

                    "text":
                        review.text,

                    "review_date":
                        review.review_date,

                    "google_review_time":

                        str(
                            review.google_review_time
                        )
                        if review.google_review_time
                        else None,

                    "sentiment":

                        calculate_sentiment(
                            review.rating
                        ),

                    "likes":

                        getattr(
                            review,
                            "likes",
                            0
                        )
                })

            return {

                "status":
                    "success",

                "company": {

                    "id":
                        company.id,

                    "name":
                        company.name
                },

                "count":
                    len(formatted_reviews),

                "reviews":
                    formatted_reviews
            }

    except HTTPException:

        raise

    except Exception as e:

        logger.exception(
            "❌ GET REVIEWS FAILED"
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# SYNC REVIEWS
# ==========================================================

@router.post("/sync/{company_id}")

async def sync_reviews(

    request: Request,

    company_id: int
):

    try:

        logger.info(
            f"🚀 REVIEW SYNC STARTED => {company_id}"
        )

        async with AsyncSessionLocal() as db:

            # ==================================================
            # COMPANY
            # ==================================================

            company_stmt = select(
                Company
            ).where(
                Company.id == company_id
            )

            company_result = await db.execute(
                company_stmt
            )

            company = company_result.scalar_one_or_none()

            if not company:

                raise HTTPException(

                    status_code=404,

                    detail="Company not found"
                )

            # ==================================================
            # PLACE ID
            # ==================================================

            place_id = getattr(
                company,
                "google_place_id",
                None
            )

            if not place_id:

                raise HTTPException(

                    status_code=400,

                    detail="Company missing google_place_id"
                )

            # ==================================================
            # EXISTING IDS
            # ==================================================

            existing_ids = await load_existing_review_ids(
                company_id
            )

            # ==================================================
            # SERPAPI
            # ==================================================

            reviews = await scrape_serpapi_reviews(

                place_id=
                    place_id,

                existing_ids=
                    existing_ids,

                target_limit=150
            )

            # ==================================================
            # PLAYWRIGHT FALLBACK
            # ==================================================

            if not reviews:

                logger.warning(
                    "⚠️ SERPAPI EMPTY — PLAYWRIGHT FALLBACK"
                )

                reviews = await playwright_backup(

                    place_id=
                        place_id,

                    existing_ids=
                        existing_ids,

                    target_limit=80
                )

            # ==================================================
            # NO REVIEWS
            # ==================================================

            if not reviews:

                return {

                    "status":
                        "success",

                    "inserted_reviews":
                        0,

                    "message":
                        "No new reviews found."
                }

            # ==================================================
            # INSERT
            # ==================================================

            inserted = 0

            skipped = 0

            for review_data in reviews:

                try:

                    review_id = review_data.get(
                        "review_id"
                    )

                    # ==============================
                    # DUPLICATE CHECK
                    # ==============================

                    existing_stmt = select(
                        Review
                    ).where(

                        Review.company_id == company_id,

                        Review.google_review_id == review_id
                    )

                    existing_result = await db.execute(
                        existing_stmt
                    )

                    existing_review = existing_result.scalar_one_or_none()

                    if existing_review:

                        skipped += 1

                        continue

                    # ==============================
                    # CREATE REVIEW
                    # ==============================

                    review = Review(

                        company_id=
                            company_id,

                        google_review_id=
                            review_id,

                        author_name=
                            review_data.get(
                                "author_name",
                                "Anonymous"
                            ),

                        rating=
                            safe_int(
                                review_data.get(
                                    "rating",
                                    5
                                )
                            ),

                        text=
                            review_data.get(
                                "text",
                                ""
                            ),

                        review_date=
                            review_data.get(
                                "review_date",
                                ""
                            ),

                        google_review_time=

                            datetime.fromisoformat(

                                review_data.get(
                                    "google_review_time"
                                )
                            )

                            if review_data.get(
                                "google_review_time"
                            )

                            else datetime.utcnow(),

                        likes=
                            safe_int(
                                review_data.get(
                                    "likes",
                                    0
                                )
                            )
                    )

                    db.add(review)

                    inserted += 1

                except Exception as review_error:

                    logger.warning(
                        f"⚠️ REVIEW INSERT FAILED => {review_error}"
                    )

                    continue

            # ==================================================
            # COMMIT
            # ==================================================

            await db.commit()

            logger.info(
                f"✅ INSERTED => {inserted}"
            )

            logger.info(
                f"⏭️ SKIPPED => {skipped}"
            )

            # ==================================================
            # RESPONSE
            # ==================================================

            return {

                "status":
                    "success",

                "company": {

                    "id":
                        company.id,

                    "name":
                        company.name
                },

                "inserted_reviews":
                    inserted,

                "skipped_reviews":
                    skipped,

                "total_fetched":
                    len(reviews),

                "message":

                    f"{inserted} new reviews added."
            }

    except HTTPException:

        raise

    except Exception as e:

        logger.exception(
            "❌ REVIEW SYNC FAILED"
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# DELETE REVIEW
# ==========================================================

@router.delete("/{review_id}")

async def delete_review(

    review_id: int
):

    try:

        async with AsyncSessionLocal() as db:

            stmt = select(
                Review
            ).where(
                Review.id == review_id
            )

            result = await db.execute(stmt)

            review = result.scalar_one_or_none()

            if not review:

                raise HTTPException(

                    status_code=404,

                    detail="Review not found"
                )

            await db.delete(review)

            await db.commit()

            logger.info(
                f"🗑️ REVIEW DELETED => {review_id}"
            )

            return {

                "status":
                    "success",

                "message":
                    "Review deleted successfully"
            }

    except HTTPException:

        raise

    except Exception as e:

        logger.exception(
            "❌ DELETE REVIEW FAILED"
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# REVIEW HEALTH
# ==========================================================

@router.get("/health")

async def reviews_health():

    return {

        "status":
            "healthy",

        "service":
            "reviews",

        "timestamp":
            str(
                datetime.utcnow()
            )
    }
