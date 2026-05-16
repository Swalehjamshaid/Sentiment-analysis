# filename: app/routes/reports.py

from **future** import annotations

import os
import logging
from typing import Any, Dict

from fastapi import (
APIRouter,
Request,
Depends,
HTTPException,
status,
)

from fastapi.responses import (
FileResponse,
JSONResponse,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

from app.services.report_service import ReportService
from app.services.analytics_service import analytics_service
from app.services.ai_insight_service import ai_insight_service

logger = logging.getLogger("app.reports")

router = APIRouter(
prefix="/api/reports",
tags=["reports"]
)

# ==========================================================

# SERVICES

# ==========================================================

report_service = ReportService()

# ==========================================================

# AUTH CHECK

# ==========================================================

def require_user(request: Request):

```
user_id = request.session.get("user_id")

if not user_id:

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized"
    )

return user_id
```

# ==========================================================

# GENERATE EXECUTIVE PDF REPORT

# ==========================================================

@router.get("/{company_id}/download")
async def generate_report(
company_id: int,
request: Request,
session: AsyncSession = Depends(get_db),
):

```
require_user(request)

try:

    pdf_path = await report_service.generate_executive_report(
        session=session,
        company_id=company_id,
    )

    if not os.path.exists(pdf_path):

        raise HTTPException(
            status_code=404,
            detail="PDF report not found"
        )

    logger.info(
        "✅ Executive report generated for company_id=%s",
        company_id
    )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=os.path.basename(pdf_path)
    )

except HTTPException:
    raise

except Exception as e:

    logger.exception(
        "❌ Failed to generate executive report"
    )

    raise HTTPException(
        status_code=500,
        detail=f"Failed to generate report: {str(e)}"
    )
```

# ==========================================================

# GET ANALYTICS DATA

# ==========================================================

@router.get("/{company_id}/analytics")
async def get_analytics(
company_id: int,
request: Request,
session: AsyncSession = Depends(get_db),
):

```
require_user(request)

try:

    from app.core.models import (
        Company,
        Review,
    )

    # ==================================================
    # GET COMPANY
    # ==================================================

    company_result = await session.execute(
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

    # ==================================================
    # GET REVIEWS
    # ==================================================

    review_result = await session.execute(
        select(Review).where(
            Review.company_id == company_id
        )
    )

    reviews = review_result.scalars().all()

    formatted_reviews = []

    for review in reviews:

        formatted_reviews.append({
            "rating": float(review.rating or 0),
            "review_text": review.review_text or "",
            "sentiment": review.sentiment or "neutral",
            "date": (
                review.created_at.strftime("%Y-%m-%d")
                if review.created_at
                else None
            )
        })

    # ==================================================
    # GENERATE ANALYTICS
    # ==================================================

    analytics_data = analytics_service.generate_complete_analytics(
        company_name=company.name,
        reviews=formatted_reviews,
    )

    # ==================================================
    # GENERATE AI INSIGHTS
    # ==================================================

    ai_insights = ai_insight_service.generate_ai_insights(
        company_name=company.name,
        analytics_data=analytics_data,
    )

    logger.info(
        "✅ Analytics generated for company_id=%s",
        company_id
    )

    return JSONResponse({

        "status": "success",

        "company": {
            "id": company.id,
            "name": company.name,
            "address": company.address,
        },

        "analytics": analytics_data,

        "ai_insights": ai_insights,
    })

except HTTPException:
    raise

except Exception as e:

    logger.exception(
        "❌ Failed to generate analytics"
    )

    raise HTTPException(
        status_code=500,
        detail=f"Analytics generation failed: {str(e)}"
    )
```

# ==========================================================

# QUICK BUSINESS HEALTH API

# ==========================================================

@router.get("/{company_id}/health")
async def business_health(
company_id: int,
request: Request,
session: AsyncSession = Depends(get_db),
):

```
require_user(request)

try:

    from app.core.models import (
        Company,
        Review,
    )

    company_result = await session.execute(
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

    review_result = await session.execute(
        select(Review).where(
            Review.company_id == company_id
        )
    )

    reviews = review_result.scalars().all()

    formatted_reviews = []

    for review in reviews:

        formatted_reviews.append({
            "rating": float(review.rating or 0),
            "review_text": review.review_text or "",
            "sentiment": review.sentiment or "neutral",
            "date": (
                review.created_at.strftime("%Y-%m-%d")
                if review.created_at
                else None
            )
        })

    analytics_data = analytics_service.generate_complete_analytics(
        company_name=company.name,
        reviews=formatted_reviews,
    )

    return {
        "status": "success",
        "company": company.name,
        "business_health_score": analytics_data.get(
            "business_health_score",
            0
        ),
        "risk_level": analytics_data.get(
            "business_risk_level",
            "Unknown"
        ),
        "average_rating": analytics_data.get(
            "average_rating",
            0
        ),
        "customer_satisfaction_score": analytics_data.get(
            "customer_satisfaction_score",
            0
        )
    }

except HTTPException:
    raise

except Exception as e:

    logger.exception(
        "❌ Failed to generate business health"
    )

    raise HTTPException(
        status_code=500,
        detail=str(e)
    )
```
