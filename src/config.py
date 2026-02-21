import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
try:
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path.as_posix())
except Exception:
    pass

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

# Mandatory channel membership configuration
MANDATORY_CHANNEL_ID = os.getenv("MANDATORY_CHANNEL_ID", "").strip() if os.getenv("MANDATORY_CHANNEL_ID") else ""
MANDATORY_CHANNEL_USERNAME = os.getenv("MANDATORY_CHANNEL_USERNAME", "").strip() if os.getenv("MANDATORY_CHANNEL_USERNAME") else ""
MANDATORY_CHANNEL_URL = os.getenv("MANDATORY_CHANNEL_URL", "https://t.me/rishehapp").strip()
