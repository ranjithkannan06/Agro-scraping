import logging
from core.firebase import send_push_notification

logger = logging.getLogger(__name__)

async def notify_price_changes(db, new_items: list):
    """
    Checks if there are devices registered and sends a push notification 
    for the newly updated items.
    """
    if not new_items:
        return
        
    try:
        collection = db["devices"]
        devices = await collection.find({}).to_list(1000)
        if not devices:
            logger.info("No registered devices to notify.")
            return
            
        # Example: Notify about the first updated item or create a summary message
        item = new_items[0]
        title = "Live Market Price Update!"
        body = f"{item.get('commodity', 'Flower')} price is now ₹{item.get('price')} in {item.get('district')}!"
        
        success_count = 0
        for device in devices:
            token = device.get("token")
            if token:
                # If using Expo, we should ideally use Expo Push API, 
                # but if using FCM directly via Expo, the token works with firebase_admin.
                # For this implementation we'll pass it to our FCM wrapper.
                # Note: 'ExponentPushToken[...]' is an Expo token, not FCM. 
                # If they are Expo tokens, we would actually use the exponent_server_sdk python package.
                # For standard Firebase integration as requested by the user, we assume standard FCM tokens 
                # or FCM configured directly in Expo. Let's log it.
                if token.startswith("ExponentPushToken"):
                    logger.warning("Found Expo token instead of FCM. Ensure Firebase is natively configured in Expo.")
                
                if send_push_notification(token, title, body):
                    success_count += 1
                    
        logger.info(f"Sent notifications to {success_count} out of {len(devices)} devices.")
    except Exception as e:
        logger.error(f"Error in notify_price_changes: {e}")
