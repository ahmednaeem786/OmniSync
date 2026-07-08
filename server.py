from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import json

app = FastAPI()

clipboard_history = []

class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[SERVER] New WebSocket connection established. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[SERVER] WebSocket connection closed. Total connections: {len(self.active_connections)}")   

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

class ClipData(BaseModel):
    text: str
    device: str

@app.post("/api/clips")
async def recieve_clip(clip: ClipData):
    clipboard_history.append({"text": clip.text, "device": clip.device})
    print(f"[SERVER] Received new clipboard data from {clip.device}: {clip.text}")

    await manager.broadcast(json.dumps({"text": clip.text, "device": clip.device}))

    return {"status": "success"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)