# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from aiogram import Bot

from db import db


def _watch_count(chat_id: int, user_id: int) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM watches WHERE chat_id=%s AND user_id=%s AND is_active=1",
            (chat_id, user_id),
        )
        return int((cur.fetchone() or {}).get("c") or 0)


def add_watch_word(chat_id: int, user_id: int, word: str) -> int:
    w = (word or "").strip().lower()
    if len(w) < 3:
        raise ValueError("word too short")
    if _watch_count(chat_id, user_id) >= 20:
        raise ValueError("too many watches")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO watches (chat_id, user_id, type, value, is_active) VALUES (%s,%s,'word',%s,1)",
            (chat_id, user_id, w),
        )
        return int(cur.lastrowid or 0)


def add_watch_user(chat_id: int, user_id: int, target_user_id: int) -> int:
    if _watch_count(chat_id, user_id) >= 20:
        raise ValueError("too many watches")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO watches (chat_id, user_id, type, value, is_active) VALUES (%s,%s,'user',%s,1)",
            (chat_id, user_id, str(int(target_user_id))),
        )
        return int(cur.lastrowid or 0)


def list_watches(chat_id: int, user_id: int) -> List[Dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, type, value, is_active, created_at FROM watches WHERE chat_id=%s AND user_id=%s ORDER BY id DESC LIMIT 50",
            (chat_id, user_id),
        )
        return cur.fetchall() or []


def deactivate_watch(chat_id: int, user_id: int, watch_id: int) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE watches SET is_active=0 WHERE chat_id=%s AND user_id=%s AND id=%s",
            (chat_id, user_id, int(watch_id)),
        )
        return int(cur.rowcount or 0)


def active_watches_for_chat(chat_id: int) -> List[Dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, type, value FROM watches WHERE chat_id=%s AND is_active=1",
            (chat_id,),
        )
        return cur.fetchall() or []


def _chat_message_link(chat_id: int, message_id: int) -> Optional[str]:
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{int(message_id)}"
    return None


async def notify_watch(bot: Bot, chat_id: int, message_id: int, watcher_user_id: int, text: str) -> None:
    link = _chat_message_link(chat_id, message_id)
    payload = text + (f"\n{link}" if link else "")
    try:
        await bot.send_message(watcher_user_id, payload)
        return
    except Exception:
        pass
    # fallback у чат
    try:
        mention = f"<a href='tg://user?id={watcher_user_id}'>watch</a>"
        await bot.send_message(chat_id, f"{mention} {text}")
    except Exception:
        pass

