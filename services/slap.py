# -*- coding: utf-8 -*-

from __future__ import annotations

import secrets
from typing import Optional

from db import db


def random_opponent(chat_id: int, user_id: int) -> Optional[dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, username
            FROM user_map
            WHERE chat_id=%s AND user_id<>%s AND user_id>0
            ORDER BY RAND()
            LIMIT 1
            """,
            (chat_id, user_id),
        )
        return cur.fetchone()


def play_slap(
    chat_id: int,
    attacker_id: int,
    attacker_username: str | None,
    target_id: int,
    target_username: str | None,
) -> bool:
    """Return True when the palm lands, otherwise the target blocks it."""
    landed = secrets.randbelow(2) == 0
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO slap_scores (chat_id, user_id, username, points, games, hits, blocks)
            VALUES (%s, %s, %s, %s, 1, %s, 0)
            ON DUPLICATE KEY UPDATE
                username=COALESCE(VALUES(username), username),
                points=points+VALUES(points),
                games=games+1,
                hits=hits+VALUES(hits)
            """,
            (chat_id, attacker_id, attacker_username, 1 if landed else 0, 1 if landed else 0),
        )
        cur.execute(
            """
            INSERT INTO slap_scores (chat_id, user_id, username, points, games, hits, blocks)
            VALUES (%s, %s, %s, %s, 1, 0, %s)
            ON DUPLICATE KEY UPDATE
                username=COALESCE(VALUES(username), username),
                points=points+VALUES(points),
                games=games+1,
                blocks=blocks+VALUES(blocks)
            """,
            (chat_id, target_id, target_username, 0 if landed else 1, 0 if landed else 1),
        )
    return landed


def top_slap_players(chat_id: int, limit: int = 10) -> list[dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, username, points, games, hits, blocks
            FROM slap_scores
            WHERE chat_id=%s
            ORDER BY points DESC, hits DESC, games DESC, user_id ASC
            LIMIT %s
            """,
            (chat_id, max(1, min(20, int(limit)))),
        )
        return cur.fetchall() or []
