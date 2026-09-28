# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMINS
from services.reports import create_report, list_reports, set_report_status
from services.settings import get_chat_settings
from utils import remember_user, is_chat_admin


router = Router()


@router.message(Command("report"))
async def report_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("reports_enabled"):
        return await m.answer("Репорти вимкнені в цьому чаті.")
    if not getattr(m, "reply_to_message", None) or not m.reply_to_message.from_user:
        return await m.answer("Команда працює тільки як reply на повідомлення.")
    reason = ""
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) == 2:
        reason = parts[1].strip()

    rep = m.reply_to_message
    try:
        rid = await asyncio.to_thread(
            create_report,
            m.chat.id,
            rep.message_id,
            rep.from_user.id,
            rep.from_user.username,
            m.from_user.id,
            m.from_user.username,
            reason,
        )
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")

    await m.answer("✅ Репорт прийнято. Адміни переглянуть.")

    # повідомлення адмінам у приват (якщо відкритий)
    note = (
        f"🚩 <b>Новий репорт</b> (#{rid})\n"
        f"chat_id: <code>{m.chat.id}</code>\n"
        f"reported: <a href='tg://user?id={rep.from_user.id}'>id={rep.from_user.id}</a>\n"
        f"reporter: <a href='tg://user?id={m.from_user.id}'>id={m.from_user.id}</a>\n"
        f"reason: {html.escape(reason) if reason else '—'}"
    )
    for admin_id in ADMINS:
        try:
            await m.bot.send_message(int(admin_id), note)
        except Exception:
            pass


@router.message(Command("reports"))
async def reports_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("reports_enabled"):
        return await m.answer("Репорти вимкнені в цьому чаті.")
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        return await m.answer("Тільки для адмінів.")
    rows = await asyncio.to_thread(list_reports, m.chat.id, 10)
    if not rows:
        return await m.answer("Порожньо.")
    lines = ["🚩 <b>Останні репорти</b>"]
    for r in rows:
        rid = int(r["id"])
        st = html.escape(str(r.get("status") or "new"))
        reason = (r.get("reason") or "").strip().replace("\n", " ")
        if len(reason) > 60:
            reason = reason[:57] + "…"
        reason = html.escape(reason) if reason else "—"
        reported_id = int(r.get("reported_user_id") or 0)
        reporter_id = int(r.get("reporter_user_id") or 0)
        lines.append(
            f"• #{rid} [{st}] reported=<a href='tg://user?id={reported_id}'>id={reported_id}</a> "
            f"by <a href='tg://user?id={reporter_id}'>id={reporter_id}</a> — {reason}"
        )
    await m.answer("\n".join(lines))


@router.message(Command("report_status"))
async def report_status_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("reports_enabled"):
        return await m.answer("Репорти вимкнені в цьому чаті.")
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        return await m.answer("Тільки для адмінів.")
    parts = (m.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit():
        return await m.answer("Використай: <code>/report_status ID reviewed|rejected|actioned</code>")
    try:
        n = await asyncio.to_thread(set_report_status, m.chat.id, int(parts[1]), parts[2])
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer("OK." if n else "Не знайдено.")

