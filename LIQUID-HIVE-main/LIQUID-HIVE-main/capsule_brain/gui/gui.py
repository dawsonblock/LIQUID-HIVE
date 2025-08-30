import asyncio, json, logging
from pathlib import Path
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from ..security.secrets import SecretManager
log = logging.getLogger(__name__)
class AdvancedGUI:
    def __init__(self, engine, app: FastAPI):
        self.engine=engine; self.app=app; self._clients:Set[WebSocket]=set(); self._setup_routes()
    def _setup_routes(self):
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=static_path), name="static")
        @self.app.get("/", include_in_schema=False)
        async def root() -> FileResponse: return FileResponse(static_path / "index.html")
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(None)):
            admin_env = SecretManager.get_secret("ADMIN_API_KEY")
            if admin_env and token != admin_env: await websocket.close(code=4003, reason="Invalid authentication token"); return
            await websocket.accept(); self._clients.add(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    if self.engine.bus: await self.engine.bus.put({"type":"user_chat_message","payload":{"text": data}})
            except WebSocketDisconnect:
                self._clients.discard(websocket)
            except Exception as e:
                log.error(f"WebSocket error: {e}"); self._clients.discard(websocket)
    async def broadcast(self, message: dict):
        if not self._clients: return
        dead=set(); msg=json.dumps(message)
        for c in self._clients:
            try: await c.send_text(msg)
            except Exception: dead.add(c)
        self._clients -= dead
    async def run_broadcasters(self):
        if not self.engine.bus: return
        while True:
            try:
                message = await self.engine.bus.get(); await self.broadcast(message)
            except Exception as e:
                log.error(f"GUI broadcaster error: {e}"); await asyncio.sleep(1)
