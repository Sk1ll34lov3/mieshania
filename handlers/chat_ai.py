from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import log
from services.chat_ai import (
    fallback_chat_reply,
    generate_chat_reply,
    get_chatter_settings,
    is_chat_ai_available,
    remember_chat_line,
    remember_generated_reply,
    set_chatter_intensity,
    set_chatter_on,
)
from utils import get_chat, in_quiet, is_chat_admin, remember_user, upsert_chat

router = Router()


async def ensure_admin(m: Message) -> bool:
    if not m.from_user:
        return False
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("Тільки для адмінів.")
        return False
    return True


def _bot_was_tagged(message: Message, bot_username: str | None) -> bool:
    if not bot_username or not message.entities or not message.text:
        return False
    target = f"@{bot_username.lower()}"
    for entity in message.entities:
        if entity.type != "mention":
            continue
        value = message.text[entity.offset:entity.offset + entity.length].lower()
        if value == target:
            return True
    return False


def _is_reply_to_bot(message: Message, bot_id: int) -> bool:
    reply = getattr(message, "reply_to_message", None)
    return bool(reply and reply.from_user and reply.from_user.id == bot_id)


@router.message(Command("chat_ai_on"))
async def chat_ai_on_cmd(m: Message):
    if not await ensure_admin(m):
        return
    upsert_chat(m.chat.id)
    set_chatter_on(m.chat.id, True)
    await m.answer("Режим живого чату увімкнено.")


@router.message(Command("chat_ai_off"))
async def chat_ai_off_cmd(m: Message):
    if not await ensure_admin(m):
        return
    upsert_chat(m.chat.id)
    set_chatter_on(m.chat.id, False)
    await m.answer("Режим живого чату вимкнено.")


@router.message(Command("chat_ai_intensity"))
async def chat_ai_intensity_cmd(m: Message):
    if not await ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Використання: <code>/chat_ai_intensity 20</code>")
    intensity = max(0, min(100, int(parts[1])))
    upsert_chat(m.chat.id)
    set_chatter_intensity(m.chat.id, intensity)
    await m.answer(f"Інтенсивність балачок: <b>{intensity}</b>/100")


@router.message(Command("chat_ai_status"))
async def chat_ai_status_cmd(m: Message):
    upsert_chat(m.chat.id)
    settings = get_chatter_settings(m.chat.id)
    enabled = "ON" if settings.get("chatter_on") else "OFF"
    intensity = int(settings.get("chatter_intensity") or 0)
    api_state = "є" if is_chat_ai_available() else "нема"
    await m.answer(
        f"AI-режим: <b>{enabled}</b>\n"
        f"Інтенсивність: <b>{intensity}</b>/100\n"
        f"OpenAI key: <b>{api_state}</b>"
    )


async def maybe_reply_in_chat(m: Message):
    log.info(
        "chat_ai incoming: chat=%s user=%s text=%r",
        m.chat.id,
        m.from_user.id if m.from_user else None,
        (m.text or m.caption or "")[:200],
    )
    if m.chat.type not in ("group", "supergroup"):
        return
    if m.from_user and m.from_user.is_bot:
        return
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    remember_chat_line(m)
    if (m.text or "").startswith("/"):
        return
    if not is_chat_ai_available():
        return

    settings = get_chatter_settings(m.chat.id)
    if not settings.get("chatter_on"):
        return

    chat_row = get_chat(m.chat.id) or {}
    if in_quiet(chat_row):
        return

    me = await m.bot.get_me()
    tagged = _bot_was_tagged(m, me.username)
    replied_to_bot = _is_reply_to_bot(m, me.id)
    should_reply = tagged or replied_to_bot

    if not should_reply:
        return

    reply = await generate_chat_reply(m, me.username)
    if not reply:
        if not should_reply:
            return
        reply = fallback_chat_reply(m, tagged=tagged)
    if not reply:
        return

    try:
        await m.reply(reply)
        remember_generated_reply(m.chat.id, me.username or "bot", reply)
    except Exception:
        return
