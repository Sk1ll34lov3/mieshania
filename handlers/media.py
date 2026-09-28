# -*- coding: utf-8 -*-

from __future__ import annotations

import html
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.event.bases import SkipHandler

from downloader import download_url, get_media_info, is_supported
from services.media import media_action_keyboard, pick_first_supported_url
from services.limits import is_download_allowed, record_download
from services.settings import get_chat_settings
from services.xp import add_download
from utils import remember_user, is_chat_admin, is_muted_now


router = Router()


async def _ensure_media_enabled(m: Message) -> bool:
    s = get_chat_settings(m.chat.id)
    if not s.get("media_enabled"):
        await m.answer("Медіа-функції вимкнені в цьому чаті.")
        return False
    return True


async def _check_download_limit(m: Message, action: str = "download") -> bool:
    if await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        return True
    allowed, _, _, _, _ = is_download_allowed(m.chat.id, m.from_user.id)
    if not allowed:
        await m.answer("Забагато завантажень. Спробуй трохи пізніше.")
        return False
    record_download(m.chat.id, m.from_user.id, action=action)
    return True


def _url_from_args_or_reply(m: Message) -> Optional[str]:
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) >= 2 and parts[1].strip():
        return parts[1].strip()
    if getattr(m, "reply_to_message", None):
        return pick_first_supported_url(m.reply_to_message)
    return None


def _fmt_seconds(sec: object) -> str:
    try:
        s = int(sec or 0)
    except Exception:
        return "—"
    if s <= 0:
        return "—"
    h = s // 3600
    m = (s % 3600) // 60
    ss = s % 60
    return f"{h:d}:{m:02d}:{ss:02d}" if h else f"{m:d}:{ss:02d}"


def _fmt_bytes(n: object) -> str:
    try:
        x = int(n or 0)
    except Exception:
        return "—"
    if x <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(x)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.1f} {units[i]}"


def _guess_size(info: dict) -> int:
    for key in ("filesize", "filesize_approx"):
        try:
            v = int(info.get(key) or 0)
            if v > 0:
                return v
        except Exception:
            pass
    rf = info.get("requested_formats")
    if isinstance(rf, list):
        total = 0
        for it in rf:
            try:
                total += int((it or {}).get("filesize") or (it or {}).get("filesize_approx") or 0)
            except Exception:
                pass
        if total > 0:
            return total
    return 0


@router.message(Command("dl_audio"))
async def dl_audio_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    url = _url_from_args_or_reply(m)
    if not url:
        return await m.answer("Використай: <code>/dl_audio &lt;url&gt;</code> або зроби reply на повідомлення з лінком.")
    if not is_supported(url):
        return await m.answer("Цей домен поки не підтримую.")
    if not await _ensure_media_enabled(m):
        return
    if not await _check_download_limit(m, action="audio"):
        return
    await m.answer("Секунду, тягну аудіо…")
    try:
        await download_url(m.chat.id, url, m.bot, mode="audio")
        try:
            add_download(m.chat.id, m.from_user.id, m.from_user.username)
        except Exception:
            pass
    except Exception as e:
        await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")


@router.message(Command("dl_hd"))
async def dl_hd_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    url = _url_from_args_or_reply(m)
    if not url:
        return await m.answer("Використай: <code>/dl_hd &lt;url&gt;</code> або зроби reply на повідомлення з лінком.")
    if not is_supported(url):
        return await m.answer("Цей домен поки не підтримую.")
    if not await _ensure_media_enabled(m):
        return
    if not await _check_download_limit(m, action="hd"):
        return
    await m.answer("Секунду, тягну HD…")
    try:
        await download_url(m.chat.id, url, m.bot, mode="hd")
        try:
            add_download(m.chat.id, m.from_user.id, m.from_user.username)
        except Exception:
            pass
    except Exception as e:
        await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")


