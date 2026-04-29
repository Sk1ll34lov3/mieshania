import html
import random
from collections import defaultdict, deque
from typing import Deque

import aiohttp
from aiogram.types import Message

from config import CHATTER_DEFAULT_INTENSITY, OPENAI_API_KEY, OPENAI_CHAT_MODEL, OPENAI_CHAT_TIMEOUT, log
from db import db

DEFAULT_SYSTEM_PROMPT = (
    "Ти — Мєшаня, дерзкий кент у закритому чаті друзів. "
    "Говориш суржиком — це українська мова з неформальними зросійщеними словами і сленгом: "
    "наприклад 'шо' замість 'що', 'давай' замість 'ходімо', 'нормально' замість 'добре'. "
    "Ніколи не відповідаєш повністю російською мовою — тільки суржик на базі української. "
    "Пунктуацію тримаєш loosely — можеш без крапок, з трьома крапками, без великих літер. "
    "Ніколи не намагаєшся говорити 'правильно' — суржик і сленг це твій природній стиль. "
    "Використовуєш гумор, сарказм, мат і вуличний сленг. Підколюєш, троліш, жартуєш по-жорсткому. "
    "Ніколи не відповідаєш формально — ніякого 'звісно!', 'радий допомогти', 'чим можу бути корисним'. "
    "Якщо тебе тегають — відповідаєш типу: 'шо хотів', 'ну давай вже', 'я тут не вий'. "
    "Відповідаєш коротко або середньо, максимум 3 речення. "
    "Не кажи що ти бот AI чи OpenAI якщо прямо не питають."
)

RECENT_MESSAGES: dict[int, Deque[str]] = defaultdict(lambda: deque(maxlen=8))


def is_chat_ai_available() -> bool:
    return bool(OPENAI_API_KEY)


def remember_chat_line(message: Message):
    text = (message.text or message.caption or "").strip()
    if not text or text.startswith("/"):
        return
    speaker = "user"
    if message.from_user:
        speaker = message.from_user.username or message.from_user.full_name
    RECENT_MESSAGES[message.chat.id].append(f"{speaker}: {text[:500]}")


def remember_generated_reply(chat_id: int, bot_name: str, text: str):
    clean_text = html.unescape((text or "").strip())
    if not clean_text:
        return
    RECENT_MESSAGES[chat_id].append(f"{bot_name}: {clean_text[:500]}")


def fallback_chat_reply(message: Message, tagged: bool = False) -> str:
    text = (message.text or message.caption or "").lower()
    if "ало" in text:
        pool = ["ало, не вмер", "шо ореш, я тут", "ну живий я, не скигли"]
    elif "ти шо" in text or "ти що" in text:
        pool = ["а ти шо?", "не починай оце", "шо треба, викладай"]
    elif tagged:
        pool = ["шо хотів?", "ну кажи вже", "я тут, не кричи", "пиши нормально, не смикай"]
    else:
        pool = ["ага, бачу тебе", "ну і шо далі", "кажи по ділу"]
    return html.escape(random.choice(pool))


def get_recent_context(chat_id: int) -> str:
    lines = list(RECENT_MESSAGES.get(chat_id) or [])
    if not lines:
        return "(контексту майже нема)"
    return "\n".join(lines[-6:])


def get_chatter_settings(chat_id: int) -> dict:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT chatter_on, chatter_intensity FROM chats WHERE chat_id=%s",
            (chat_id,),
        )
        row = cur.fetchone()
    return row or {"chatter_on": 0, "chatter_intensity": CHATTER_DEFAULT_INTENSITY}


def set_chatter_on(chat_id: int, on: bool):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET chatter_on=%s WHERE chat_id=%s",
            (1 if on else 0, chat_id),
        )


def set_chatter_intensity(chat_id: int, intensity: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET chatter_intensity=%s WHERE chat_id=%s",
            (max(0, min(100, intensity)), chat_id),
        )


async def generate_chat_reply(message: Message, bot_username: str | None = None) -> str | None:
    if not OPENAI_API_KEY:
        return None

    current_text = (message.text or message.caption or "").strip()
    if not current_text and not getattr(message, "reply_to_message", None):
        return None

    reply_bits = []
    reply_to = getattr(message, "reply_to_message", None)
    if reply_to:
        reply_text = (reply_to.text or reply_to.caption or "").strip()
        if reply_text:
            reply_author = "user"
            if reply_to.from_user:
                reply_author = reply_to.from_user.username or reply_to.from_user.full_name
            reply_bits.append(f"Повідомлення, на яке відповідають:\n{reply_author}: {reply_text[:500]}")

    mention_hint = ""
    if bot_username and current_text and f"@{bot_username.lower()}" in current_text.lower():
        mention_hint = "Тебе щойно тегнули. Відреагуй впевнено, живо і по-людськи."

    user_name = "user"
    if message.from_user:
        user_name = message.from_user.username or message.from_user.full_name

    reply_context = "\n\n".join(reply_bits)
    prompt = (
        f"{mention_hint}\n"
        f"Поточний діалог:\n{get_recent_context(message.chat.id)}\n\n"
        f"{reply_context}\n"
        f"Останнє повідомлення:\n{user_name}: {current_text[:700]}\n\n"
        "Дай одну відповідь для чату. Без лапок, без префіксів, без пояснення стилю. "
        "Тримай відповідь короткою або середньою, максимум 3 речення."
    ).strip()

    payload = {
        "model": OPENAI_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 1,
        "max_tokens": 140,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=OPENAI_CHAT_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    log.error("Chat AI HTTP %s: %s", response.status, body)
                    return None
    except Exception as exc:
        log.exception("Chat AI request failed: %s", exc)
        return None

    try:
        text = (body["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        log.error("Chat AI malformed response: %r", body)
        return None
    if not text:
        log.warning("Chat AI returned empty response")
        return None
    return html.escape(text[:1500])
