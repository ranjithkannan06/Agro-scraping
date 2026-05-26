from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "harvesthub"
    JWT_SECRET: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

import os
# Auto-detect local host vs Docker environments
if not os.path.exists('/.dockerenv') and "mongodb://mongodb:" in settings.MONGODB_URL:
    settings.MONGODB_URL = settings.MONGODB_URL.replace("mongodb://mongodb:", "mongodb://127.0.0.1:")
