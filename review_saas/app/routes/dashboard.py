from fastapi import APIRouter, HTTPException, Query, Body, Request
from pydantic import BaseModel
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# SESSION AUTH HELPER
# ----------------------------------------------------------
def get_current_user(request: Request):

    user = request.session.get("user")

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

    return user

# ----------------------------------------------------------
# LAZY SERVICE LOADING
# ----------------------------------------------------------
def get_service(name: str):

    try:
        if name == "company":
            from app.services.company_service import CompanyService
            return CompanyService

        elif name == "review":
            from app.services.review_service import ReviewService
            return ReviewService

        elif name == "insights":
            from app.services.ai_insights_service import AIInsightsService
            return AIInsightsService

        elif name == "revenue":
            from app.services.revenue_risk_service import RevenueRiskService
            return RevenueRiskService

        elif name == "chat":
            from app.services.chat_service import AIChatService
            return AIChatService

    except Exception as e:

        logger.error(f"Failed to import {name}_service: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"Service {name} not available"
        )

    raise HTTPException(
        status_code=500,
        detail="Unknown service"
    )

# ----------------------------------------------------------
# ROUTER
# ----------------------------------------------------------
router = APIRouter(
    prefix="/api",
    tags=["dashboard"]
)

# ----------------------------------------------------------
# REQUEST MODELS
# ----------------------------------------------------------
class ChatRequest(BaseModel):
    message: str

# ----------------------------------------------------------
# GET COMPANIES
# ----------------------------------------------------------
@router.get("/companies")
async def get_companies(request: Request):

    user = get_current_user(request)

    try:
        CompanyService = get_service("company")

        companies = await CompanyService.get_user_companies(
            user["id"]
        )

        return {
            "companies": companies or []
        }

    except Exception as e:

        logger.exception("Error in get_companies")

        raise HTTPException(
            status_code=500,
            detail="Failed to load companies"
        )

# ----------------------------------------------------------
# ADD COMPANY
# ----------------------------------------------------------
@router.post("/companies")
async def add_company(
    request: Request,
    payload: Dict[str, Any]
):

    user = get_current_user(request)

    if not payload.get("place_id"):

        raise HTTPException(
            status_code=400,
            detail="place_id is required"
        )

    try:

        CompanyService = get_service("company")

        company = await CompanyService.create_company(
            user_id=user["id"],
            name=payload.get("name"),
            place_id=payload.get("place_id"),
            address=payload.get("address")
        )

        return {
            "message": "Business linked successfully",
            "company": company
        }

    except Exception as e:

        logger.exception("Error adding company")

        raise HTTPException(
            status_code=500,
            detail="Failed to add business"
        )

# ----------------------------------------------------------
# AI CHAT
# ----------------------------------------------------------
@router.post("/dashboard/chat")
async def ai_chat(
    request: Request,
    company_id: int = Query(...),
    chat: ChatRequest = Body(...)
):

    user = get_current_user(request)

    try:

        CompanyService = get_service("company")

        if not await CompanyService.user_owns_company(
            user["id"],
            company_id
        ):

            raise HTTPException(
                status_code=403,
                detail="Access denied"
            )

        ChatService = get_service("chat")

        answer = await ChatService.get_response(
            company_id,
            chat.message
        )

        return {
            "answer": answer
        }

    except Exception as e:

        logger.exception("Chat failed")

        raise HTTPException(
            status_code=500,
            detail="AI chat unavailable"
        )

# ----------------------------------------------------------
# LOGOUT
# ----------------------------------------------------------
@router.get("/auth/logout")
async def logout(request: Request):

    request.session.clear()

    return {
        "message": "Logged out"
    }
