"""
backend/api/routes/ws.py
WebSocket connections for Real-time Dashboard and Force-Logout.
"""
import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> WebSocket
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: str):
        await ws.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(ws)

    def disconnect(self, ws: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if ws in self.active_connections[user_id]:
                self.active_connections[user_id].remove(ws)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

    async def broadcast(self, message: dict):
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: str = ""):
    # A complete implementation would verify the token here.
    # We will grab the user_id after they send their first init message.
    await websocket.accept()
    user_id = "unknown"
    try:
        data = await websocket.receive_text()
        msg = json.loads(data)
        if msg.get("type") == "init":
            user_id = msg.get("userId", "unknown")
            if user_id not in manager.active_connections:
                manager.active_connections[user_id] = []
            manager.active_connections[user_id].append(websocket)
            await websocket.send_json({"type": "connected", "userId": user_id})
        
        while True:
            await websocket.receive_text() # keep alive
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        manager.disconnect(websocket, user_id)
        print(f"WS Error: {e}")
