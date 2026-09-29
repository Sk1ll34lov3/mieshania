import os, logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mieshania")
moderation_log = logging.getLogger("mieshania.moderation")

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
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_CHAT_TIMEOUT = int(os.getenv("OPENAI_CHAT_TIMEOUT", "30"))
CHATTER_DEFAULT_INTENSITY = int(os.getenv("CHATTER_DEFAULT_INTENSITY", "10"))

# Cobalt API
COBALT_ENABLED    = os.getenv("COBALT_ENABLED", "0") == "1"
COBALT_API_URL    = os.getenv("COBALT_API_URL", "https://api.cobalt.tools/")
COBALT_TIMEOUT    = int(os.getenv("COBALT_TIMEOUT", "25"))
COBALT_MAX_FILE_MB = int(os.getenv("COBALT_MAX_FILE_MB", "49"))
COBALT_AUTH       = os.getenv("COBALT_AUTH")

# Instagram (instagrapi)
IG_USERNAME     = os.getenv("IG_USERNAME", "")
IG_PASSWORD     = os.getenv("IG_PASSWORD", "")
IG_SESSION_FILE = os.getenv("IG_SESSION_FILE", "ig_session.json")

# Telegram forum routing
LSK_FORUM_CHAT_ID = int(os.getenv("LSK_FORUM_CHAT_ID", "-1001594062218"))
LSK_MEMES_THREAD_ID = int(os.getenv("LSK_MEMES_THREAD_ID", "309709")) or None
