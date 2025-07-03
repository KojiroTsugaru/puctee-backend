# app/api/routers/plans/main.py
from fastapi import APIRouter
from .arrival import router as arrival_router
from .create import router as create_router
from .read import router as read_router
from .update import router as update_router
from .delete import router as delete_router
from .invites import router as invites_router
from .penalties import router as penalties_router
from .locations import router as locations_router
from .location_share_ws import router as location_share_ws_router

router = APIRouter()

# 各ルーターを適切なプレフィックスでマウント
router.include_router(arrival_router, prefix="")
router.include_router(create_router, prefix="")
router.include_router(read_router, prefix="")
router.include_router(update_router, prefix="")
router.include_router(delete_router, prefix="")
router.include_router(invites_router, prefix="")
router.include_router(penalties_router, prefix="")
router.include_router(location_share_ws_router, prefix="")
router.include_router(locations_router, prefix="")