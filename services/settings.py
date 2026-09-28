# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Dict, Tuple

from db import db


def ensure_chat_settings(chat_id: int) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (chat_id,))

_cache: Dict[int, Tuple[float, Dict]] = {}
_TTL = 30.0


def get_chat_settings(chat_id: int) -> Dict:
    cid = int(chat_id)
    now = time.time()
    cached = _cache.get(cid)
    if cached and (now - cached[0]) < _TTL:
        return cached[1]
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM chat_settings WHERE chat_id=%s", (cid,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT IGNORE INTO chat_settings (chat_id) VALUES (%s)", (cid,))
            cur.execute("SELECT * FROM chat_settings WHERE chat_id=%s", (cid,))
            row = cur.fetchone()
        row = row or {"chat_id": cid}
    _cache[cid] = (now, row)
    return row


def set_feature(chat_id: int, feature_col: str, enabled: bool) -> None:
    cid = int(chat_id)
    with db() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE chat_settings SET {feature_col}=%s WHERE chat_id=%s", (1 if enabled else 0, cid))
    _cache.pop(cid, None)


def set_download_limits(chat_id: int, user_per_min: int, chat_per_10min: int) -> None:
    cid = int(chat_id)
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chat_settings SET download_user_per_min=%s, download_chat_per_10min=%s WHERE chat_id=%s",
            (int(user_per_min), int(chat_per_10min), cid),
        )
    _cache.pop(cid, None)
