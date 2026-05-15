from fastapi import APIRouter, Request
from pydantic import BaseModel

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

@api_router.get("/cities")
async def get_cities(request: Request, district: str = None):
    db = request.app.mongodb
    collection = db["market_prices"]
    query = {}
    if district:
        query["district"] = {"$regex": district, "$options": "i"}
    cities = await collection.distinct("city", query)
    return {"status": "success", "data": cities}
