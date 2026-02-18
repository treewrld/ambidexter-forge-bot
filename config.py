# config.py
import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")  # токен из .env
ADMIN_ID = int(os.getenv("ADMIN_ID", "1114403361"))
