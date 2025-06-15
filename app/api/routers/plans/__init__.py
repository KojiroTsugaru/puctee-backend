from fastapi import APIRouter
from .main import router as plans_router

router = APIRouter()
router.include_router(plans_router, prefix="/api/plans", tags=["plans"])
