from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
import asyncio

from routers import search, watchlist

app = FastAPI(title="Stock Tracker V2 API")

# Include Routers
app.include_router(search.router)
app.include_router(watchlist.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Initialize DB on startup
    try:
        init_db()
    except Exception as e:
        print(f"Warning: DB Init failed (Docker might be starting): {e}")

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Stock Tracker V2 Engine"}

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Placeholder for live stream logic
            await websocket.send_json({"type": "ping", "ts": asyncio.get_event_loop().time()})
            await asyncio.sleep(1)
    except Exception as e:
        print(f"WS Disconnect: {e}")
