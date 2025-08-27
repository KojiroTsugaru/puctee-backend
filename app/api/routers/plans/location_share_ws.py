# app/api/routers/plans/location_share_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any
from sqlalchemy import select
from app.core.auth import get_current_user_ws
from app.db.session import AsyncSessionLocal
from app.models import Plan, User
from app.schemas import LocationShareMessage, WebSocketErrorResponse, LocationUpdateRequest
import json

router = APIRouter()

# plan_id -> user_id -> List[WebSocket]
class PlanConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[int, List[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, plan_id: int, user_id: int):
        # accept は外で呼ぶ前提だが、保険でここでも許容
        try:
            await websocket.accept()
        except RuntimeError:
            pass
        self.active_connections.setdefault(plan_id, {}).setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, plan_id: int, user_id: int):
        plan_map = self.active_connections.get(plan_id)
        if not plan_map:
            return
        lst = plan_map.get(user_id)
        if lst and websocket in lst:
            lst.remove(websocket)
            if not lst:
                del plan_map[user_id]
            if not plan_map:
                del self.active_connections[plan_id]

    async def broadcast(self, plan_id: int, message: Any):
        for ws_list in self.active_connections.get(plan_id, {}).values():
            for ws in list(ws_list):
                try:
                    await ws.send_text(message)
                except Exception:
                    # 壊れた接続を掃除
                    try:
                        ws_list.remove(ws)
                    except ValueError:
                        pass

manager = PlanConnectionManager()

@router.websocket("/ws/{plan_id}")
async def plan_location_ws(websocket: WebSocket, plan_id: int):
    print(f"WS connect attempt for plan {plan_id}")
    await websocket.accept()  # まず accept して 101 を返す

    db = AsyncSessionLocal()
    user = None
    try:
        # User authentication
        user = await get_current_user_ws(websocket)
        if not user:
            await websocket.close(code=4401)  # Unauthorized
            await db.close()
            return

        # Check if plan exists and user is a participant (IDベースでチェック)
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = result.scalar_one_or_none()
        if not plan:
            await websocket.close(code=4404)  # Plan not found
            await db.close()
            return

        # participants.any(User.id == user.id) でチェック
        check_q = select(Plan.id).where(
            Plan.id == plan_id,
            Plan.participants.any(User.id == user.id)
        )
        exists = await db.execute(check_q)
        if exists.scalar_one_or_none() is None:
            await websocket.close(code=4403)  # Forbidden
            await db.close()
            return

        await manager.connect(websocket, plan_id, user.id)
        await db.close()

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    # Parse and validate incoming data using Pydantic
                    payload = json.loads(data)
                    location_request = LocationUpdateRequest(**payload)
                    
                    # Create response using Pydantic model
                    location_message = LocationShareMessage(
                        user_id=user.id,
                        display_name=user.display_name,
                        profileImageUrl=user.profile_image_url,
                        latitude=location_request.latitude,
                        longitude=location_request.longitude
                    )
                    
                    # Send as JSON string
                    await manager.broadcast(plan_id, location_message.model_dump_json())
                except Exception as e:
                    # Send structured error response
                    error_response = WebSocketErrorResponse(
                        error="Invalid location data",
                        code="INVALID_DATA"
                    )
                    await websocket.send_text(error_response.model_dump_json())
        except WebSocketDisconnect:
            manager.disconnect(websocket, plan_id, user.id)

    except Exception as e:
        print("WS error:", e)
        # Send structured error response before closing
        try:
            error_response = WebSocketErrorResponse(
                error="Internal server error",
                code="INTERNAL_ERROR"
            )
            await websocket.send_text(error_response.model_dump_json())
        except:
            pass
        await websocket.close(code=1011)  # Internal error
        await db.close()
