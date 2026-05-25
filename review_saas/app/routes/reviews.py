# ==========================================================
# FILE: app/routes/reviews.py
# TRUSTLYTICS AI — ENTERPRISE REVIEW ROUTER
# FULLY ALIGNED WITH EXISTING SYSTEM
# ==========================================================

from __future__ import annotations

import logging
import traceback
from datetime import datetime

from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ==========================================================
# DATABASE
# ==========================================================

from app.core.db import get_db

# ==========================================================
# MODELS
# ==========================================================

from app.core.models import (
    Company,
    Review
)

# ==========================================================
# SCRAPER
# ==========================================================

from app.scraper import scrape_google_reviews

# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(__name__)

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(

    prefix="/api/reviews",

    tags=["Reviews"]
)

# ==========================================================
# HEALTH
# ==========================================================

@router.get("/health")

async def reviews_health():

    return {

        "success": True,

        "service": "reviews",

        "status": "running"
    }

# ==========================================================
# SYNC REVIEWS
# ==========================================================

@router.post("/sync/{company_id}")

async def sync_reviews(

    company_id: int,

    db: AsyncSession = Depends(get_db)
):

    try:

        logger.info(
            f"🚀 REVIEW SYNC STARTED => {company_id}"
        )

        # ==================================================
        # FIND COMPANY
        # ==================================================

        stmt = select(Company).where(
            Company.id == company_id
        )

        result = await db.execute(stmt)

        company = result.scalar_one_or_none()

        if not company:

            raise HTTPException(

                status_code=404,

                detail="Company not found"
            )

        logger.info(
            f"✅ COMPANY FOUND => {company.name}"
        )

        # ==================================================
        # PLACE ID VALIDATION
        # ==================================================

        place_id = company.google_place_id

        if not place_id:

            raise HTTPException(

                status_code=400,

                detail="Google Place ID missing"
            )

        logger.info(
            f"📍 PLACE ID => {place_id}"
        )

        # ==================================================
        # SCRAPE REVIEWS
        # ==================================================

        scraped_reviews = await scrape_google_reviews(
            place_id=place_id
        )

        logger.info(
            f"✅ SCRAPED REVIEWS => {len(scraped_reviews)}"
        )

        # ==================================================
        # SAVE REVIEWS
        # ==================================================

        added_count = 0
        skipped_count = 0

        for item in scraped_reviews:

            try:

                google_review_id = str(

                    item.get("review_id")

                    or

                    item.get("google_review_id")

                    or

                    item.get("id")

                    or

                    ""
                ).strip()

                if not google_review_id:

                    skipped_count += 1
                    continue

                # ==========================================
                # DUPLICATE CHECK
                # ==========================================

                existing_stmt = select(Review).where(

                    Review.google_review_id
                    == google_review_id
                )

                existing_result = await db.execute(
                    existing_stmt
                )

                existing_review = (
                    existing_result.scalar_one_or_none()
                )

                if existing_review:

                    skipped_count += 1
                    continue

                # ==========================================
                # DATE PARSING
                # ==========================================

                review_time = None

                try:

                    raw_date = item.get("review_time")

                    if raw_date:

                        if isinstance(raw_date, datetime):

                            review_time = raw_date

                        else:

                            review_time = datetime.fromisoformat(

                                str(raw_date)
                                .replace("Z", "+00:00")
                            )

                except Exception:

                    review_time = datetime.utcnow()

                # ==========================================
                # CREATE REVIEW
                # ==========================================

                new_review = Review(

                    company_id=company.id,

                    google_review_id=google_review_id,

                    author_name=item.get(
                        "author_name",
                        "Anonymous"
                    ),

                    rating=int(
                        item.get("rating", 0)
                    ),

                    text=item.get(
                        "text",
                        ""
                    ),

                    review_likes=int(
                        item.get(
                            "review_likes",
                            0
                        )
                    ),

                    google_review_time=review_time,

                    sentiment_score=float(
                        item.get(
                            "sentiment_score",
                            0
                        )
                    ),

                    issue_category=item.get(
                        "issue_category"
                    ),

                    emotion=item.get(
                        "emotion"
                    ),

                    urgency_score=float(
                        item.get(
                            "urgency_score",
                            0
                        )
                    ),

                    ai_summary=item.get(
                        "ai_summary"
                    ),

                    risk_score=float(
                        item.get(
                            "risk_score",
                            0
                        )
                    ),

                    topic_cluster=item.get(
                        "topic_cluster"
                    ),
                )

                db.add(new_review)

                added_count += 1

            except Exception as e:

                logger.error(
                    f"❌ REVIEW SAVE FAILED => {e}"
                )

                logger.error(
                    traceback.format_exc()
                )

        # ==================================================
        # COMMIT
        # ==================================================

        await db.commit()

        logger.info(
            f"✅ REVIEWS ADDED => {added_count}"
        )

        logger.info(
            f"⚠️ REVIEWS SKIPPED => {skipped_count}"
        )

        # ==================================================
        # RESPONSE
        # ==================================================

        return {

            "success": True,

            "company_id": company_id,

            "company_name": company.name,

            "reviews_collected": added_count,

            "reviews_skipped": skipped_count,

            "total_scraped": len(scraped_reviews)
        }

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"❌ REVIEW SYNC FAILED => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# ==========================================================
# GET COMPANY REVIEWS
# ==========================================================

@router.get("/company/{company_id}")

async def get_company_reviews(

    company_id: int,

    limit: int = 100,

    db: AsyncSession = Depends(get_db)
):

    try:

        stmt = (

            select(Review)

            .where(
                Review.company_id == company_id
            )

            .order_by(
                Review.google_review_time.desc()
            )

            .limit(limit)
        )

        result = await db.execute(stmt)

        reviews = result.scalars().all()

        formatted = []

        for review in reviews:

            formatted.append({

                "id": review.id,

                "author": review.author_name,

                "rating": review.rating,

                "content": review.text,

                "created_at": str(
                    review.google_review_time
                ),

                "sentiment":

                    "positive"

                    if (review.rating or 0) >= 4

                    else

                    "negative"

                    if (review.rating or 0) <= 2

                    else

                    "neutral"
            })

        return {

            "success": True,

            "total_reviews": len(formatted),

            "reviews": formatted
        }

    except Exception as e:

        logger.error(
            f"❌ GET REVIEWS FAILED => {e}"
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )
