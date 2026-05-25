# ==========================================================
# FILE: app/routes/reviews.py
# FULLY ALIGNED WITH YOUR REAL models.py
# ==========================================================

from datetime import datetime

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

# ==========================================================
# DATABASE
# ==========================================================

from app.database import get_db

# ==========================================================
# MODELS
# ==========================================================

from app.core.models import Company
from app.core.models import Review

# ==========================================================
# SCRAPER
# ==========================================================

from app.scraper import scrape_google_reviews

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(
    prefix="/api/reviews",
    tags=["Reviews"]
)

# ==========================================================
# HEALTH CHECK
# ==========================================================

@router.get("/health")
async def review_health():

    return {

        "success": True,
        "message": "Reviews API Working"

    }

# ==========================================================
# GET COMPANY REVIEWS
# ==========================================================

@router.get("/company/{company_id}")
async def get_company_reviews(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):

    try:

        logger.info(
            f"📥 FETCHING REVIEWS => {company_id}"
        )

        result = await db.execute(

            select(Review)
            .where(Review.company_id == company_id)
            .order_by(Review.created_at.desc())

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

                "sentiment_score":
                    review.sentiment_score,

                "text":
                    review.text,

                "google_review_time":
                    str(review.google_review_time),

                "first_seen_at":
                    str(review.first_seen_at),

                "review_likes":
                    review.review_likes,

                "created_at":
                    str(review.created_at),

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

            })

        logger.success(
            f"✅ TOTAL REVIEWS => {len(response)}"
        )

        return {

            "success": True,

            "company_id": company_id,

            "total_reviews": len(response),

            "reviews": response,

        }

    except Exception as e:

        logger.exception(e)

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )

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
        # GET COMPANY
        # ==================================================

        company_result = await db.execute(

            select(Company)
            .where(Company.id == company_id)

        )

        company = company_result.scalar_one_or_none()

        if not company:

            logger.error(
                f"❌ COMPANY NOT FOUND => {company_id}"
            )

            raise HTTPException(

                status_code=404,

                detail="Company not found"

            )

        # ==================================================
        # GET GOOGLE PLACE ID
        # ==================================================

        google_place_id = getattr(
            company,
            "google_place_id",
            None
        )

        if not google_place_id:

            logger.error(
                "❌ GOOGLE PLACE ID MISSING"
            )

            raise HTTPException(

                status_code=400,

                detail="google_place_id missing"

            )

        logger.info(
            f"📍 GOOGLE PLACE ID => "
            f"{google_place_id}"
        )

        # ==================================================
        # EXISTING REVIEWS
        # ==================================================

        existing_result = await db.execute(

            select(Review.google_review_id)
            .where(Review.company_id == company_id)

        )

        existing_ids = set(
            existing_result.scalars().all()
        )

        logger.info(
            f"📊 EXISTING REVIEWS => "
            f"{len(existing_ids)}"
        )

        # ==================================================
        # SCRAPE GOOGLE REVIEWS
        # ==================================================

        scraped_reviews = await scrape_google_reviews(

            place_id=google_place_id,

            existing_ids=existing_ids,

            target_limit=300,

        )

        logger.success(
            f"✅ SCRAPED REVIEWS => "
            f"{len(scraped_reviews)}"
        )

        # ==================================================
        # INSERT REVIEWS
        # ==================================================

        inserted_reviews = 0

        for item in scraped_reviews:

            try:

                google_review_id = item.get(
                    "google_review_id"
                )

                if not google_review_id:
                    continue

                # ==========================================
                # DUPLICATE CHECK
                # ==========================================

                duplicate_result = await db.execute(

                    select(Review)
                    .where(
                        Review.google_review_id
                        == google_review_id
                    )

                )

                duplicate = (
                    duplicate_result
                    .scalar_one_or_none()
                )

                if duplicate:
                    continue

                # ==========================================
                # CREATE REVIEW
                # ==========================================

                review = Review(

                    company_id=company_id,

                    google_review_id=
                        google_review_id,

                    author_name=item.get(
                        "author_name",
                        "Google User"
                    ),

                    rating=int(
                        item.get("rating", 5)
                    ),

                    sentiment_score=float(
                        item.get(
                            "sentiment_score",
                            0
                        )
                    ),

                    text=item.get(
                        "text",
                        ""
                    ),

                    google_review_time=item.get(
                        "google_review_time",
                        datetime.utcnow()
                    ),

                    review_likes=int(
                        item.get(
                            "review_likes",
                            0
                        )
                    ),

                    issue_category=item.get(
                        "issue_category"
                    ),

                    emotion=item.get(
                        "emotion"
                    ),

                    urgency_score=item.get(
                        "urgency_score"
                    ),

                    ai_summary=item.get(
                        "ai_summary"
                    ),

                    risk_score=item.get(
                        "risk_score"
                    ),

                    topic_cluster=item.get(
                        "topic_cluster"
                    ),

                )

                db.add(review)

                inserted_reviews += 1

            except Exception as insert_error:

                logger.error(
                    f"❌ INSERT FAILED => "
                    f"{insert_error}"
                )

        # ==================================================
        # COMMIT DATABASE
        # ==================================================

        await db.commit()

        logger.success(
            f"✅ INSERTED REVIEWS => "
            f"{inserted_reviews}"
        )

        # ==================================================
        # FINAL RESPONSE
        # ==================================================

        return {

            "success": True,

            "company_id": company_id,

            "scraped_reviews":
                len(scraped_reviews),

            "inserted_reviews":
                inserted_reviews,

            "message":
                "Reviews synced successfully"

        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception(e)

        await db.rollback()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )

# ==========================================================
# DELETE COMPANY REVIEWS
# ==========================================================

@router.delete("/company/{company_id}")
async def delete_company_reviews(
    company_id: int,
    db: AsyncSession = Depends(get_db)
):

    try:

        logger.info(
            f"🗑️ DELETING REVIEWS => {company_id}"
        )

        result = await db.execute(

            select(Review)
            .where(Review.company_id == company_id)

        )

        reviews = result.scalars().all()

        deleted_count = 0

        for review in reviews:

            await db.delete(review)

            deleted_count += 1

        await db.commit()

        logger.success(
            f"✅ DELETED REVIEWS => "
            f"{deleted_count}"
        )

        return {

            "success": True,

            "company_id": company_id,

            "deleted_reviews": deleted_count,

        }

    except Exception as e:

        logger.exception(e)

        await db.rollback()

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )
