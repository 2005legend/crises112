from fastapi import APIRouter, WebSocket
from integrations.websocket_manager import connect

router = APIRouter()

@router.websocket("/ws/incidents")
async def ws(ws: WebSocket):
    await connect(ws)