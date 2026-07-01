from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from datetime import date as date_obj, datetime
import logging

logger = logging.getLogger(__name__)
api_router = APIRouter()

class TokenModel(BaseModel):
    token: str

class NotifyModel(BaseModel):
    items: list

@api_router.post("/notifications/token")
async def register_token(request: Request, data: TokenModel):
    try:
        db = request.app.mongodb
        collection = db["devices"]
        # Upsert the token to avoid duplicates
        await collection.update_one(
            {"token": data.token},
            {"$set": {"token": data.token, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        return {"status": "success", "message": "Token registered"}
    except Exception as e:
        logger.error(f"Error registering device token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error registering device token: {str(e)}"
        )

@api_router.post("/internal/notify")
async def trigger_notifications(request: Request, data: NotifyModel):
    try:
        db = request.app.mongodb
        from services.notification_service import notify_price_changes
        # Await dispatching notifications
        await notify_price_changes(db, data.items)
        return {"status": "triggered"}
    except Exception as e:
        logger.error(f"Error sending FCM notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notification dispatch failed: {str(e)}"
        )
@api_router.post("/internal/broadcast")
async def trigger_broadcast(request: Request, data: NotifyModel):
    """
    Called by the scraper after saving new data.
    Broadcasts a WebSocket event to all connected dashboard clients.
    """
    try:
        from services.websocket_manager import manager
        await manager.broadcast_scraper_update(data.items)
        return {"status": "broadcasted", "count": len(data.items)}
    except Exception as e:
        logger.error(f"Error broadcasting websocket update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Websocket broadcast failed: {str(e)}"
        )

@api_router.get("/prices")
async def get_prices(
    request: Request, 
    category: str = None, 
    district: str = None, 
    city: str = None, 
    date: str = None,
    commodity: str = None
):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        
        query = {}
        if category: query["category"] = {"$regex": category, "$options": "i"}
        if date: query["date_scraped"] = date
        if commodity: query["commodity_name"] = {"$regex": commodity, "$options": "i"}
        if city: query["market_name"] = {"$regex": city, "$options": "i"}
        
        if district and not city:
            query["$or"] = [
                {"district": {"$regex": district, "$options": "i"}},
                {"market_name": {"$regex": district, "$options": "i"}}
            ]
        elif district and city:
            query["district"] = {"$regex": district, "$options": "i"}
            
        cursor = collection.find(query, {"_id": 0}).sort("date_scraped", -1).limit(1000)
        filtered = await cursor.to_list(length=1000)
        
        if not filtered:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price records found matching the requested filters."
            )
            
        return {"status": "success", "data": filtered}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_prices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data retrieval failed: {str(e)}"
        )

@api_router.get("/prices/latest")
async def get_latest_prices(request: Request):
    """
    Fetches the latest prices per commodity and market directly from MongoDB.
    """
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        
        pipeline = [
            {"$sort": {"date_scraped": -1}},
            {
                "$group": {
                    "_id": {
                        "commodity_name": "$commodity_name",
                        "market_name": "$market_name"
                    },
                    "latest_record": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$latest_record"}},
            {"$project": {"_id": 0}},
            {"$sort": {"date_scraped": -1}}
        ]
        
        cursor = collection.aggregate(pipeline)
        results = await cursor.to_list(length=2000)
        
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Error in get_latest_prices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data retrieval failed: {str(e)}"
        )

@api_router.get("/districts")
async def get_districts(request: Request):
    """
    Returns a unique list of all districts (markets) discovered in MongoDB.
    """
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        districts = await collection.distinct("district")
        if not districts:
            districts = await collection.distinct("market_name")
        districts = [d for d in districts if d]
        return {"status": "success", "data": sorted(districts)}
    except Exception as e:
        logger.error(f"Error fetching districts: {e}")
        return {"status": "error", "data": []}

@api_router.get("/districts/today")
async def get_districts_today(request: Request, date: str = None):
    """
    Returns unique districts updated on a specific date from MongoDB.
    """
    if not date:
        date = date_obj.today().isoformat()
        
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        districts = await collection.distinct("district", {"date_scraped": date})
        districts = [d for d in districts if d]
                    
        return {
            "status": "success", 
            "date": date,
            "count": len(districts),
            "data": sorted(districts)
        }
    except Exception as e:
        logger.error(f"Error fetching today's districts: {e}")
        return {"status": "error", "data": []}

@api_router.get("/categories")
async def get_categories(request: Request):
    """
    Returns a unique list of all categories discovered in MongoDB.
    """
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        categories = await collection.distinct("category")
        categories = [c for c in categories if c]
        return {"status": "success", "data": sorted(categories)}
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return {"status": "error", "data": []}

@api_router.get("/scraper/status")
async def get_scraper_status(request: Request):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        today = date_obj.today().isoformat()
        
        districts_today = await collection.distinct("district", {"date_scraped": today})
        total_today = await collection.count_documents({"date_scraped": today})
        
        # Get the latest scraped_at timestamp from today's records
        latest_doc = await collection.find_one(
            {"date_scraped": today},
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/cities")
async def get_cities(request: Request, district: str = None):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        query = {}
        if district:
            query["district"] = {"$regex": district, "$options": "i"}
        cities = await collection.distinct("market_name", query)
        if not cities:
            raise HTTPException(status_code=404, detail="No markets/cities found.")
        return {"status": "success", "data": sorted(cities)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/markets")
async def get_markets(request: Request, district: str = None):
    """
    Returns specific markets mapped to a given district. 
    """
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        query = {}
        if district:
            query["district"] = {"$regex": district, "$options": "i"}
        markets = await collection.distinct("market_name", query)
        markets = [m for m in markets if m]
        return {"status": "success", "data": sorted(markets)}
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return {"status": "error", "data": []}
