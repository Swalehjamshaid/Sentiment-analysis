from fastapi import APIRouter

router = APIRouter(
    prefix="/api/reviews",
    tags=["Reviews"]
)

@router.get("/test-sync")
async def test_sync():

    return {
        "success": True,
        "message": "SYNC ROUTE WORKING"
    }

@router.post("/sync/{company_id}")
async def sync_reviews(company_id: int):

    return {
        "success": True,
        "company_id": company_id
    }

@router.get("/company/{company_id}")
async def get_company_reviews(company_id: int):

    return {
        "success": True,
        "company_id": company_id
    }
