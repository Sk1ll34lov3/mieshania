import os, logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mieshania")

BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in .env")

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

ADMINS = [1272917367, 276417908]

# alerts.in.ua
ALERTS_TOKEN = os.getenv("ALERTS_TOKEN")

# GPT
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_JOKES_ON = os.getenv("GPT_JOKES_ON", "0") == "1"
