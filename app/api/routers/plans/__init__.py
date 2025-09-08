from fastapi import APIRouter
from .main import router as plans_router
from .location_validation import router as location_validation_router

router = APIRouter()
router.include_router(plans_router, tags=["plans"])
router.include_router(location_validation_router, prefix="/location", tags=["location-validation"])
