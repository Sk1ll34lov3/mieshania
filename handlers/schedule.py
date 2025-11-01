# -*- coding: utf-8 -*-
# handlers/schedule.py

import asyncio
import random
import time
from datetime import datetime, timedelta, time as dtime, date
from zoneinfo import ZoneInfo
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils import upsert_chat, get_chat, in_quiet
from db import db
from services.jokes import pick_joke_maybe_gpt
from services.air_alerts import air_alert_loop  # фоновий моніторинг тривог

router = Router()

# ---------------- DB setters ----------------
def set_random(chat_id: int, on: bool):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET random_on=%s WHERE chat_id=%s",
            (1 if on else 0, chat_id),
        )

def set_random_window(chat_id: int, mn: int, mx: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET random_min=%s, random_max=%s WHERE chat_id=%s",
            (mn, mx, chat_id),
        )

def set_mode(chat_id: int, mode: str):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE chats SET mode=%s WHERE chat_id=%s", (mode, chat_id))

def set_quiet(chat_id: int, start: str | None, end: str | None):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET quiet_start=%s, quiet_end=%s WHERE chat_id=%s",
            (start, end, chat_id),
        )

def set_morning_on(chat_id: int, on: bool):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET morning_on=%s WHERE chat_id=%s",
            (1 if on else 0, chat_id),
        )

def set_morning_time(chat_id: int, hhmm: str):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET morning_time=%s WHERE chat_id=%s",
            (hhmm, chat_id),
        )

def get_all_morning_chats():
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT chat_id, morning_time FROM chats WHERE morning_on=1")
        return cur.fetchall()

# ---------------- Background loops ----------------
async def random_loop(bot):
    last_sent: dict[int, float] = {}
    while True:
        await asyncio.sleep(20)
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM chats WHERE random_on=1")
            chats = cur.fetchall()
        for ch in chats:
            cid = ch["chat_id"]
            if in_quiet(ch):
                continue
            mn = max(1, int(ch.get("random_min", 60)))
            mx = max(mn, int(ch.get("random_max", 180)))
            interval = random.randint(mn * 60, mx * 60)
            last = last_sent.get(cid, 0.0)
            if time.time() - last >= interval:
                line = await pick_joke_maybe_gpt(cid, ch.get("mode", "pg13"))
                try:
                    await bot.send_message(cid, line)
                    last_sent[cid] = time.time()
                except Exception:
                    pass

async def morning_blast_loop(bot):
    sent_today: dict[int, date] = {}
    tz = ZoneInfo("Europe/Kyiv")
    while True:
        try:
            now = datetime.now(tz)
            rows = get_all_morning_chats()
            for r in rows:
                cid = r["chat_id"]
                hhmm = (r["morning_time"] or "09:00").strip()
                try:
                    hh, mm = int(hhmm[:2]), int(hhmm[3:5])
                except Exception:
                    hh, mm = 9, 0
                should_send = (now.hour == hh and now.minute == mm)
                if should_send and sent_today.get(cid) != now.date():
                    try:
                        await bot.send_message(cid, "ВСІМ ВСТАТИ! ХВИЛИНА МОВЧАННЯ!")
                        sent_today[cid] = now.date()
                    except Exception:
                        pass
            await asyncio.sleep(20)
        except Exception:
            await asyncio.sleep(20)

# ---------------- Commands ----------------
@router.message(Command("random_on"))
async def rnd_on(m: Message):
    upsert_chat(m.chat.id)
    set_random(m.chat.id, True)
    await m.answer("Рандомні вкиди увімкнено ✅")

@router.message(Command("random_off"))
async def rnd_off(m: Message):
    upsert_chat(m.chat.id)
    set_random(m.chat.id, False)
    await m.answer("Рандомні вкиди вимкнено ⛔️")

@router.message(Command("random_window"))
async def rnd_win(m: Message):
    parts = (m.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await m.answer("Використання: <code>/random_window 60 180</code>")
    mn, mx = int(parts[1]), int(parts[2])
    if mn < 1 or mx < mn:
        return await m.answer("Невірний інтервал.")
    upsert_chat(m.chat.id)
    set_random_window(m.chat.id, mn, mx)
    await m.answer(f"Вікно рандому: {mn}-{mx} хв.")

@router.message(Command("mode"))
async def mode_cmd(m: Message):
    parts = (m.text or "").split()
    if len(parts) < 2 or parts[1] not in ("pg13", "r18"):
        return await m.answer("Використання: <code>/mode pg13</code> або <code>/mode r18</code>")
    upsert_chat(m.chat.id)
    set_mode(m.chat.id, parts[1])
    await m.answer(f"Режим: {parts[1].upper()}")

@router.message(Command("quiet"))
async def quiet_cmd(m: Message):
    upsert_chat(m.chat.id)
    parts = (m.text or "").split()
    if len(parts) == 2 and parts[1].lower() == "off":
        set_quiet(m.chat.id, None, None)
        return await m.answer("Quiet hours вимкнено.")
    if len(parts) != 2 or "-" not in parts[1]:
        return await m.answer("Використання: <code>/quiet 23:00-08:00</code> або <code>/quiet off</code>")
    a, b = parts[1].split("-", 1)
    set_quiet(m.chat.id, a, b)
    await m.answer(f"Quiet hours: {a}-{b}")

@router.message(Command("morning_on"))
async def morning_on_cmd(m: Message):
    upsert_chat(m.chat.id)
    set_morning_on(m.chat.id, True)
    await m.answer("Ранковий підйом увімкнено ⏰")

@router.message(Command("morning_off"))
async def morning_off_cmd(m: Message):
    upsert_chat(m.chat.id)
    set_morning_on(m.chat.id, False)
    await m.answer("Ранковий підйом вимкнено 😴")

@router.message(Command("morning_time"))
async def morning_time_cmd(m: Message):
    parts = (m.text or "").split()
    if len(parts) != 2 or not re.match(r"^\d{2}:\d{2}$", parts[1]):
        return await m.answer("Використання: <code>/morning_time 09:00</code>")
    set_morning_time(m.chat.id, parts[1])
    await m.answer(f"Час підйому встановлено: {parts[1]}")

# ---------------- Background starter ----------------
def start_background_tasks(bot):
    loop = asyncio.get_event_loop()
    loop.create_task(random_loop(bot))
    loop.create_task(morning_blast_loop(bot))

    # підключаємо моніторинг повітряних тривог тільки якщо є токен
    from config import ALERTS_TOKEN
    if ALERTS_TOKEN:
        loop.create_task(air_alert_loop(bot))

    print("[schedule] Background tasks started.")
