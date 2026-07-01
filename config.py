import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]

SECRET_KEY: str = os.environ["SECRET_KEY"]
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

# Optional bootstrap admin, seeded on startup if no admin exists yet.
ADMIN_USERNAME: str | None = os.getenv("ADMIN_USERNAME") or None
ADMIN_PASSWORD: str | None = os.getenv("ADMIN_PASSWORD") or None
ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")

access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
