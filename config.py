from os import environ

DATABASE_URL = environ.get("DATABASE_URL", "sqlite://moodle_notif_bot.db")  # Database connection url
BASE_URL = environ.get("BASE_URL", "")  # Moodle base url with schema, like "https://moodle.example.com"
USERS_LIMIT_PER_TG_USER = 10  # How many moodle users can one telegram user add

API_ID = int(environ.get("API_ID", 0))  # Telegram api id
API_HASH = environ.get("API_HASH", "")  # Telegram api hash
BOT_TOKEN = environ.get("BOT_TOKEN", "")  # Telegram bot token
