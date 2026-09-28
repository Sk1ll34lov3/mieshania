# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Tuple

from db import db
from services.settings import get_chat_settings


def _counts(chat_id: int, user_id: int) -> Tuple[int, int]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS c FROM download_limits "
            "WHERE chat_id=%s AND user_id=%s AND created_at >= (NOW() - INTERVAL 1 MINUTE)",
            (chat_id, user_id),
        )
        u = int((cur.fetchone() or {}).get("c") or 0)
        cur.execute(
            "SELECT COUNT(*) AS c FROM download_limits "
            "WHERE chat_id=%s AND created_at >= (NOW() - INTERVAL 10 MINUTE)",
            (chat_id,),
        )
        ch = int((cur.fetchone() or {}).get("c") or 0)
        return u, ch


def record_download(chat_id: int, user_id: int, action: str = "download") -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO download_limits (chat_id, user_id, action) VALUES (%s,%s,%s)",
            (chat_id, user_id, action),
        )


def is_download_allowed(chat_id: int, user_id: int) -> Tuple[bool, int, int, int, int]:
    """
    Returns (allowed, user_count, chat_count, user_limit, chat_limit).
    """
    s = get_chat_settings(chat_id)
    user_limit = int(s.get("download_user_per_min") or 3)
    chat_limit = int(s.get("download_chat_per_10min") or 15)
    user_count, chat_count = _counts(chat_id, user_id)
    allowed = (user_count < user_limit) and (chat_count < chat_limit)
    return allowed, user_count, chat_count, user_limit, chat_limit

