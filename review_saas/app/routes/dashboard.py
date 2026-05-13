from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Dict, Any
import logging
import statistics
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["dashboard"]
)

# ==========================================================
# SESSION AUTH
# ==========================================================

def get_current_user(request: Request):

    user = request.session.get("user")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    return user

# ==========================================================
# REQUEST MODEL
# ==========================================================

class ChatRequest(BaseModel):
    message: str

# ==========================================================
# SAFE IMPORTS
# ==========================================================

def get_company_service():

    from app.services.company_service import CompanyService

    return CompanyService


def get_review_service():

    try:

        from app.services.review_service import ReviewService

        return ReviewService

    except:

        from app.services.scraper import ReviewService

        return ReviewService


def get_insights_service():

    from app.services.ai_insights_service import AIInsightsService

    return AIInsightsService

# ==========================================================
# UTILITIES
# ==========================================================

def safe_rating(review):

    try:
        return int(review.get("rating", 0))
    except:
        return 0


def calculate_sentiment(avg_rating: float):

    if avg_rating >= 4:
        return "Positive"

    elif avg_rating >= 3:
        return "Neutral"

    return "Negative"

# ==========================================================
# GET COMPANIES
# ==========================================================

@router.get("/companies")
async def get_companies(request: Request):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()

        companies = await CompanyService.get_user_companies(
            user["id"]
        )

        formatted = []

        for company in companies:

            formatted.append({
                "id": company.get("id"),
                "name": company.get("name"),
                "place_id": company.get("google_place_id"),
                "address": company.get("address")
            })

        return {
            "status": "success",
            "companies": formatted
        }

    except Exception as e:

        logger.exception("Companies fetch failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# ADD COMPANY
# ==========================================================

@router.post("/companies")
async def add_company(
    request: Request,
    payload: Dict[str, Any]
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()

        company = await CompanyService.create_company(
            user_id=user["id"],
            name=payload.get("name"),
            place_id=payload.get("place_id"),
            address=payload.get("address")
        )

        return {
            "status": "success",
            "company": company
        }

    except Exception as e:

        logger.exception("Company creation failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# MAIN DASHBOARD
# ==========================================================

@router.get("/dashboard/{company_id}")
async def get_dashboard_data(
    request: Request,
    company_id: int
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()
        ReviewService = get_review_service()

        owns = await CompanyService.user_owns_company(
            user["id"],
            company_id
        )

        if not owns:

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        reviews = await ReviewService.get_latest_reviews(
            company_id,
            500
        )

        reviews = reviews or []

        total_reviews = len(reviews)

        ratings = []

        for review in reviews:

            rating = safe_rating(review)

            if rating > 0:
                ratings.append(rating)

        average_rating = round(
            statistics.mean(ratings),
            2
        ) if ratings else 0

        positive_reviews = len([
            r for r in ratings if r >= 4
        ])

        neutral_reviews = len([
            r for r in ratings if r == 3
        ])

        negative_reviews = len([
            r for r in ratings if r <= 2
        ])

        reputation_score = round(
            (average_rating / 5) * 100,
            2
        ) if average_rating else 0

        sentiment_score = round(
            (positive_reviews / total_reviews) * 100,
            2
        ) if total_reviews else 0

        revenue_risk = round(
            max(0, 100 - reputation_score),
            2
        )

        rating_counter = Counter(ratings)

        rating_distribution = [
            rating_counter.get(5, 0),
            rating_counter.get(4, 0),
            rating_counter.get(3, 0),
            rating_counter.get(2, 0),
            rating_counter.get(1, 0)
        ]

        return {

            "status": "success",

            "company_id": company_id,

            "total_reviews": total_reviews,

            "average_rating": average_rating,

            "positive_reviews": positive_reviews,

            "negative_reviews": negative_reviews,

            "neutral_reviews": neutral_reviews,

            "reputation_score": reputation_score,

            "revenue_risk": revenue_risk,

            "sentiment_score": sentiment_score,

            "customer_sentiment":
                calculate_sentiment(
                    average_rating
                ),

            "rating_distribution":
                rating_distribution,

            "chart_labels": [
                "5 Star",
                "4 Star",
                "3 Star",
                "2 Star",
                "1 Star"
            ],

            "chart_values":
                rating_distribution,

            "last_updated":
                datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise

    except Exception as e:

        logger.exception("Dashboard API failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# GET REVIEWS
# ==========================================================

@router.get("/reviews/company/{company_id}")
async def get_company_reviews(
    request: Request,
    company_id: int,
    limit: int = Query(100, le=500)
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()
        ReviewService = get_review_service()

        owns = await CompanyService.user_owns_company(
            user["id"],
            company_id
        )

        if not owns:

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        reviews = await ReviewService.get_latest_reviews(
            company_id,
            limit
        )

        return {
            "status": "success",
            "reviews": reviews
        }

    except Exception as e:

        logger.exception("Review fetch failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# INGEST REVIEWS
# ==========================================================

@router.post("/reviews/ingest/{company_id}")
async def ingest_reviews(
    request: Request,
    company_id: int
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()
        ReviewService = get_review_service()

        owns = await CompanyService.user_owns_company(
            user["id"],
            company_id
        )

        if not owns:

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        result = await ReviewService.ingest_from_google(
            company_id
        )

        return {
            "status": "success",
            "reviews_collected":
                result.get(
                    "ingested_count",
                    0
                ),
            "synced_at":
                datetime.utcnow().isoformat()
        }

    except Exception as e:

        logger.exception("Review ingest failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# AI INSIGHTS
# ==========================================================

@router.get("/dashboard/ai-insights/{company_id}")
async def ai_insights(
    request: Request,
    company_id: int
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()
        InsightsService = get_insights_service()

        owns = await CompanyService.user_owns_company(
            user["id"],
            company_id
        )

        if not owns:

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        insights = await InsightsService.generate_insights(
            company_id=company_id,
            start_date=None,
            end_date=None
        )

        return {
            "status": "success",
            "insights": insights
        }

    except Exception as e:

        logger.exception("Insights failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# AI CHAT
# ==========================================================

@router.post("/dashboard/chat/{company_id}")
async def dashboard_ai_chat(
    request: Request,
    company_id: int,
    payload: ChatRequest
):

    user = get_current_user(request)

    try:

        CompanyService = get_company_service()
        ReviewService = get_review_service()

        owns = await CompanyService.user_owns_company(
            user["id"],
            company_id
        )

        if not owns:

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        reviews = await ReviewService.get_latest_reviews(
            company_id,
            100
        )

        ratings = [
            safe_rating(r)
            for r in reviews
            if safe_rating(r) > 0
        ]

        avg_rating = round(
            statistics.mean(ratings),
            2
        ) if ratings else 0

        return {

            "status": "success",

            "chatbot": {

                "question":
                    payload.message,

                "average_rating":
                    avg_rating,

                "customer_sentiment":
                    calculate_sentiment(
                        avg_rating
                    ),

                "business_health_score":
                    round(
                        (avg_rating / 5) * 100,
                        2
                    ),

                "recommendations": [
                    "Reply quickly to negative reviews",
                    "Track repeated complaints",
                    "Improve customer support",
                    "Encourage happy customers to review",
                    "Monitor sentiment weekly"
                ],

                "generated_at":
                    datetime.utcnow().isoformat()
            }
        }

    except Exception as e:

        logger.exception("AI chat failed")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# ==========================================================
# LOGOUT
# ==========================================================

@router.get("/auth/logout")
async def logout(request: Request):

    request.session.clear()

    return {
        "status": "success",
        "message": "Logged out successfully"
    }
