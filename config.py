import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))

    SEERR_URL = os.getenv("SEERR_URL")
    SEERR_API_KEY = os.getenv("SEERR_API_KEY")

    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database/discordeerr.db")

    WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 5000))
    WEBHOOK_AUTH_HEADER = os.getenv("WEBHOOK_AUTH_HEADER", "")

    NOTIFICATION_CHANNEL_ID = int(os.getenv("NOTIFICATION_CHANNEL_ID", 0))

    DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
