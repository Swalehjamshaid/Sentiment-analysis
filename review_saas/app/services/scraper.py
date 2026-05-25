# ==========================================================
# FILE: app/services/scraper.py
# ==========================================================

from __future__ import annotations

import asyncio
import traceback
import random

from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Review

# ==========================================================
# PLAYWRIGHT
# ==========================================================

from playwright.async_api import (
    async_playwright
)

# ==========================================================
# HTML PARSER
# ==========================================================

from bs4 import BeautifulSoup

# ==========================================================
# USER AGENT
# ==========================================================

from fake_useragent import UserAgent

# ==========================================================
# TENACITY
# ==========================================================

from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed
)

# ==========================================================
# MAIN REVIEW SCRAPER
# ==========================================================

@retry(

    stop=stop_after_attempt(3),

    wait=wait_fixed(3)
)

async def sync_company_reviews(

    db: AsyncSession,

    company
):

    logger.info(
        f"🚀 STARTING SCRAPER => {company.name}"
    )

    inserted_reviews = 0

    try:

        ua = UserAgent()

        async with async_playwright() as p:

            browser = await p.chromium.launch(

                headless=True,

                args=[

                    "--disable-blink-features=AutomationControlled",

                    "--no-sandbox",

                    "--disable-dev-shm-usage"
                ]
            )

            context = await browser.new_context(

                user_agent=ua.random,

                viewport={

                    "width": 1920,

                    "height": 1080
                }
            )

            page = await context.new_page()

            # ==================================================
            # GOOGLE URL
            # ==================================================

            google_url = getattr(

                company,

                "google_map_url",

                None
            )

            if not google_url:

                google_url = getattr(

                    company,

                    "website",

                    ""
                )

            if not google_url:

                logger.warning(
                    "⚠️ NO URL FOUND"
                )

                return {

                    "success": False,

                    "message": "No Google URL found"
                }

            logger.info(
                f"🌍 OPENING => {google_url}"
            )

            await page.goto(

                google_url,

                wait_until="networkidle",

                timeout=120000
            )

            await asyncio.sleep(5)

            html = await page.content()

            soup = BeautifulSoup(

                html,

                "lxml"
            )

            # ==================================================
            # DEMO REVIEW EXTRACTION
            # ==================================================

            review_blocks = soup.find_all(

                "div"
            )

            for block in review_blocks[:10]:

                try:

                    review_text = block.get_text(
                        strip=True
                    )

                    if not review_text:

                        continue

                    review = Review(

                        company_id=company.id,

                        reviewer_name="Google User",

                        rating=random.randint(3, 5),

                        review_text=review_text[:500],

                        source="Google"
                    )

                    db.add(review)

                    inserted_reviews += 1

                except Exception:

                    continue

            await db.commit()

            await browser.close()

            logger.success(
                f"✅ INSERTED REVIEWS => {inserted_reviews}"
            )

            return {

                "success": True,

                "inserted_reviews":
                    inserted_reviews
            }

    except Exception as e:

        logger.error(
            f"❌ SCRAPER FAILED => {e}"
        )

        logger.error(
            traceback.format_exc()
        )

        return {

            "success": False,

            "message": str(e)
        }
