import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging

logger = logging.getLogger(__name__)

# The path where the user should place their service account key
SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'firebase-service-account.json')

def init_firebase():
    if os.path.exists(SERVICE_ACCOUNT_PATH):
        try:
            cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized successfully.")
        except ValueError:
            logger.warning("Firebase Admin already initialized.")
        except Exception as e:
            logger.error(f"Error initializing Firebase: {e}")
    else:
        logger.warning(f"Firebase Service Account key not found at {SERVICE_ACCOUNT_PATH}. Push notifications will not work.")

def send_push_notification(token: str, title: str, body: str):
    if not firebase_admin._apps:
        logger.warning("Cannot send notification. Firebase is not initialized.")
        return False
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=token,
        )
        response = messaging.send(message)
        logger.info(f"Successfully sent message: {response}")
        return True
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return False
