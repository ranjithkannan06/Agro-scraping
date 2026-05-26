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
        # Support queries utilizing DB indexed fields
        if commodity:
            query["commodity_name"] = {"$regex": commodity, "$options": "i"}
        if date:
            query["date_scraped"] = date
            
        # Support filters
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        if district:
            query["district"] = {"$regex": district, "$options": "i"}
        if city:
            query["market_name"] = {"$regex": city, "$options": "i"}
            
        prices = await collection.find(query).sort("date_scraped", -1).to_list(1000)
        
        if not prices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price records found matching the requested filters."
            )
            
        # Format for JSON serialization
        for p in prices:
            p["_id"] = str(p["_id"])
            if "scraped_at" in p:
                p["scraped_at"] = p["scraped_at"].isoformat() + "Z"
                
        return {"status": "success", "data": prices}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error in get_prices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

@api_router.get("/prices/latest")
async def get_latest_prices(request: Request):
    """
    Fetches the latest prices per commodity and market using an aggregation pipeline.
    Ensures that the dashboard displays the most up-to-date information on load.
    """
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        
        # Aggregation pipeline to select the absolute latest entry per commodity and market
        pipeline = [
            {"$sort": {"date_scraped": -1, "scraped_at": -1}},
            {
                "$group": {
                    "_id": {
                        "commodity_name": "$commodity_name",
                        "market_name": "$market_name"
                    },
                    "doc": {"$first": "$$ROOT"}
                }
            },
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"commodity_name": 1, "market_name": 1}}
        ]
        
        latest_prices = await collection.aggregate(pipeline).to_list(1000)
        
        if not latest_prices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price records found in the database. Please run the scraper."
            )
            
        # Format for JSON serialization
        for p in latest_prices:
            p["_id"] = str(p["_id"])
            if "scraped_at" in p:
                p["scraped_at"] = p["scraped_at"].isoformat() + "Z"
                
        return {"status": "success", "data": latest_prices}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error in get_latest_prices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

@api_router.get("/categories")
async def get_categories(request: Request):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        categories = await collection.distinct("category")
        if not categories:
            raise HTTPException(status_code=404, detail="No categories found.")
        return {"status": "success", "data": categories}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/districts")
async def get_districts(request: Request):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        districts = await collection.distinct("district")
        if not districts:
            raise HTTPException(status_code=404, detail="No districts found.")
        return {"status": "success", "data": districts}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/districts/today")
async def get_districts_today(request: Request, date: str = None):
    try:
        db = request.app.mongodb
        collection = db["market_prices"]
        # Default to today's date if not provided
        target_date = date if date else date_obj.today().isoformat()
        districts = await collection.distinct("district", {"date_scraped": target_date})
        districts_sorted = sorted([d for d in districts if d])
        
        if not districts_sorted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No districts scraped yet on {target_date}."
            )
            
        logger.info(f"Districts available for {target_date}: {len(districts_sorted)} found")
        return {
            "status": "success",
            "date": target_date,
            "count": len(districts_sorted),
            "data": districts_sorted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        return {"status": "success", "data": cities}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
