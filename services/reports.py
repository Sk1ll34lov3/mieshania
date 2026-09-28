# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict, List, Optional

from db import db


def create_report(
    chat_id: int,
    reported_message_id: int,
    reported_user_id: int,
    reported_username: str | None,
    reporter_user_id: int,
    reporter_username: str | None,
    reason: str | None,
) -> int:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports
              (chat_id, reported_message_id, reported_user_id, reported_username,
               reporter_user_id, reporter_username, reason, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'new')
            """,
            (
                chat_id,
                int(reported_message_id),
                int(reported_user_id),
                reported_username,
                int(reporter_user_id),
                reporter_username,
                reason,
            ),
        )
        return int(cur.lastrowid or 0)


def list_reports(chat_id: int, limit: int = 10) -> List[Dict]:
    limit = max(1, min(50, int(limit)))
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, reported_message_id, reported_user_id, reported_username,
                   reporter_user_id, reporter_username, reason, status, created_at
            FROM reports
            WHERE chat_id=%s
            ORDER BY id DESC
            LIMIT %s
            """,
            (chat_id, limit),
        )
        return cur.fetchall() or []


def set_report_status(chat_id: int, report_id: int, status: str) -> int:
    st = (status or "").lower()
    if st not in ("reviewed", "rejected", "actioned"):
        raise ValueError("bad status")
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE reports SET status=%s WHERE chat_id=%s AND id=%s",
            (st, chat_id, int(report_id)),
        )
        return int(cur.rowcount or 0)

