import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "data/app.db")
ADMIN_USER_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()]
APP_URL = os.getenv("APP_URL", "")
SOCIAL_TELEGRAM_URL = os.getenv("SOCIAL_TELEGRAM_URL", "")
SOCIAL_INSTAGRAM_URL = os.getenv("SOCIAL_INSTAGRAM_URL", "")
SOCIAL_YOUTUBE_URL = os.getenv("SOCIAL_YOUTUBE_URL", "")
SOCIAL_LINKEDIN_URL = os.getenv("SOCIAL_LINKEDIN_URL", "")
WEBSITE_URL = os.getenv("WEBSITE_URL", "")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/rishehsupport")
