# This file implements a real-time location sharing WebSocket endpoint for plan participants.
# Creates a room for each plan at /ws/plan/{plan_id} and shares all participants' location information in real-time.
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any
from app.core.auth import get_current_user_ws
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models import Plan, User
import json

router = APIRouter()

# plan_id -> user_id -> List[WebSocket]
class PlanConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[int, List[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, plan_id: int, user_id: int):
        await websocket.accept()
        if plan_id not in self.active_connections:
            self.active_connections[plan_id] = {}
        if user_id not in self.active_connections[plan_id]:
            self.active_connections[plan_id][user_id] = []
        self.active_connections[plan_id][user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, plan_id: int, user_id: int):
        if plan_id in self.active_connections and user_id in self.active_connections[plan_id]:
            self.active_connections[plan_id][user_id].remove(websocket)
            if not self.active_connections[plan_id][user_id]:
                del self.active_connections[plan_id][user_id]
            if not self.active_connections[plan_id]:
                del self.active_connections[plan_id]

    async def broadcast(self, plan_id: int, message: Any):
        if plan_id in self.active_connections:
            for user_ws_list in self.active_connections[plan_id].values():
                for ws in user_ws_list:
                    await ws.send_text(message)

manager = PlanConnectionManager()

@router.websocket("/ws/plan/{plan_id}")
async def plan_location_ws(websocket: WebSocket, plan_id: int):
    db = AsyncSessionLocal()
    try:
        # User authentication
        user = await get_current_user_ws(websocket)
        if not user:
            await websocket.close(code=4001)
            await db.close()
            return

        # Check if plan exists and user is a participant
        result = await db.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        if not plan or user not in plan.participants:
            await websocket.close(code=4003)
            await db.close()
            return

        await manager.connect(websocket, plan_id, user.id)
        await db.close()

        try:
            while True:
                data = await websocket.receive_text()
                # Validate and broadcast location data
                try:
                    payload = json.loads(data)
                    # Required: latitude, longitude
                    latitude = float(payload["latitude"])
                    longitude = float(payload["longitude"])
                    # Optional: name
                    name = payload.get("name", "")
                    # user_id is assigned by server
                    location_message = json.dumps({
                        "user_id": user.id,
                        "display_name": user.display_name,
                        "profileImageUrl": user.profile_image_url,
                        "latitude": latitude,
                        "longitude": longitude,
                    })
                    await manager.broadcast(plan_id, location_message)
                except Exception:
                    await websocket.send_text(json.dumps({"error": "Invalid location data"}))
        except WebSocketDisconnect:
            manager.disconnect(websocket, plan_id, user.id)
    except Exception:
        await websocket.close(code=4000)
        await db.close() 