import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found! Please set it in .env file or Railway environment variables.")

# Google Sheets
GOOGLE_SHEETS_KEY = os.getenv("GOOGLE_SHEETS_KEY")
if not GOOGLE_SHEETS_KEY:
    raise ValueError("No GOOGLE_SHEETS_KEY found!")
