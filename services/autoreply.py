# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from db import db


COOLDOWN_SEC = 60
_last_fire: dict[tuple[int, int], float] = {}


def add_autoreply(chat_id: int, trigger_text: str, response_text: str, match_type: str = "contains") -> int:
    trigger = (trigger_text or "").strip()
    response = (response_text or "").strip()
    if not trigger or not response:
        raise ValueError("empty")
    if match_type not in ("contains", "exact"):
        match_type = "contains"
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auto_replies (chat_id, trigger_text, response_text, match_type, is_active)
            VALUES (%s,%s,%s,%s,1)
            """,
            (chat_id, trigger, response, match_type),
        )
        return int(cur.lastrowid or 0)


def list_autoreplies(chat_id: int) -> List[Dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, trigger_text, response_text, match_type, is_active, created_at FROM auto_replies WHERE chat_id=%s ORDER BY id DESC LIMIT 50",
            (chat_id,),
        )
        return cur.fetchall() or []


def remove_autoreply(chat_id: int, rid: int) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM auto_replies WHERE chat_id=%s AND id=%s", (chat_id, int(rid)))
        return int(cur.rowcount or 0)


def active_autoreplies(chat_id: int) -> List[Dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, trigger_text, response_text, match_type FROM auto_replies WHERE chat_id=%s AND is_active=1",
            (chat_id,),
        )
        return cur.fetchall() or []


def cooldown_ok(chat_id: int, rid: int) -> bool:
    key = (int(chat_id), int(rid))
    now = time.time()
    last = _last_fire.get(key, 0.0)
    if now - last < COOLDOWN_SEC:
        return False
    _last_fire[key] = now
    return True

