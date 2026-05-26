import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from pymongo import UpdateOne, IndexModel

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        raw_url = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
        # Auto-detect local host vs Docker environments
        if not os.path.exists('/.dockerenv') and "mongodb://mongodb:" in raw_url:
            self.url = raw_url.replace("mongodb://mongodb:", "mongodb://127.0.0.1:")
            logger.info(f"Local host environment detected. Resolving Docker MongoDB alias to: {self.url}")
        else:
            self.url = raw_url
            
        self.db_name = os.getenv("DATABASE_NAME", "harvesthub")
        self.client = None
        self.db = None

    async def connect(self):
        try:
            self.client = AsyncIOMotorClient(self.url)
            self.db = self.client[self.db_name]
            logger.info("Connected to MongoDB successfully.")
            
            # Setup quality-gate indexes
            await self._ensure_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB or setup indexes: {e}")

    async def _ensure_indexes(self):
        if self.db is None:
            return
        
        try:
            collection = self.db["market_prices"]
            
            # Remove any bad/corrupted records containing nulls in unique index fields
            logger.info("Cleaning invalid/incomplete database entries prior to index setup...")
            await collection.delete_many({
                "$or": [
                    {"commodity_name": None},
                    {"market_name": None},
                    {"date_scraped": None}
                ]
            })
            
            # Group duplicates to find matching tuples and keep the newest one
            logger.info("De-duplicating valid price records to prepare for unique constraint index...")
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "commodity_name": "$commodity_name",
                            "market_name": "$market_name",
                            "date_scraped": "$date_scraped"
                        },
                        "count": {"$sum": 1},
                        "ids": {"$push": "$_id"}
                    }
                },
                {"$match": {"count": {"$gt": 1}}}
            ]
            
            async for dup_group in collection.aggregate(pipeline):
                # Keep the last id (newest record) and delete the earlier ones
                ids_to_delete = dup_group["ids"][:-1]
                if ids_to_delete:
                    logger.info(f"Removing {len(ids_to_delete)} duplicate records for {dup_group['_id']}")
                    await collection.delete_many({"_id": {"$in": ids_to_delete}})
            
            # 1. Unique index on {commodity_name, market_name, date_scraped} to prevent duplicates
            unique_index = IndexModel(
                [("commodity_name", 1), ("market_name", 1), ("date_scraped", 1)],
                unique=True,
                name="unique_crop_price_index"
            )
            
            # 2. Individual indexes for fast query resolution as specified in Quality Gates
            commodity_index = IndexModel([("commodity_name", 1)], name="commodity_name_index")
            date_index = IndexModel([("date_scraped", 1)], name="date_scraped_index")
            
            # Create all indexes safely
            await collection.create_indexes([unique_index, commodity_index, date_index])
            logger.info("MongoDB indexes successfully created/verified.")
        except Exception as e:
            logger.error(f"Error creating database indexes: {e}")

    async def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

    async def insert_prices(self, data: list):
        if not data:
            logger.warning("No data passed to insert_prices.")
            return
            
        try:
            collection = self.db["market_prices"]
            operations = []
            
            for item in data:
                # Ensure all required fields are present to satisfy data completeness
                required_fields = [
                    "commodity_name", "market_name", "price", 
                    "unit", "date_scraped", "source_url"
                ]
                
                # Check for partial records and filter them out
                is_complete = all(item.get(field) is not None for field in required_fields)
                if not is_complete:
                    missing = [field for field in required_fields if item.get(field) is None]
                    logger.warning(f"Filtered out incomplete record: {item}. Missing fields: {missing}")
                    continue
                
                # Enforce clean timestamps
                item['scraped_at'] = datetime.utcnow()
                
                # Formulate bulk UpdateOne operations with upsert=True
                operations.append(
                    UpdateOne(
                        {
                            "commodity_name": item.get("commodity_name"),
                            "market_name": item.get("market_name"),
                            "date_scraped": item.get("date_scraped")
                        },
                        {"$set": item},
                        upsert=True
                    )
                )
            
            if operations:
                result = await collection.bulk_write(operations)
                logger.info(
                    f"Bulk write completed. "
                    f"Upserted: {result.upserted_count}, "
                    f"Modified: {result.modified_count}, "
                    f"Matched: {result.matched_count}"
                )
            else:
                logger.warning("No complete records found to bulk write.")
        except Exception as e:
            logger.error(f"Error inserting data into MongoDB: {e}")
            raise e
