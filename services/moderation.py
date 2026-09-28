# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

from db import db


# in-memory sliding windows
_msg_times: Dict[Tuple[int, int], Deque[float]] = {}
_flood_strikes: Dict[Tuple[int, int], Deque[float]] = {}
_link_times: Dict[Tuple[int, int], Deque[float]] = {}


def _prune(dq: Deque[float], window_sec: float, now: float) -> None:
    while dq and (now - dq[0]) > window_sec:
        dq.popleft()


def register_message(chat_id: int, user_id: int, now: float) -> int:
    key = (int(chat_id), int(user_id))
    dq = _msg_times.setdefault(key, deque())
    dq.append(now)
    _prune(dq, 3.0, now)
    return len(dq)


def register_links(chat_id: int, user_id: int, count: int, now: float) -> int:
    key = (int(chat_id), int(user_id))
    dq = _link_times.setdefault(key, deque())
    for _ in range(max(0, int(count))):
        dq.append(now)
    _prune(dq, 30.0, now)
    return len(dq)


def register_flood_strike(chat_id: int, user_id: int, now: float) -> int:
    key = (int(chat_id), int(user_id))
    dq = _flood_strikes.setdefault(key, deque())
    dq.append(now)
    _prune(dq, 60.0, now)
    return len(dq)


def add_warn(chat_id: int, user_id: int) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_moderation (chat_id, user_id, warns) VALUES (%s,%s,1) "
            "ON DUPLICATE KEY UPDATE warns=warns+1",
            (chat_id, user_id),
        )
        cur.execute("SELECT warns FROM user_moderation WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        row = cur.fetchone() or {"warns": 1}
        return int(row.get("warns") or 1)


def reset_warns(chat_id: int, user_id: int) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE user_moderation SET warns=0 WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))


def blacklist_match(chat_id: int, text_lower: str) -> Optional[Dict]:
    if not text_lower:
        return None
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT word, action, mute_minutes FROM chat_blacklist_words WHERE chat_id=%s",
            (chat_id,),
        )
        rows = cur.fetchall() or []
    for r in rows:
        w = str(r.get("word") or "").strip().lower()
        if not w:
            continue
        if w in text_lower:
            return r
    return None


def add_blacklist_word(chat_id: int, word: str, action: str, mute_minutes: Optional[int] = None) -> None:
    w = (word or "").strip().lower()
    if not w:
        raise ValueError("empty")
    action = (action or "delete").strip().lower()
    if action not in ("delete", "warn", "mute"):
        raise ValueError("bad action")
    mm = int(mute_minutes) if (mute_minutes is not None) else None
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_blacklist_words (chat_id, word, action, mute_minutes)
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE action=VALUES(action), mute_minutes=VALUES(mute_minutes)
            """,
            (chat_id, w, action, mm),
        )


def remove_blacklist_word(chat_id: int, word: str) -> int:
    w = (word or "").strip().lower()
    with db() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_blacklist_words WHERE chat_id=%s AND word=%s", (chat_id, w))
        return int(cur.rowcount or 0)


def list_blacklist(chat_id: int) -> list[Dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT word, action, mute_minutes, created_at FROM chat_blacklist_words WHERE chat_id=%s ORDER BY word ASC",
            (chat_id,),
        )
        return cur.fetchall() or []
