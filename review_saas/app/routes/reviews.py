# ==========================================================
# FILE: app/routes/reviews.py
# TRUSTLYTICS AI SAAS - ENTERPRISE REVIEWS ROUTES
# FINAL FIXED VERSION - MAY 2026
# ==========================================================

import logging
import traceback

from typing import (
    List,
    Dict,
    Any
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status
)

from sqlalchemy import (
    select,
    func,
    desc
)

from sqlalchemy.ext.asyncio import AsyncSession

# ==========================================================
# DATABASE
# ==========================================================

from app.core.db import get_db

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
    scrape_google_reviews
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
    prefix="/reviews",
    tags=["Reviews"]
)

# ==========================================================
# HEALTH CHECK
# ==========================================================

@router.get("/health")

async def reviews_health():

    return {

        "success": True,

        "service":
            "reviews",

        "status":
            "healthy"
    }

# ==========================================================
# SAVE SCRAPED REVIEWS
# ==========================================================

async def save_reviews_to_database(

    db: AsyncSession,

    company_id: int,

    scraped_reviews: list
):

    inserted_reviews = []

    for item in scraped_reviews:

        try:

            google_review_id = item.get(
                "review_id"
            )

            # ==============================================
            # DUPLICATE CHECK
            # ==============================================

            existing_stmt = select(
                Review
            ).where(
                Review.google_review_id ==
                google_review_id
            )

            existing_result = await db.execute(
                existing_stmt
            )

            existing_review = (
                existing_result.scalar_one_or_none()
            )

            if existing_review:
                continue

            # ==============================================
            # CREATE REVIEW
            # ==============================================

            review = Review(

                company_id=company_id,

                google_review_id=google_review_id,

                author_name=item.get(
                    "author_name",
                    "Anonymous"
                ),

                rating=item.get(
                    "rating",
                    5
                ),

                text=item.get(
                    "text",
                    ""
                ),

                review_likes=item.get(
                    "likes",
                    0
                )
            )

            db.add(review)

            inserted_reviews.append({

                "author_name":
                    review.author_name,

                "rating":
                    review.rating,

                "text":
                    review.text[:100]
            })

        except Exception as inner_error:

            logger.error(
                f"❌ INSERT FAILED: {inner_error}"
            )

    await db.commit()

    return inserted_reviews

# ==========================================================
# SYNC REVIEWS FROM GOOGLE
# ==========================================================

@router.post("/sync")

async def sync_reviews(

    place_id: str,

    company_id: int,

    target_limit: int = 100,

    db: AsyncSession = Depends(get_db)
):

    logger.info(
        f"🚀 Review sync started | company={company_id}"
    )

    try:

        # ==================================================
        # VALIDATE COMPANY
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

                status_code=
                    status.HTTP_404_NOT_FOUND,

                detail=
                    "Company not found"
            )

        # ==================================================
        # SCRAPE REVIEWS
        # ==================================================

        scraped_reviews = await scrape_google_reviews(

            place_id=place_id,

            target_limit=target_limit
        )

        # ==================================================
        # SAVE REVIEWS
        # ==================================================

        inserted_reviews = await save_reviews_to_database(

            db=db,

            company_id=company_id,

            scraped_reviews=scraped_reviews
        )

        logger.info(
            f"✅ Sync completed | inserted={len(inserted_reviews)}"
        )

        return {

            "success":
                True,

            "company_id":
                company_id,

            "inserted_reviews":
                len(inserted_reviews),

            "reviews":
                inserted_reviews
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"❌ Sync failed: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        raise HTTPException(

            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=
                str(e)
        )

# ==========================================================
# FRONTEND COMPATIBILITY INGEST ROUTE
# ==========================================================

@router.post("/ingest/{company_id}")

