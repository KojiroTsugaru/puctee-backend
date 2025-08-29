from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from mangum import Mangum
from app.api.routers import auth, plans, users, friends, notifications, invite
from app.api.routers.plans import router as plans_router
from app.api.routers.plans.location_share_ws import router as websocket_router
from app.services.scheduler import start_scheduler, stop_scheduler
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Start plan scheduler
    start_scheduler()

    yield  # API server is now running

    # Stop plan scheduler
    stop_scheduler()

app = FastAPI(
    title="Puctee API",
    description="Puctee Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict appropriately in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(friends.router, prefix="/api/friends", tags=["friends"])
app.include_router(plans_router, prefix="/api/plans", tags=["plans"])
app.include_router(websocket_router, prefix="/api/plans", tags=["websocket"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(invite.router, tags=["invite"])

@app.get("/")
async def root():
    return {"message": "Welcome to Puctee API"}

@app.get("/health")
def health():
    return {"ok": True}