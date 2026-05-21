# ==========================================================
# FILE: app/core/mailer.py
# TRUSTLYTICS AI — FINAL STABLE MAILER
# MAY 2026 ENTERPRISE VERSION
# ==========================================================

import os
import resend

from fastapi import HTTPException
from dotenv import load_dotenv

# ==========================================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================================

load_dotenv()

# ==========================================================
# RESEND CONFIGURATION
# ==========================================================

RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY"
)

MAIL_FROM = os.getenv(

    "MAIL_FROM",

    "onboarding@resend.dev"
)

BASE_URL = os.getenv(

    "APP_BASE_URL",

    "https://sentiment-analysis-production-f96a.up.railway.app"
)

# ==========================================================
# VALIDATE RESEND API KEY
# ==========================================================

if not RESEND_API_KEY:

    print("⚠️ RESEND_API_KEY NOT FOUND")

else:

    resend.api_key = RESEND_API_KEY

    print("✅ RESEND CONFIGURED")

# ==========================================================
# SEND VERIFICATION EMAIL
# ==========================================================

async def send_verification_email(

    email: str,

    token: str
):

    """
    SEND EMAIL VERIFICATION LINK
    """

    # ======================================================
    # VERIFY URL
    # ======================================================

    verify_url = (

        f"{BASE_URL}/api/auth/verify?token={token}"
    )

    # ======================================================
    # HTML EMAIL TEMPLATE
    # ======================================================

    html_content = f"""

    <!DOCTYPE html>

    <html>

    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f9fafb;">

        <div style="max-width: 600px; margin: auto; background: white; padding: 40px; border-radius: 12px; border: 1px solid #e5e7eb; text-align: center;">

            <h2 style="color: #4f46e5;">

                Trustlytics AI

            </h2>

            <p style="color: #374151; font-size: 16px;">

                Welcome!

                Click the button below to verify your email
                and instantly login to your dashboard.

            </p>

            <div style="margin: 30px 0;">

                <a href="{verify_url}"

                   style="background-color: #4f46e5;
                          color: white;
                          padding: 14px 28px;
                          text-decoration: none;
                          border-radius: 8px;
                          font-weight: bold;
                          display: inline-block;">

                   Verify & Login

                </a>

            </div>

            <p style="color: #6b7280; font-size: 12px;">

                This link will expire in 30 minutes.

                If you did not create an account,
                you can safely ignore this email.

            </p>

        </div>

    </body>

    </html>

    """

    # ======================================================
    # SEND EMAIL
    # ======================================================

    try:

        # ==================================================
        # CHECK RESEND API
        # ==================================================

        if not RESEND_API_KEY:

            raise HTTPException(

                status_code=500,

                detail="RESEND_API_KEY missing."
            )

        # ==================================================
        # SEND EMAIL
        # ==================================================

        response = resend.Emails.send(

            {

                "from":

                    f"Trustlytics AI <{MAIL_FROM}>",

                "to":

                    [email],

                "subject":

                    "Verify Your Email - Trustlytics AI",

                "html":

                    html_content
            }

        )

        print(

            f"✅ VERIFICATION EMAIL SENT TO: {email}"

        )

        print(

            f"📨 RESEND RESPONSE: {response}"

        )

        return True

    except Exception as e:

        print(

            f"❌ RESEND ERROR: {str(e)}"

        )

        raise HTTPException(

            status_code=500,

            detail="Mail service unavailable."
        )

# ==========================================================
# MAIL HEALTH CHECK
# ==========================================================

async def mailer_health_check():

    """
    MAILER HEALTH CHECK
    """

    return {

        "status": "healthy",

        "resend_configured": bool(
            RESEND_API_KEY
        ),

        "mail_from": MAIL_FROM
    }
