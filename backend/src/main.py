import os
import sys

# Dynamically add backend/src to PYTHONPATH for local development imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
import logging

from api.routes import api_router
from core.config import settings
from services.websocket_manager import manager
from core.firebase import init_firebase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_firebase()

app = FastAPI(
    title="HarvestHub API",
    description="Backend API for HarvestHub mobile application",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for mobile app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.mongodb = app.mongodb_client[settings.DATABASE_NAME]
    logger.info("Connected to MongoDB")

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()
    logger.info("Disconnected from MongoDB")

# Include API router
app.include_router(api_router, prefix="/api")

# WebSocket Endpoint for real-time updates
@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Serve the web dashboard at /dashboard dynamically resolving local vs Docker paths
local_dashboard = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web_dashboard", "index.html"))
if os.path.exists(local_dashboard):
    DASHBOARD_PATH = local_dashboard
else:
    DASHBOARD_PATH = "/app/web_dashboard/index.html"

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(DASHBOARD_PATH)

@app.get("/")
async def root():
    return {"message": "Welcome to HarvestHub API — Dashboard at /dashboard"}