@router.message(Command("dl_sd"))
async def dl_sd_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    url = _url_from_args_or_reply(m)
    if not url:
        return await m.answer("Використай: <code>/dl_sd &lt;url&gt;</code> або зроби reply на повідомлення з лінком.")
    if not is_supported(url):
        return await m.answer("Цей домен поки не підтримую.")
    if not await _ensure_media_enabled(m):
        return
    if not await _check_download_limit(m, action="sd"):
        return
    await m.answer("Секунду, тягну SD…")
    try:
        await download_url(m.chat.id, url, m.bot, mode="sd")
        try:
            add_download(m.chat.id, m.from_user.id, m.from_user.username)
        except Exception:
            pass
    except Exception as e:
        await m.answer(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")


@router.message(Command("dl_info"))
async def dl_info_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    url = _url_from_args_or_reply(m)
    if not url:
        return await m.answer("Використай: <code>/dl_info &lt;url&gt;</code> або зроби reply на повідомлення з лінком.")
    if not is_supported(url):
        return await m.answer("Цей домен поки не підтримую.")
    if not await _ensure_media_enabled(m):
        return
    try:
        info = await get_media_info(url)
    except Exception as e:
        return await m.answer(f"Не вийшло отримати info: <code>{html.escape(str(e))[:1500]}</code>")

    title = html.escape(str(info.get("title") or "—"))
    platform = html.escape(str(info.get("extractor_key") or info.get("extractor") or "—"))
    duration = _fmt_seconds(info.get("duration"))
    size = _fmt_bytes(_guess_size(info))

    content_type = "video"
    try:
        if str(info.get("vcodec") or "").lower() == "none":
            content_type = "audio"
    except Exception:
        pass

    await m.answer(
        "ℹ️ <b>Media info</b>\n"
        f"• <b>Назва:</b> {title}\n"
        f"• <b>Платформа:</b> {platform}\n"
        f"• <b>Тривалість:</b> {duration}\n"
        f"• <b>Розмір:</b> {size}\n"
        f"• <b>Тип:</b> {html.escape(content_type)}"
    )


@router.message()
async def link_buttons_on_message(m: Message):
    if (m.text or "").startswith("/"):
        raise SkipHandler
    if m.from_user and is_muted_now(m.chat.id, m.from_user.id):
        raise SkipHandler
    if not await _ensure_media_enabled(m):
        raise SkipHandler
    url = pick_first_supported_url(m)
    if not url:
        raise SkipHandler
    # Авто-стратегія як раніше (пост лінка = завантаження), + кнопки для варіантів
    if m.from_user:
        if not await _check_download_limit(m, action="auto"):
            return
    await m.reply("Секунду, тягну відео…")
    try:
        await download_url(m.chat.id, url, m.bot, mode="auto")
        try:
            if m.from_user:
                add_download(m.chat.id, m.from_user.id, m.from_user.username)
        except Exception:
            pass
        await m.reply("Обери інший варіант:", reply_markup=media_action_keyboard())
    except Exception as e:
        await m.reply(f"Не вийшло витягнути відео. <code>{html.escape(str(e))[:1500]}</code>")
    raise SkipHandler


@router.callback_query(F.data.startswith("dl:"))
async def dl_callback(c: CallbackQuery):
    try:
        await c.answer()
    except Exception:
        pass
    msg = c.message
    if not msg or not getattr(msg, "reply_to_message", None):
        return
    url = pick_first_supported_url(msg.reply_to_message)
    if not url or not is_supported(url):
        return await msg.reply("Не бачу підтримуваного лінка в оригінальному повідомленні.")
    action = (c.data or "").split(":", 1)[1]
    mode = {"hd": "hd", "sd": "sd", "audio": "audio", "file": "file"}.get(action)
    if not mode:
        return

    # rate limit: враховуємо того, хто натиснув кнопку
    if not await is_chat_admin(c.bot, msg.chat.id, c.from_user.id):
        allowed, _, _, _, _ = is_download_allowed(msg.chat.id, c.from_user.id)
        if not allowed:
            return await msg.reply("Забагато завантажень. Спробуй трохи пізніше.")
        record_download(msg.chat.id, c.from_user.id, action=mode)

    await msg.reply("Секунду, тягну…")
    try:
        await download_url(msg.chat.id, url, c.bot, mode=mode)
        try:
            add_download(msg.chat.id, c.from_user.id, c.from_user.username)
        except Exception:
            pass
    except Exception as e:
        await msg.reply(f"Не вийшло: <code>{html.escape(str(e))[:1500]}</code>")
