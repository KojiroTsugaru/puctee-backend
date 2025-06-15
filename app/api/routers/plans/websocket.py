from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
from app.core.auth import get_current_user_ws

router = APIRouter()

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        # Get current user from token
        user = await get_current_user_ws(websocket)
        if not user:
            await websocket.close(code=4001)
            return
        
        # Connect
        await manager.connect(websocket, user.id)
        
        try:
            while True:
                # Keep connection alive
                data = await websocket.receive_text()
                # Echo back for testing
                await websocket.send_text(f"Message received: {data}")
        except WebSocketDisconnect:
            manager.disconnect(websocket, user.id)
    except Exception as e:
        await websocket.close(code=4000) 