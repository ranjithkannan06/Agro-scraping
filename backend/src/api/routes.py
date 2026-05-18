from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import date as date_obj
import logging

logger = logging.getLogger(__name__)
api_router = APIRouter()

class TokenModel(BaseModel):
    token: str

@api_router.post("/notifications/token")
async def register_token(request: Request, data: TokenModel):
    db = request.app.mongodb
    collection = db["devices"]
    # Upsert the token to avoid duplicates
    await collection.update_one(
        {"token": data.token},
        {"$set": {"token": data.token}},
        upsert=True
    )
    return {"status": "success", "message": "Token registered"}

class NotifyModel(BaseModel):
    items: list

@api_router.post("/internal/notify")
async def trigger_notifications(request: Request, data: NotifyModel):
    db = request.app.mongodb
    from services.notification_service import notify_price_changes
    # Background task or direct await
    await notify_price_changes(db, data.items)
    return {"status": "triggered"}

@api_router.post("/internal/broadcast")
async def trigger_broadcast(request: Request, data: NotifyModel):
    """
    Called by the scraper after saving new data.
    Broadcasts a WebSocket event to all connected dashboard clients with district metadata.
    """
    from services.websocket_manager import manager
    await manager.broadcast_scraper_update(data.items)
    return {"status": "broadcasted", "count": len(data.items)}

@api_router.get("/prices")
async def get_prices(request: Request, category: str = None, district: str = None, city: str = None, date: str = None):
    # Fetch from MongoDB
    db = request.app.mongodb
    collection = db["market_prices"]
    
    query = {}
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    if district:
        query["district"] = {"$regex": district, "$options": "i"}
    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if date:
        query["date"] = date
        
    prices = await collection.find(query).sort("scraped_at", -1).to_list(100)
    
    # Format for JSON serialization
    for p in prices:
        p["_id"] = str(p["_id"])
        if "scraped_at" in p:
            p["scraped_at"] = p["scraped_at"].isoformat()
            
    return {"status": "success", "data": prices}
    
@api_router.get("/categories")
async def get_categories(request: Request):
    db = request.app.mongodb
    collection = db["market_prices"]
    categories = await collection.distinct("category")
    return {"status": "success", "data": categories}

@api_router.get("/districts")
async def get_districts(request: Request):
    db = request.app.mongodb
    collection = db["market_prices"]
    districts = await collection.distinct("district")
    return {"status": "success", "data": districts}

@api_router.get("/districts/today")
async def get_districts_today(request: Request, date: str = None):
    """
    Returns only the districts that have scraped data for today (or a given date).
    Used by the web dashboard to dynamically populate the district dropdown.
    """
    db = request.app.mongodb
    collection = db["market_prices"]
    # Default to today's date if not provided
    target_date = date if date else date_obj.today().isoformat()
    districts = await collection.distinct("district", {"date": target_date})
    districts_sorted = sorted([d for d in districts if d])
    logger.info(f"Districts available for {target_date}: {len(districts_sorted)} found")
    return {
        "status": "success",
        "date": target_date,
        "count": len(districts_sorted),
        "data": districts_sorted
    }

@api_router.get("/scraper/status")
async def get_scraper_status(request: Request):
    """
    Returns a summary of today's scraping status: how many districts scraped,
    last scraped time, and total records for today.
    """
    db = request.app.mongodb
    collection = db["market_prices"]
    today = date_obj.today().isoformat()
    
    districts_today = await collection.distinct("district", {"date": today})
    total_today = await collection.count_documents({"date": today})
    
    # Get the latest scraped_at timestamp from today's records
    latest_doc = await collection.find_one(
        {"date": today},
        sort=[("scraped_at", -1)]
    )
    last_updated = None
    if latest_doc and "scraped_at" in latest_doc:
        last_updated = latest_doc["scraped_at"].isoformat()
    
    return {
        "status": "success",
        "date": today,
        "districts_count": len(districts_today),
        "districts": sorted([d for d in districts_today if d]),
        "total_records": total_today,
        "last_updated": last_updated
    }

@api_router.get("/cities")
async def get_cities(request: Request, district: str = None):
    db = request.app.mongodb
    collection = db["market_prices"]
    query = {}
    if district:
        query["district"] = {"$regex": district, "$options": "i"}
    cities = await collection.distinct("city", query)
    return {"status": "success", "data": cities}
