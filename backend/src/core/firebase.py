import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging

logger = logging.getLogger(__name__)

# Search for Firebase credential in multiple potential locations (local dev, backend, and Docker Compose)
PATHS_TO_TRY = [
    # 3 levels up: project root (local native development)
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'firebase-service-account.json')),
    # 2 levels up: backend root (Docker deployment or custom mounting)
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'firebase-service-account.json')),
    # Absolute standard Docker/local root paths
    '/app/firebase-service-account.json',
    'firebase-service-account.json'
]

SERVICE_ACCOUNT_PATH = None
for path in PATHS_TO_TRY:
    if os.path.exists(path):
        SERVICE_ACCOUNT_PATH = path
        break

if not SERVICE_ACCOUNT_PATH:
    # Default fallback path
    SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'firebase-service-account.json'))

def init_firebase():
    if SERVICE_ACCOUNT_PATH and os.path.exists(SERVICE_ACCOUNT_PATH):
        try:
            cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)
            logger.info(f"Firebase Admin initialized successfully using key: {SERVICE_ACCOUNT_PATH}")
        except ValueError:
            logger.warning("Firebase Admin already initialized.")
        except Exception as e:
            logger.error(f"Error initializing Firebase: {e}")
    else:
        logger.warning(f"Firebase Service Account key not found in locations checked: {PATHS_TO_TRY}. Push notifications will not work.")

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
