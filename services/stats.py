# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple

from db import db


WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яІіЇїЄєҐґ']+", re.U)


def _today_in_kyiv(dt: datetime) -> Tuple[str, int]:
    kyiv = dt.astimezone(ZoneInfo("Europe/Kyiv"))
    return kyiv.date().isoformat(), int(kyiv.hour)


def record_message(chat_id: int, user_id: int, username: str | None, message_dt: datetime, text: str, links: int, media: int) -> None:
    date_str, hour = _today_in_kyiv(message_dt)
    words = len(WORD_RE.findall(text or ""))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_messages_stats
              (chat_id, user_id, username, date, messages_count, words_count, links_count, media_count)
            VALUES (%s,%s,%s,%s,1,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              username=VALUES(username),
              messages_count=messages_count+1,
              words_count=words_count+VALUES(words_count),
              links_count=links_count+VALUES(links_count),
              media_count=media_count+VALUES(media_count)
            """,
            (chat_id, user_id, username, date_str, words, int(links), int(media)),
        )
        cur.execute(
            """
            INSERT INTO chat_activity_hourly (chat_id, date, hour, messages_count)
            VALUES (%s,%s,%s,1)
            ON DUPLICATE KEY UPDATE messages_count=messages_count+1
            """,
            (chat_id, date_str, hour),
        )


def chat_totals(chat_id: int, days: int = 7) -> Dict[str, int]:
    days = max(1, int(days))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              COALESCE(SUM(messages_count),0) AS msgs,
              COALESCE(SUM(words_count),0) AS words,
              COALESCE(SUM(links_count),0) AS links,
              COALESCE(SUM(media_count),0) AS media
            FROM chat_messages_stats
            WHERE chat_id=%s AND date >= (CURDATE() - INTERVAL %s DAY)
            """,
            (chat_id, days - 1),
        )
        return cur.fetchone() or {"msgs": 0, "words": 0, "links": 0, "media": 0}


def top_users(chat_id: int, days: int = 7, by: str = "messages") -> List[Dict]:
    col = "messages_count" if by == "messages" else "links_count"
    days = max(1, int(days))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT user_id, MAX(username) AS username, COALESCE(SUM({col}),0) AS c
            FROM chat_messages_stats
            WHERE chat_id=%s AND date >= (CURDATE() - INTERVAL %s DAY)
            GROUP BY user_id
            ORDER BY c DESC
            LIMIT 10
            """,
            (chat_id, days - 1),
        )
        return cur.fetchall() or []


def activity_hours(chat_id: int, days: int = 7) -> List[Dict]:
    days = max(1, int(days))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT hour, COALESCE(SUM(messages_count),0) AS c
            FROM chat_activity_hourly
            WHERE chat_id=%s AND date >= (CURDATE() - INTERVAL %s DAY)
            GROUP BY hour
            ORDER BY hour ASC
            """,
            (chat_id, days - 1),
        )
        return cur.fetchall() or []

