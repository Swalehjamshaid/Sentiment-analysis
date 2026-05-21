# ==========================================================
# FILE: app/routes/auth.py
# TRUSTLYTICS AI — FINAL STABLE AUTH ROUTE
# MAY 2026 ENTERPRISE VERSION
# ==========================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ==========================================================
# DATABASE
# ==========================================================

from app.core.db import get_db

# ==========================================================
# MODELS
# ==========================================================

from app.core.models import User

# ==========================================================
# SECURITY
# ==========================================================

from app.core.security import (
    get_password_hash,
    create_verification_token,
    decode_verification_token
)

# ==========================================================
# MAILER
# ==========================================================

from app.core.mailer import send_verification_email

# ==========================================================
# ROUTER
# ==========================================================

router = APIRouter(

    prefix="/api/auth",

    tags=["Authentication"]
)

# ==========================================================
# REGISTER USER
# ==========================================================

@router.post(

    "/register",

    status_code=status.HTTP_201_CREATED
)

async def register_user(

    name: str,

    email: str,

    password: str,

    db: AsyncSession = Depends(get_db)
):

    """
    USER REGISTRATION
    SEND EMAIL VERIFICATION
    """

    # ======================================================
    # CHECK EXISTING USER
    # ======================================================

    result = await db.execute(

        select(User).where(
            User.email == email
        )

    )

    existing_user = result.scalars().first()

    if existing_user:

        raise HTTPException(

            status_code=400,

            detail="Email is already registered."
        )

    # ======================================================
    # CREATE NEW USER
    # ======================================================

    try:

        new_user = User(

            name=name,

            email=email,

            hashed_password=get_password_hash(password),

            # ==================================================
            # FIXED FIELD NAME
            # ==================================================

            is_verified=False,

            is_active=True
        )

        db.add(new_user)

        await db.commit()

        await db.refresh(new_user)

    except Exception as e:

        await db.rollback()

        raise HTTPException(

            status_code=500,

            detail=f"User creation failed: {str(e)}"
        )

    # ======================================================
    # GENERATE EMAIL TOKEN
    # ======================================================

    try:

        token = create_verification_token(
            new_user.email
        )

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=f"Token generation failed: {str(e)}"
        )

    # ======================================================
    # SEND VERIFICATION EMAIL
    # ======================================================

    try:

        await send_verification_email(

            new_user.email,

            token
        )

    except Exception as e:

        print(f"❌ EMAIL SEND FAILED: {e}")

    # ======================================================
    # SUCCESS RESPONSE
    # ======================================================

    return {

        "status": "success",

        "message": "User registered successfully. Please verify your email.",

        "email": new_user.email
    }

# ==========================================================
# VERIFY EMAIL
# ==========================================================

@router.get("/verify")

async def verify_email(

    token: str = Query(...),

    db: AsyncSession = Depends(get_db)
):

    """
    VERIFY EMAIL TOKEN
    """

    # ======================================================
    # DECODE TOKEN
    # ======================================================

    email = decode_verification_token(token)

    if not email:

        raise HTTPException(

            status_code=400,

            detail="Invalid or expired verification token."
        )

    # ======================================================
    # FIND USER
    # ======================================================

    result = await db.execute(

        select(User).where(
            User.email == email
        )

    )

    user = result.scalars().first()

    if not user:

        raise HTTPException(

            status_code=404,

            detail="User not found."
        )

    # ======================================================
    # VERIFY USER
    # ======================================================

    try:

        # ==================================================
        # FIXED FIELD NAME
        # ==================================================

        if not user.is_verified:

            user.is_verified = True

            await db.commit()

    except Exception as e:

        await db.rollback()

        raise HTTPException(

            status_code=500,

            detail=f"Verification update failed: {str(e)}"
        )

    # ======================================================
    # REDIRECT RESPONSE
    # ======================================================

    response = RedirectResponse(

        url="/dashboard",

        status_code=status.HTTP_302_FOUND
    )

    response.set_cookie(

        key="session_user",

        value=user.email,

        httponly=True,

        max_age=3600,

        samesite="lax"
    )

    return response

# ==========================================================
# AUTH HEALTH CHECK
# ==========================================================

@router.get("/health")

async def auth_health():

    return {

        "status": "healthy",

        "service": "auth"
    }
