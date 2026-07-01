"""Check how many records are in MongoDB and show a sample."""
import asyncio, os, sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

# Replicate the same docker-vs-local URL rewrite that database.py uses
raw_url = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
if not os.path.exists("/.dockerenv") and "mongodb://mongodb:" in raw_url:
    MONGO_URL = raw_url.replace("mongodb://mongodb:", "mongodb://127.0.0.1:")
    print(f"Docker alias detected outside container — rewriting to: {MONGO_URL}")
else:
    MONGO_URL = raw_url

from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    name   = os.getenv("DATABASE_NAME", "harvesthub")
    client = AsyncIOMotorClient(MONGO_URL)
    col    = client[name]["market_prices"]

    count = await col.count_documents({})
    print(f"MongoDB db='{name}', collection='market_prices'")
    print(f"Total records : {count}")

    if count > 0:
        # Show one sample
        doc = await col.find_one({}, {"_id": 0})
        print(f"Sample record : {doc}")
        # Show breakdown by category
        pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}]
        print("\nBreakdown by category:")
        async for row in col.aggregate(pipeline):
            print(f"  {row['_id']:25s} : {row['count']} records")
    else:
        print("No records found. Scraper hasn't saved to DB yet or ran into errors.")

    client.close()

asyncio.run(main())
