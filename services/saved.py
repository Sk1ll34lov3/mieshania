# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List, Optional

from aiogram.types import Message

from db import db


def _media_type(msg: Message) -> Optional[str]:
    for k in ("photo", "video", "document", "animation", "sticker", "voice", "video_note", "audio"):
        if getattr(msg, k, None):
            return k
    return None


def save_reply(chat_id: int, user_id: int, reply: Message) -> None:
    txt = (reply.text or reply.caption or None)
    mtype = _media_type(reply)
    src_user_id = reply.from_user.id if reply.from_user else None
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO saved_messages (chat_id, user_id, source_message_id, source_user_id, text, media_type)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (chat_id, user_id, reply.message_id, src_user_id, txt, mtype),
        )


def list_saved(chat_id: int, user_id: int, limit: int = 10) -> List[Dict]:
    limit = max(1, min(20, int(limit)))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_message_id, source_user_id, text, media_type, created_at
            FROM saved_messages
            WHERE chat_id=%s AND user_id=%s
            ORDER BY id DESC
            LIMIT %s
            """,
            (chat_id, user_id, limit),
        )
        return cur.fetchall() or []


def clear_saved(chat_id: int, user_id: int) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM saved_messages WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        return int(cur.rowcount or 0)