async def ingest_reviews(

    company_id: int,

    db: AsyncSession = Depends(get_db)
):

    logger.info(
        f"🚀 Frontend ingest started | company={company_id}"
    )

    try:

        stmt = select(
            Company
        ).where(
            Company.id == company_id
        )

        result = await db.execute(
            stmt
        )

        company = result.scalar_one_or_none()

        if not company:

            raise HTTPException(

                status_code=
                    status.HTTP_404_NOT_FOUND,

                detail=
                    "Company not found"
            )

        place_id = getattr(
            company,
            "google_place_id",
            None
        )

        if not place_id:

            raise HTTPException(

                status_code=
                    status.HTTP_400_BAD_REQUEST,

                detail=
                    "Company missing Google Place ID"
            )

        # ==================================================
        # SCRAPE REVIEWS
        # ==================================================

        scraped_reviews = await scrape_google_reviews(

            place_id=place_id,

            target_limit=100
        )

        # ==================================================
        # SAVE REVIEWS
        # ==================================================

        inserted_reviews = await save_reviews_to_database(

            db=db,

            company_id=company_id,

            scraped_reviews=scraped_reviews
        )

        return {

            "success":
                True,

            "company_id":
                company_id,

            "reviews_collected":
                len(inserted_reviews),

            "reviews":
                inserted_reviews
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(
            f"❌ Frontend ingest failed: {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        raise HTTPException(

            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=
                str(e)
        )

# ==========================================================
# GET ALL REVIEWS
# ==========================================================

@router.get("/all")

async def get_all_reviews(

    company_id: int,

    limit: int = Query(
        default=50,
        le=500
    ),

    db: AsyncSession = Depends(get_db)
):

    try:

        stmt = (

            select(Review)

            .where(
                Review.company_id == company_id
            )

            .order_by(
                desc(Review.created_at)
            )

            .limit(limit)
        )

        result = await db.execute(
            stmt
        )

        reviews = result.scalars().all()

        response = []

        for review in reviews:

            response.append({

                "id":
                    review.id,

                "company_id":
                    review.company_id,

                "google_review_id":
                    review.google_review_id,

                "author_name":
                    review.author_name,

                "rating":
                    review.rating,

                "text":
                    review.text,

                "sentiment_score":
                    review.sentiment_score,

                "review_likes":
                    review.review_likes,

                "google_review_time":
                    review.google_review_time,

                "first_seen_at":
                    review.first_seen_at,

                "issue_category":
                    review.issue_category,

                "emotion":
                    review.emotion,

                "urgency_score":
                    review.urgency_score,

                "ai_summary":
                    review.ai_summary,

                "risk_score":
                    review.risk_score,

                "topic_cluster":
                    review.topic_cluster,

                "created_at":
                    review.created_at
            })

        return {

            "success":
                True,

            "count":
                len(response),

            "reviews":
                response
        }

    except Exception as e:

        logger.exception(
            f"❌ Get reviews failed: {e}"
        )

        raise HTTPException(

            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=
                str(e)
        )

# ==========================================================
# DASHBOARD ANALYTICS
# ==========================================================

@router.get("/dashboard/stats")

async def dashboard_stats(

    company_id: int,

    db: AsyncSession = Depends(get_db)
):

    try:

        total_stmt = (

            select(
                func.count(Review.id)
            )

            .where(
                Review.company_id == company_id
            )
        )

        total_result = await db.execute(
            total_stmt
        )

        total_reviews = (
            total_result.scalar() or 0
        )

        avg_stmt = (

            select(
                func.avg(Review.rating)
            )

            .where(
                Review.company_id == company_id
            )
        )

        avg_result = await db.execute(
            avg_stmt
        )

        average_rating = avg_result.scalar()

        if average_rating is None:
            average_rating = 0

        average_rating = round(
            float(average_rating),
            2
        )

        recent_stmt = (

            select(Review)

            .where(
                Review.company_id == company_id
            )

            .order_by(
                desc(Review.created_at)
            )

            .limit(10)
        )

        recent_result = await db.execute(
            recent_stmt
        )

        recent_reviews = (
            recent_result.scalars().all()
        )

        recent_reviews_data = []

        for review in recent_reviews:

            recent_reviews_data.append({

                "author_name":
                    review.author_name,

                "rating":
                    review.rating,

                "text":
                    review.text,

                "created_at":
                    review.created_at
            })

        return {

            "success":
                True,

            "dashboard": {

                "total_reviews":
                    total_reviews,

                "average_rating":
                    average_rating,

                "recent_reviews":
                    recent_reviews_data
            }
        }

    except Exception as e:

        logger.exception(
            f"❌ Dashboard stats failed: {e}"
        )

        raise HTTPException(

            status_code=
                status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail=
                str(e)
        )
