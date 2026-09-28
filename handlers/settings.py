# -*- coding: utf-8 -*-

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.settings import get_chat_settings, set_feature, set_download_limits
from utils import is_chat_admin, remember_user


router = Router()


FEATURE_MAP = {
    "media": "media_enabled",
    "stats": "stats_enabled",
    "xp": "xp_enabled",
    "moderation": "moderation_enabled",
    "reports": "reports_enabled",
    "autoreply": "autoreply_enabled",
    "watch": "watch_enabled",
}


async def ensure_admin(m: Message) -> bool:
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("Тільки для адмінів.")
        return False
    return True


@router.message(Command("settings"))
async def settings_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    await m.answer(
        "⚙️ <b>Налаштування</b>\n"
        f"• media: {'on' if s.get('media_enabled') else 'off'}\n"
        f"• stats: {'on' if s.get('stats_enabled') else 'off'}\n"
        f"• xp: {'on' if s.get('xp_enabled') else 'off'}\n"
        f"• moderation: {'on' if s.get('moderation_enabled') else 'off'}\n"
        f"• reports: {'on' if s.get('reports_enabled') else 'off'}\n"
        f"• autoreply: {'on' if s.get('autoreply_enabled') else 'off'}\n"
        f"• watch: {'on' if s.get('watch_enabled') else 'off'}\n"
        "\n⏱ <b>Download limits</b>\n"
        f"• user/min: {int(s.get('download_user_per_min') or 3)}\n"
        f"• chat/10min: {int(s.get('download_chat_per_10min') or 15)}\n"
        "\nАдмін: <code>/feature &lt;name&gt; on|off</code>"
    )


@router.message(Command("feature"))
async def feature_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await m.answer("Використай: <code>/feature media|stats|xp|moderation|reports|autoreply|watch on|off</code>")
    name = parts[1].strip().lower()
    val = parts[2].strip().lower()
    if name not in FEATURE_MAP:
        return await m.answer("Невідома фіча.")
    if val not in ("on", "off"):
        return await m.answer("Значення: on або off.")
    set_feature(m.chat.id, FEATURE_MAP[name], val == "on")
    await m.answer(f"OK: {name} → {val}")


@router.message(Command("download_limits"))
async def download_limits_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    s = get_chat_settings(m.chat.id)
    await m.answer(
        "⏱ <b>Download limits</b>\n"
        f"• user/min: {int(s.get('download_user_per_min') or 3)}\n"
        f"• chat/10min: {int(s.get('download_chat_per_10min') or 15)}"
    )


@router.message(Command("set_download_limit"))
async def set_download_limit_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    if not await ensure_admin(m):
        return
    parts = (m.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await m.answer("Використай: <code>/set_download_limit 3 15</code>")
    user_per_min = max(1, int(parts[1]))
    chat_per_10min = max(1, int(parts[2]))
    set_download_limits(m.chat.id, user_per_min, chat_per_10min)
    await m.answer(f"OK: user/min={user_per_min}, chat/10min={chat_per_10min}")

