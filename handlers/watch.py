# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.dispatcher.event.bases import SkipHandler

from services.settings import get_chat_settings
from services.watch import add_watch_word, add_watch_user, list_watches, deactivate_watch, active_watches_for_chat, notify_watch
from utils import remember_user, is_muted_now, extract_mention, resolve_username_to_id


router = Router()


@router.message()
async def watch_trigger(m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler
    s = get_chat_settings(m.chat.id)
    if not s.get("watch_enabled"):
        raise SkipHandler

    text = (m.text or m.caption or "").lower()
    if not text:
        return

    watches = await asyncio.to_thread(active_watches_for_chat, m.chat.id)
    if not watches:
        return

    sender_id = m.from_user.id
    per_user: dict[int, str] = {}
    for w in watches:
        watcher_id = int(w["user_id"])
        wtype = w.get("type")
        val = str(w.get("value") or "")
        if wtype == "user":
            if val == str(sender_id):
                per_user.setdefault(watcher_id, f"👀 Пише користувач <a href='tg://user?id={sender_id}'>id={sender_id}</a> у чаті.")
        elif wtype == "word":
            if val and val in text:
                per_user.setdefault(watcher_id, f"🔔 Знайшов слово <b>{html.escape(val)}</b> у чаті.")

    for watcher_id, msg in per_user.items():
        await notify_watch(m.bot, m.chat.id, m.message_id, watcher_id, msg)
    raise SkipHandler


@router.message(Command("watch_word"))
async def watch_word_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("watch_enabled"):
        return await m.answer("Watch вимкнено в цьому чаті.")
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await m.answer("Використай: <code>/watch_word слово</code>")
    word = parts[1].strip()
    try:
        wid = await asyncio.to_thread(add_watch_word, m.chat.id, m.from_user.id, word)
    except ValueError as e:
        if "short" in str(e):
            return await m.answer("Слово надто коротке (мін 3 символи).")
        if "too many" in str(e):
            return await m.answer("Забагато watch-правил (макс 20).")
        return await m.answer("Не вийшло додати.")
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer(f"OK: watch #{wid} (word).")


@router.message(Command("watch_user"))
async def watch_user_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("watch_enabled"):
        return await m.answer("Watch вимкнено в цьому чаті.")
    uid, uname = extract_mention(m)
    if not uid:
        # дозволимо reply або @username
        if getattr(m, "reply_to_message", None) and m.reply_to_message.from_user:
            uid = m.reply_to_message.from_user.id
        else:
            parts = (m.text or "").split(maxsplit=1)
            if len(parts) != 2:
                return await m.answer("Використай: <code>/watch_user @user</code> або reply.")
            arg = parts[1].strip()
            if arg.startswith("@"):
                arg = arg[1:]
            rid = resolve_username_to_id(m.chat.id, arg)
            if not rid:
                return await m.answer("Не бачив цього користувача в чаті.")
            uid = rid
    try:
        wid = await asyncio.to_thread(add_watch_user, m.chat.id, m.from_user.id, int(uid))
    except ValueError as e:
        if "too many" in str(e):
            return await m.answer("Забагато watch-правил (макс 20).")
        return await m.answer("Не вийшло додати.")
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer(f"OK: watch #{wid} (user).")


@router.message(Command("unwatch"))
async def unwatch_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("watch_enabled"):
        return await m.answer("Watch вимкнено в цьому чаті.")
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Використай: <code>/unwatch ID</code>")
    n = await asyncio.to_thread(deactivate_watch, m.chat.id, m.from_user.id, int(parts[1]))
    await m.answer("OK." if n else "Не знайдено.")


@router.message(Command("watch_list"))
async def watch_list_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("watch_enabled"):
        return await m.answer("Watch вимкнено в цьому чаті.")
    rows = await asyncio.to_thread(list_watches, m.chat.id, m.from_user.id)
    if not rows:
        return await m.answer("Порожньо.")
    lines = ["👀 <b>Watch list</b>"]
    for r in rows[:20]:
        lines.append(f"• #{int(r['id'])} {html.escape(str(r.get('type')))}: {html.escape(str(r.get('value')))}")
    await m.answer("\n".join(lines))
