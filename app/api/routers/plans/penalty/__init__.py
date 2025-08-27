from fastapi import APIRouter
from .penalties import router as penalties_router
from .penalty_status import router as penalty_status_router
from .penalty_requests import router as penalty_requests_router

router = APIRouter()

# Include all penalty-related routers
router.include_router(penalties_router, tags=["penalties"])
router.include_router(penalty_status_router, tags=["penalty-status"])
router.include_router(penalty_requests_router, tags=["penalty-requests"])
