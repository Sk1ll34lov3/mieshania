# -*- coding: utf-8 -*-

from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.saved import save_reply, list_saved, clear_saved
from utils import remember_user


router = Router()


@router.message(Command("save"))
async def save_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not getattr(m, "reply_to_message", None):
        return await m.answer("Команда працює тільки як reply на повідомлення.")
    try:
        save_reply(m.chat.id, m.from_user.id, m.reply_to_message)
    except Exception as e:
        return await m.answer(f"Не вийшло зберегти: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer("✅ Збережено.")


@router.message(Command("saved"))
async def saved_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    try:
        rows = list_saved(m.chat.id, m.from_user.id, 10)
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    if not rows:
        return await m.answer("Порожньо.")
    lines = ["⭐️ <b>Saved (останні 10)</b>"]
    for r in rows:
        mid = int(r.get("source_message_id") or 0)
        mtype = r.get("media_type") or "text"
        txt = (r.get("text") or "").strip().replace("\n", " ")
        if len(txt) > 80:
            txt = txt[:77] + "…"
        lines.append(f"• #{int(r['id'])} msg_id={mid} ({html.escape(str(mtype))}) {html.escape(txt)}")
    await m.answer("\n".join(lines))


@router.message(Command("saved_clear"))
async def saved_clear_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    try:
        n = clear_saved(m.chat.id, m.from_user.id)
    except Exception as e:
        return await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
    await m.answer(f"OK: видалено {n}.")

