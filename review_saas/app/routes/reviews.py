# ==========================================================
# FILE: app/routes/reviews.py
# TRUSTLYTICS AI SAAS - REVIEWS ROUTES
# ==========================================================

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)

from sqlalchemy import (
    select,
    func,
    desc
)

from sqlalchemy.ext.asyncio import AsyncSession

from typing import List

from app.core.database import get_db
from app.core.models import Review

from app.services.scraper import (
    fetch_reviews_from_google
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
        "status": "healthy",
        "service": "reviews"
    }

# ==========================================================
# SYNC REVIEWS
# ==========================================================

@router.post("/sync")
async def sync_reviews(

    place_id: str,

    company_id: int,

    target_limit: int = 100,

    db: AsyncSession = Depends(get_db)
):

    try:

        reviews = await fetch_reviews_from_google(

            place_id=place_id,

            company_id=company_id,

            session=db,

            target_limit=target_limit
        )

        return {

            "success": True,

            "inserted_reviews":
                len(reviews),

            "reviews":
                reviews
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# GET ALL REVIEWS
# ==========================================================

@router.get("/all")
async def get_all_reviews(

    company_id: int,

    limit: int = Query(50, le=500),

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

        result = await db.execute(stmt)

        reviews = result.scalars().all()

        response = []

        for review in reviews:

            response.append({

                "id":
                    review.id,

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

                "created_at":
                    review.created_at
            })

        return {

            "success": True,

            "count":
                len(response),

            "reviews":
                response
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# DASHBOARD ANALYTICS
# ==========================================================

@router.get("/dashboard")
async def dashboard_analytics(

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

        total_reviews = total_result.scalar() or 0

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

        positive_stmt = (

            select(
                func.count(Review.id)
            )

            .where(
                Review.company_id == company_id
            )

            .where(
                Review.rating >= 4
            )
        )

        positive_result = await db.execute(
            positive_stmt
        )

        positive_reviews = (
            positive_result.scalar() or 0
        )

        negative_stmt = (

            select(
                func.count(Review.id)
            )

            .where(
                Review.company_id == company_id
            )

            .where(
                Review.rating <= 2
            )
        )

        negative_result = await db.execute(
            negative_stmt
        )

        negative_reviews = (
            negative_result.scalar() or 0
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

            "success": True,

            "dashboard": {

                "total_reviews":
                    total_reviews,

                "average_rating":
                    average_rating,

                "positive_reviews":
                    positive_reviews,

                "negative_reviews":
                    negative_reviews,

                "recent_reviews":
                    recent_reviews_data
            }
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )
