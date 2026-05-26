from fastapi import WebSocket
from typing import List
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected clients."""
        msg_str = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception as e:
                logger.error(f"Error sending message to client: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_scraper_update(self, new_items: list):
        """
        Broadcasts a structured 'scraper_update' event to all dashboard clients.
        Includes the districts that were just scraped and the count of new records.
        """
        if not new_items:
            return
        districts = list({item.get("district") for item in new_items if item.get("district")})
        message = {
            "event": "scraper_update",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "new_records": len(new_items),
            "districts_updated": sorted(districts),
            "districts_count": len(districts),
            "sample_item": {
                "commodity": new_items[0].get("commodity_name", ""),
                "price": new_items[0].get("price_modal", ""),
                "district": new_items[0].get("district", "")
            }
        }
        await self.broadcast(message)
        logger.info(f"Broadcasted scraper update: {len(new_items)} records, {len(districts)} districts")

manager = ConnectionManager()
