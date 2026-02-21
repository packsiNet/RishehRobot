import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "data/app.db")
ADMIN_USER_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()]
APP_URL = os.getenv("APP_URL", "https://t.me/rishehbot")
SOCIAL_TELEGRAM_URL = os.getenv("SOCIAL_TELEGRAM_URL", "https://t.me/rishehapp")
SOCIAL_INSTAGRAM_URL = os.getenv("SOCIAL_INSTAGRAM_URL", "https://instagram.com/risheh.life")
SOCIAL_YOUTUBE_URL = os.getenv("SOCIAL_YOUTUBE_URL", "https://youtube.com/@risheh")
SOCIAL_LINKEDIN_URL = os.getenv("SOCIAL_LINKEDIN_URL", "https://www.linkedin.com/company/rishehstory")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://risheh.net")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/rishehsupport")
