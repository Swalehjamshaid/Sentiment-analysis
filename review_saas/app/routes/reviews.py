# =========================================================
# FILE: review_saas/app/routes/reviews.py
# =========================================================

from fastapi import (
    APIRouter,
    HTTPException,
    Query
)

from typing import Optional
from datetime import datetime

# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/api/reviews",
    tags=["Reviews"]
)

# =========================================================
# TEMPORARY IN-MEMORY STORAGE
# =========================================================

FAKE_REVIEWS_DB = []

# =========================================================
# TEST ROUTE
# =========================================================

@router.get("/test-sync")
async def test_sync():

    return {

        "success": True,

        "message": "TEST ROUTE WORKING",

        "timestamp": datetime.utcnow()
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

    rating: Optional[int] = None,

    sentiment: Optional[str] = None
):

    try:

        company_reviews = [

            review for review in FAKE_REVIEWS_DB

            if review["company_id"] == company_id
        ]

        # =============================================
        # FILTER BY RATING
        # =============================================

        if rating is not None:

            company_reviews = [

                review for review in company_reviews

                if review["rating"] == rating
            ]

        # =============================================
        # FILTER BY SENTIMENT
        # =============================================

        if sentiment:

            company_reviews = [

                review for review in company_reviews

                if review["sentiment"].lower()
                == sentiment.lower()
            ]

        total_reviews = len(company_reviews)

        reviews = company_reviews[
            skip: skip + limit
        ]

        return {

            "success": True,

            "company_id": company_id,

            "total_reviews": total_reviews,

            "reviews": reviews
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# SYNC REVIEWS
# =========================================================

@router.post("/sync/{company_id}")
@router.post("/sync/{company_id}/")
async def sync_reviews(company_id: int):

    try:

        # =============================================
        # FAKE SCRAPED REVIEWS
        # =============================================

        new_reviews = [

            {

                "id": 1,

                "company_id": company_id,

                "author": "John Smith",

                "rating": 5,

                "review_text":
                    "Amazing customer service and fast delivery.",

                "sentiment": "positive",

                "source": "Google",

                "review_date":
                    datetime.utcnow().isoformat(),

                "created_at":
                    datetime.utcnow().isoformat()
            },

            {

                "id": 2,

                "company_id": company_id,

                "author": "Emma Johnson",

                "rating": 2,

                "review_text":
                    "Delivery was delayed and support was slow.",

                "sentiment": "negative",

                "source": "Google",

                "review_date":
                    datetime.utcnow().isoformat(),

                "created_at":
                    datetime.utcnow().isoformat()
            }
        ]

        inserted_reviews = 0

        for review in new_reviews:

            already_exists = any(

                existing["review_text"]
                == review["review_text"]

                and

                existing["company_id"]
                == company_id

                for existing in FAKE_REVIEWS_DB
            )

            if not already_exists:

                FAKE_REVIEWS_DB.append(review)

                inserted_reviews += 1

        return {

            "success": True,

            "message": "POST ROUTE WORKING",

            "company_id": company_id,

            "inserted_reviews": inserted_reviews,

            "total_reviews":
                len(FAKE_REVIEWS_DB),

            "reviews": new_reviews
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# REVIEW ANALYTICS
# =========================================================

@router.get("/analytics/{company_id}")
async def review_analytics(company_id: int):

    try:

        reviews = [

            review for review in FAKE_REVIEWS_DB

            if review["company_id"] == company_id
        ]

        if not reviews:

            return {

                "success": True,

                "company_id": company_id,

                "total_reviews": 0,

                "average_rating": 0,

                "positive_reviews": 0,

                "negative_reviews": 0,

                "neutral_reviews": 0
            }

        total_reviews = len(reviews)

        average_rating = round(

            sum(
                review["rating"]
                for review in reviews
            ) / total_reviews,

            2
        )

        positive_reviews = len([

            review for review in reviews

            if review["sentiment"] == "positive"
        ])

        negative_reviews = len([

            review for review in reviews

            if review["sentiment"] == "negative"
        ])

        neutral_reviews = len([

            review for review in reviews

            if review["sentiment"] == "neutral"
        ])

        return {

            "success": True,

            "company_id": company_id,

            "total_reviews": total_reviews,

            "average_rating": average_rating,

            "positive_reviews": positive_reviews,

            "negative_reviews": negative_reviews,

            "neutral_reviews": neutral_reviews
        }

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# DELETE REVIEW
# =========================================================

@router.delete("/delete/{review_id}")
async def delete_review(review_id: int):

    try:

        global FAKE_REVIEWS_DB

        initial_count = len(FAKE_REVIEWS_DB)

        FAKE_REVIEWS_DB = [

            review for review in FAKE_REVIEWS_DB

            if review["id"] != review_id
        ]

        if len(FAKE_REVIEWS_DB) == initial_count:

            raise HTTPException(

                status_code=404,

                detail="Review not found"
            )

        return {

            "success": True,

            "message": "Review deleted",

            "review_id": review_id
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )

# =========================================================
# HEALTH CHECK
# =========================================================

@router.get("/health")
async def reviews_health():

    return {

        "success": True,

        "service": "reviews",

        "status": "healthy",

        "total_reviews":
            len(FAKE_REVIEWS_DB),

        "timestamp":
            datetime.utcnow().isoformat()
    }

# =========================================================
# END OF FILE
# =========================================================
