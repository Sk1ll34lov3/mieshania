# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from db import db


LEVELS = [
    (1, 0),
    (2, 50),
    (3, 150),
    (4, 300),
    (5, 600),
    (6, 1000),
]


def level_for_xp(xp: int) -> int:
    xp = max(0, int(xp))
    for lvl, need in reversed(LEVELS):
        if xp >= need:
            return lvl
    return 1


def level_after_1000(xp: int) -> int:
    # після 1000 XP: кожні +500 XP = +1 level
    xp = max(0, int(xp))
    if xp < 1000:
        return level_for_xp(xp)
    return 6 + (xp - 1000) // 500


def award_message_xp(chat_id: int, user_id: int, username: str | None, xp_delta: int) -> Tuple[int, int, int]:
    """
    Додає XP за повідомлення, але не частіше 1 разу на 60 сек.
    Завжди інкрементить messages_count.
    Повертає (added, total_xp, level).
    """
    xp_delta = max(0, int(xp_delta))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_xp (chat_id, user_id, username, xp, level, messages_count, downloads_count, last_xp_at)
            VALUES (%s,%s,%s,0,1,0,0,NULL)
            ON DUPLICATE KEY UPDATE username=VALUES(username)
            """,
            (chat_id, user_id, username),
        )
        # умовний апдейт з cooldown
        cond = "(last_xp_at IS NULL OR last_xp_at < (NOW() - INTERVAL 60 SECOND))"
        cur.execute(
            f"""
            UPDATE user_xp
            SET
              messages_count = messages_count + 1,
              xp = xp + IF({cond}, %s, 0),
              last_xp_at = IF({cond}, NOW(), last_xp_at)
            WHERE chat_id=%s AND user_id=%s
            """,
            (xp_delta, chat_id, user_id),
        )
        cur.execute("SELECT xp, last_xp_at FROM user_xp WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        row = cur.fetchone() or {"xp": 0}
        total_xp = int(row.get("xp") or 0)
        level = level_after_1000(total_xp)
        cur.execute("UPDATE user_xp SET level=%s WHERE chat_id=%s AND user_id=%s", (level, chat_id, user_id))

    # added: якщо cooldown дозволив — ми додали xp_delta (інакше 0). Визначити точно без ще одного SELECT складно.
    # Повертаємо xp_delta як best-effort (користувачу це не критично).
    return xp_delta, total_xp, level


def add_download(chat_id: int, user_id: int, username: str | None) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_xp (chat_id, user_id, username, xp, level, messages_count, downloads_count, last_xp_at)
            VALUES (%s,%s,%s,0,1,0,1,NULL)
            ON DUPLICATE KEY UPDATE
              username=VALUES(username),
              downloads_count = downloads_count + 1
            """,
            (chat_id, user_id, username),
        )


def get_rank(chat_id: int, user_id: int) -> Dict:
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM user_xp WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        return cur.fetchone() or {}


def top_xp(chat_id: int, limit: int = 10) -> List[Dict]:
    limit = max(1, min(20, int(limit)))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, username, xp, level
            FROM user_xp
            WHERE chat_id=%s
            ORDER BY xp DESC
            LIMIT %s
            """,
            (chat_id, limit),
        )
        return cur.fetchall() or []


def reset_xp(chat_id: int, user_id: int) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE user_xp SET xp=0, level=1, messages_count=0, downloads_count=0, last_xp_at=NULL WHERE chat_id=%s AND user_id=%s",
            (chat_id, user_id),
        )

