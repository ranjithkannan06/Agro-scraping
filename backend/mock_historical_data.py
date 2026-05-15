import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import random

async def main():
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient("mongodb://mongodb:27017")
    db = client["harvesthub"]
    collection = db["market_prices"]
    
    # Get today's date
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch today's data
    todays_data = await collection.find({"date": today_str}).to_list(100)
    
    if not todays_data:
        print(f"No data found for {today_str}. Please wait for the scraper to run first.")
        return
        
    print(f"Found {len(todays_data)} records for today. Generating historical data for the past 7 days...")
    
    historical_records = []
    
    # Generate data for the past 7 days
    for i in range(1, 8):
        past_date = datetime.now() - timedelta(days=i)
        past_date_str = past_date.strftime("%Y-%m-%d")
        
        for item in todays_data:
            # Create a new record based on today's item
            new_item = item.copy()
            
            # Remove the existing _id so MongoDB generates a new one
            if "_id" in new_item:
                del new_item["_id"]
                
            # Update the date
            new_item["date"] = past_date_str
            
            # Tweak the price slightly (fluctuate by up to +/- 15%)
            try:
                current_price = float(item.get("price", 0))
                fluctuation = current_price * random.uniform(-0.15, 0.15)
                new_price = max(1, round(current_price + fluctuation))
                new_item["price"] = str(new_price)
                
                # Update raw data string representation of price if needed
                if "raw_data" in new_item and len(new_item["raw_data"]) > 3:
                    new_item["raw_data"][3] = f"Rs. {new_price}"
            except ValueError:
                pass # Price might not be a valid number, keep as is
                
            historical_records.append(new_item)
            
    # Insert the historical data
    if historical_records:
        result = await collection.insert_many(historical_records)
        print(f"Successfully inserted {len(result.inserted_ids)} historical records for the past 7 days!")
    else:
        print("No historical records generated.")

if __name__ == "__main__":
    asyncio.run(main())
