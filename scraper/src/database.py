import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.db_name = os.getenv("DATABASE_NAME", "athanur_agro")
        self.client = None
        self.db = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(self.url)
            self.db = self.client[self.db_name]
            logger.info("Connected to MongoDB successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

    async def insert_prices(self, data: list):
        if not data:
            return
            
        try:
            collection = self.db["market_prices"]
            
            # For real-time updates, we also need to notify the backend (e.g. via internal API or direct socket)
            # but for now, we just insert into DB, and backend clients can listen to changes via MongoDB Change Streams 
            # or we can push to a redis channel. Let's just do an upsert to avoid duplicates.
            
            operations = []
            from pymongo import UpdateOne
            
            for item in data:
                # Assuming item has 'commodity', 'market', 'date', 'price'
                # We want to keep track of historical prices, so we can insert new records
                # Or we update the 'latest_price' collection and push to 'price_history' collection.
                
                # Let's insert into history
                item['scraped_at'] = datetime.utcnow()
                operations.append(
                    UpdateOne(
                        {
                            "commodity": item.get("commodity"),
                            "market": item.get("market"),
                            "date": item.get("date")
                        },
                        {"$set": item},
                        upsert=True
                    )
                )
            
            if operations:
                result = await collection.bulk_write(operations)
                logger.info(f"Bulk write completed. Upserted: {result.upserted_count}, Modified: {result.modified_count}")
        except Exception as e:
            logger.error(f"Error inserting data into MongoDB: {e}")
