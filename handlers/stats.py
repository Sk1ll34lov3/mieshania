# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.dispatcher.event.bases import SkipHandler

from services.media import extract_urls
from services.settings import get_chat_settings
from services.stats import record_message, chat_totals, top_users, activity_hours
from utils import remember_user, is_muted_now
from db import db


router = Router()


def _has_media(m: Message) -> int:
    return int(
        bool(
            getattr(m, "photo", None)
            or getattr(m, "video", None)
            or getattr(m, "document", None)
            or getattr(m, "animation", None)
            or getattr(m, "sticker", None)
            or getattr(m, "voice", None)
            or getattr(m, "video_note", None)
            or getattr(m, "audio", None)
        )
    )


@router.message()
async def stats_collector(m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        raise SkipHandler

    text = (m.text or m.caption or "")[:8000]
    links = len(extract_urls(m))
    media = _has_media(m)
    dt = m.date if isinstance(m.date, datetime) else datetime.utcnow()

    await asyncio.to_thread(record_message, m.chat.id, m.from_user.id, m.from_user.username, dt, text, links, media)
    raise SkipHandler


@router.message(Command("stats"))
async def stats_7d(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    totals = await asyncio.to_thread(chat_totals, m.chat.id, 7)
    await m.answer(
        "📊 <b>Статистика за 7 днів</b>\n"
        f"• повідомлень: {int(totals.get('msgs') or 0)}\n"
        f"• слів: {int(totals.get('words') or 0)}\n"
        f"• лінків: {int(totals.get('links') or 0)}\n"
        f"• медіа: {int(totals.get('media') or 0)}"
    )


@router.message(Command("stats_today"))
async def stats_today(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    totals = await asyncio.to_thread(chat_totals, m.chat.id, 1)
    await m.answer(
        "📊 <b>Статистика за сьогодні</b>\n"
        f"• повідомлень: {int(totals.get('msgs') or 0)}\n"
        f"• слів: {int(totals.get('words') or 0)}\n"
        f"• лінків: {int(totals.get('links') or 0)}\n"
        f"• медіа: {int(totals.get('media') or 0)}"
    )


@router.message(Command("top"))
async def top_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    rows = await asyncio.to_thread(top_users, m.chat.id, 7, "messages")
    if not rows:
        return await m.answer("Немає даних.")
    lines = ["🏆 <b>Топ активних (7 днів)</b>"]
    for i, r in enumerate(rows, 1):
        uid = int(r["user_id"])
        uname = r.get("username")
        c = int(r.get("c") or 0)
        who = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>user</a>"
        lines.append(f"{i}. {who}: <b>{c}</b>")
    await m.answer("\n".join(lines))


@router.message(Command("top_links"))
async def top_links_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    rows = await asyncio.to_thread(top_users, m.chat.id, 7, "links")
    if not rows:
        return await m.answer("Немає даних.")
    lines = ["🔗 <b>Топ лінків (7 днів)</b>"]
    for i, r in enumerate(rows, 1):
        uid = int(r["user_id"])
        uname = r.get("username")
        c = int(r.get("c") or 0)
        who = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>user</a>"
        lines.append(f"{i}. {who}: <b>{c}</b>")
    await m.answer("\n".join(lines))


@router.message(Command("silent"))
async def silent_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id, username, last_seen FROM user_map WHERE chat_id=%s ORDER BY last_seen ASC LIMIT 10",
            (m.chat.id,),
        )
        rows = cur.fetchall() or []
    if not rows:
        return await m.answer("Немає user_map.")
    lines = ["🤫 <b>Тихі (давно не писали)</b>"]
    for r in rows:
        uid = int(r["user_id"])
        uname = r.get("username")
        last = r.get("last_seen")
        who = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>user</a>"
        lines.append(f"• {who} — {last}")
    await m.answer("\n".join(lines))


@router.message(Command("activity"))
async def activity_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("stats_enabled"):
        return await m.answer("Статистика вимкнена в цьому чаті.")
    rows = await asyncio.to_thread(activity_hours, m.chat.id, 7)
    if not rows:
        return await m.answer("Немає даних.")
    lines = ["🕒 <b>Активність по годинах (7 днів, Kyiv)</b>"]
    for r in rows:
        h = int(r.get("hour") or 0)
        c = int(r.get("c") or 0)
        bar = "█" * min(20, max(1, c // 10)) if c else ""
        lines.append(f"{h:02d}:00 — {c} {bar}")
    await m.answer("\n".join(lines))
