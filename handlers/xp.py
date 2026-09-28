# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.dispatcher.event.bases import SkipHandler

from services.media import extract_urls
from services.settings import get_chat_settings
from services.xp import award_message_xp, get_rank, top_xp as top_xp_q, reset_xp, level_after_1000
from utils import remember_user, is_muted_now, extract_mention, resolve_username_to_id, is_chat_admin


router = Router()


@router.message()
async def xp_collector(m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler
    s = get_chat_settings(m.chat.id)
    if not s.get("xp_enabled"):
        raise SkipHandler

    links = extract_urls(m)
    links_count = len(links)
    has_useful_link = (links_count > 0) and (links_count <= 3)
    is_reply = bool(
        getattr(m, "reply_to_message", None)
        and getattr(m.reply_to_message, "from_user", None)
        and m.reply_to_message.from_user.id != m.from_user.id
    )

    xp = 1
    if has_useful_link:
        xp += 2
    if is_reply:
        xp += 3

    await asyncio.to_thread(award_message_xp, m.chat.id, m.from_user.id, m.from_user.username, xp)
    raise SkipHandler


@router.message(Command("rank"))
async def rank_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("xp_enabled"):
        return await m.answer("XP вимкнений в цьому чаті.")

    uid = m.from_user.id
    uname = m.from_user.username
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) == 2:
        mid, mname = extract_mention(m)
        if mid:
            uid = mid
            uname = mname
        else:
            arg = parts[1].strip()
            if arg.startswith("@"):
                arg = arg[1:]
            rid = resolve_username_to_id(m.chat.id, arg)
            if not rid:
                return await m.answer("Не бачив цього користувача в чаті. Нехай напише хоч раз.")
            uid = rid
            uname = arg

    row = await asyncio.to_thread(get_rank, m.chat.id, uid)
    xp = int(row.get("xp") or 0)
    lvl = int(row.get("level") or level_after_1000(xp))
    msgs = int(row.get("messages_count") or 0)
    dls = int(row.get("downloads_count") or 0)
    who = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>user</a>"
    await m.answer(
        f"🏅 {who}\n"
        f"• level: <b>{lvl}</b>\n"
        f"• xp: <b>{xp}</b>\n"
        f"• messages: {msgs}\n"
        f"• downloads: {dls}"
    )


@router.message(Command("top_xp"))
async def top_xp_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    if not s.get("xp_enabled"):
        return await m.answer("XP вимкнений в цьому чаті.")
    rows = await asyncio.to_thread(top_xp_q, m.chat.id, 10)
    if not rows:
        return await m.answer("Немає даних.")
    lines = ["🏆 <b>Топ XP</b>"]
    for i, r in enumerate(rows, 1):
        uid = int(r["user_id"])
        uname = r.get("username")
        xp = int(r.get("xp") or 0)
        lvl = int(r.get("level") or level_after_1000(xp))
        who = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>user</a>"
        lines.append(f"{i}. {who}: <b>{xp}</b> (lvl {lvl})")
    await m.answer("\n".join(lines))


@router.message(Command("xp_reset"))
async def xp_reset_cmd(m: Message):
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        return await m.answer("Тільки для адмінів.")
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) != 2:
        return await m.answer("Використай: <code>/xp_reset @user</code> або reply.")
    uid, uname = extract_mention(m)
    if not uid:
        arg = parts[1].strip()
        if arg.startswith("@"):
            arg = arg[1:]
        uid = resolve_username_to_id(m.chat.id, arg)
        if not uid:
            return await m.answer("Не бачив цього користувача в чаті.")
    await asyncio.to_thread(reset_xp, m.chat.id, uid)
    await m.answer("OK: XP скинуто.")
