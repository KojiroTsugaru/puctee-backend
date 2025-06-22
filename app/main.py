from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from mangum import Mangum
from app.api.routers import auth, plans, users, friends, notifications, invite
from app.api.routers.plans import router as plans_router
from app.services.scheduler import plan_scheduler
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):

    # プランスケジューラーを開始
    asyncio.create_task(plan_scheduler.start())

    yield  # ここで API サーバが立ち上がった状態に

    # プランスケジューラーを停止
    await plan_scheduler.stop()

app = FastAPI(
    title="Puctee API",
    description="Puctee Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターの登録
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(friends.router, prefix="/api/friends", tags=["friends"])
app.include_router(plans_router)
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(invite.router, tags=["invite"])

@app.get("/")
async def root():
    return {"message": "Welcome to Puctee API"}