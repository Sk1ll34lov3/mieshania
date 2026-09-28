# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.dispatcher.event.bases import SkipHandler

from services.autoreply import add_autoreply, list_autoreplies, remove_autoreply, active_autoreplies, cooldown_ok
from services.settings import get_chat_settings
from utils import remember_user, is_muted_now, is_chat_admin


router = Router()


async def _ensure_admin(m: Message) -> bool:
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("Тільки для адмінів.")
        return False
    return True


@router.message()
async def autoreply_trigger(m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler
    s = get_chat_settings(m.chat.id)
    if not s.get("autoreply_enabled"):
        raise SkipHandler

    txt = (m.text or m.caption or "").strip()
    if not txt:
        return
    low = txt.lower()

    rows = await asyncio.to_thread(active_autoreplies, m.chat.id)
    for r in rows:
        rid = int(r["id"])
        trig = str(r.get("trigger_text") or "")
        resp = str(r.get("response_text") or "")
        mt = str(r.get("match_type") or "contains")
        if not trig or not resp:
            continue
        t = trig.lower()
        matched = (low == t) if mt == "exact" else (t in low)
        if not matched:
            continue
        if not cooldown_ok(m.chat.id, rid):
            raise SkipHandler
        await m.reply(resp)
        raise SkipHandler
    raise SkipHandler


@router.message(Command("autoreply_add"))
async def autoreply_add_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("autoreply_enabled"):
        return await m.answer("Auto-reply вимкнений в цьому чаті.")
    if not await _ensure_admin(m):
        return
    args = (m.text or "").split(maxsplit=1)
    if len(args) != 2 or "|" not in args[1]:
        return await m.answer("Використай: <code>/autoreply_add trigger | response</code>")
    left, right = [p.strip() for p in args[1].split("|", 1)]
    try:
        rid = await asyncio.to_thread(add_autoreply, m.chat.id, left, right, "contains")
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer(f"OK: autoreply #{rid}.")


@router.message(Command("autoreply_list"))
async def autoreply_list_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("autoreply_enabled"):
        return await m.answer("Auto-reply вимкнений в цьому чаті.")
    if not await _ensure_admin(m):
        return
    rows = await asyncio.to_thread(list_autoreplies, m.chat.id)
    if not rows:
        return await m.answer("Порожньо.")
    lines = ["🤖 <b>Auto replies</b>"]
    for r in rows[:20]:
        rid = int(r["id"])
        trig = html.escape(str(r.get("trigger_text") or ""))
        mt = html.escape(str(r.get("match_type") or "contains"))
        lines.append(f"• #{rid} ({mt}) — {trig}")
    await m.answer("\n".join(lines))


@router.message(Command("autoreply_rm"))
async def autoreply_rm_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("autoreply_enabled"):
        return await m.answer("Auto-reply вимкнений в цьому чаті.")
    if not await _ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Використай: <code>/autoreply_rm ID</code>")
    n = await asyncio.to_thread(remove_autoreply, m.chat.id, int(parts[1]))
    await m.answer("OK." if n else "Не знайдено.")
