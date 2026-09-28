# -*- coding: utf-8 -*-

from __future__ import annotations

import time
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.dispatcher.event.bases import CancelHandler, SkipHandler

from config import moderation_log
from services.media import extract_urls
from services.settings import get_chat_settings
from services.moderation import (
    register_message,
    register_flood_strike,
    register_links,
    add_warn,
    reset_warns,
    blacklist_match,
    add_blacklist_word,
    remove_blacklist_word,
    list_blacklist,
)
from utils import remember_user, is_chat_admin, is_muted_now, restrict_for_minutes


router = Router()


async def _ensure_admin(m: Message) -> bool:
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("Тільки для адмінів.")
        return False
    return True


@router.message()
async def smart_moderation(m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    # remember_user робить misc.py (та командні handlers) — тут не дублюємо
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler

    s = get_chat_settings(m.chat.id)
    if not s.get("moderation_enabled"):
        raise SkipHandler
    if await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        raise SkipHandler

    now = time.time()

    # антифлуд: 5 повідомлень за 3 секунди
    cnt = register_message(m.chat.id, m.from_user.id, now)
    if cnt >= 5:
        try:
            await m.bot.delete_message(m.chat.id, m.message_id)
        except Exception:
            pass
        warns = add_warn(m.chat.id, m.from_user.id)
        strikes = register_flood_strike(m.chat.id, m.from_user.id, now)
        moderation_log.info(f"ANTIFLOOD delete chat={m.chat.id} user={m.from_user.id} warns={warns} strikes={strikes}")
        try:
            await m.answer(f"⚠️ Антифлуд: попередження ({warns}).")
        except Exception:
            pass
        if strikes >= 2:
            try:
                await restrict_for_minutes(m.bot, m.chat.id, m.from_user.id, 5)
                moderation_log.info(f"ANTIFLOOD mute chat={m.chat.id} user={m.from_user.id} minutes=5")
                await m.answer("🔇 Антифлуд: mute на 5 хв.")
            except Exception:
                pass
        raise CancelHandler

    # антиспам лінків
    urls = extract_urls(m)
    if len(urls) > 3:
        try:
            await m.bot.delete_message(m.chat.id, m.message_id)
        except Exception:
            pass
        moderation_log.info(f"ANTISPAM delete chat={m.chat.id} user={m.from_user.id} links_in_msg={len(urls)}")
        raise CancelHandler

    links_30s = register_links(m.chat.id, m.from_user.id, len(urls), now)
    if links_30s > 5:
        try:
            await restrict_for_minutes(m.bot, m.chat.id, m.from_user.id, 10)
            moderation_log.info(f"ANTISPAM mute chat={m.chat.id} user={m.from_user.id} minutes=10 links_30s={links_30s}")
            await m.answer("🔇 Антиспам: mute на 10 хв.")
        except Exception:
            pass
        raise CancelHandler

    # blacklist слів
    text_low = (m.text or m.caption or "").lower()
    bl = blacklist_match(m.chat.id, text_low)
    if bl:
        action = str(bl.get("action") or "delete")
        word = str(bl.get("word") or "")
        mm = bl.get("mute_minutes")
        if action in ("delete", "mute"):
            try:
                await m.bot.delete_message(m.chat.id, m.message_id)
            except Exception:
                pass
        if action == "warn":
            warns = add_warn(m.chat.id, m.from_user.id)
            moderation_log.info(f"BLACKLIST warn chat={m.chat.id} user={m.from_user.id} word={word} warns={warns}")
            try:
                await m.answer(f"⚠️ Заборонене слово → варн ({warns}).")
            except Exception:
                pass
            if warns >= 3:
                try:
                    await restrict_for_minutes(m.bot, m.chat.id, m.from_user.id, 30)
                    reset_warns(m.chat.id, m.from_user.id)
                    await m.answer("🔇 3 варни → автомута на 30 хв.")
                except Exception:
                    pass
        elif action == "mute":
            minutes = int(mm or 10)
            try:
                await restrict_for_minutes(m.bot, m.chat.id, m.from_user.id, minutes)
                moderation_log.info(f"BLACKLIST mute chat={m.chat.id} user={m.from_user.id} word={word} minutes={minutes}")
                await m.answer(f"🔇 Заборонене слово → mute на {minutes} хв.")
            except Exception:
                pass
        else:
            moderation_log.info(f"BLACKLIST delete chat={m.chat.id} user={m.from_user.id} word={word}")
        raise CancelHandler

    # нічого не зробили — не блокуємо інші фічі (media/stats/xp/watch/...)
    raise SkipHandler


@router.message(Command("blacklist_add"))
async def blacklist_add_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await _ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) < 3:
        return await m.answer("Використай: <code>/blacklist_add слово delete|warn|mute [mute_minutes]</code>")
    word = parts[1]
    action = parts[2]
    mm = int(parts[3]) if (len(parts) >= 4 and parts[3].isdigit()) else None
    try:
        add_blacklist_word(m.chat.id, word, action, mm)
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer("OK.")


@router.message(Command("blacklist_rm"))
async def blacklist_rm_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await _ensure_admin(m):
        return
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await m.answer("Використай: <code>/blacklist_rm слово</code>")
    n = remove_blacklist_word(m.chat.id, parts[1])
    await m.answer("OK." if n else "Не знайдено.")


@router.message(Command("blacklist_list"))
async def blacklist_list_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await _ensure_admin(m):
        return
    rows = list_blacklist(m.chat.id)
    if not rows:
        return await m.answer("Порожньо.")
    lines = ["🧹 <b>Blacklist</b>"]
    for r in rows[:50]:
        w = html.escape(str(r.get("word") or ""))
        a = html.escape(str(r.get("action") or ""))
        mm = r.get("mute_minutes")
        extra = f" ({int(mm)}m)" if (a == "mute" and mm) else ""
        lines.append(f"• {w} → {a}{extra}")
    await m.answer("\n".join(lines))


@router.message(Command("clean"))
async def clean_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await _ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Використай: <code>/clean 50</code>")
    n = min(100, max(1, int(parts[1])))
    deleted = 0
    for i in range(n + 1):  # + команда
        try:
            await m.bot.delete_message(m.chat.id, m.message_id - i)
            deleted += 1
        except Exception:
            pass
    await m.answer(f"OK: видалено {deleted}.")


@router.message(Command("slowmode"))
async def slowmode_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await _ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 2:
        return await m.answer("Використай: <code>/slowmode 5</code> або <code>/slowmode off</code>")
    arg = parts[1].lower()
    delay = 0
    if arg != "off":
        if not arg.isdigit():
            return await m.answer("Використай: <code>/slowmode 5</code> або <code>/slowmode off</code>")
        delay = max(0, min(21600, int(arg)))
    try:
        await m.bot.set_chat_slow_mode_delay(m.chat.id, delay)
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer("OK: slowmode off." if delay == 0 else f"OK: slowmode {delay}s.")
