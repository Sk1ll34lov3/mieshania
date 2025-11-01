# -*- coding: utf-8 -*-
# handlers/fun.py

import random, re
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils import remember_user, get_chat, extract_mention
from services.jokes import pick_joke_maybe_gpt, pick_personal_joke

router = Router()

@router.message(Command("joke"))
async def joke_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    ch = get_chat(m.chat.id) or {}
    mode = (ch.get("mode") or "pg13").lower()
    line = await pick_joke_maybe_gpt(m.chat.id, mode)
    await m.answer(line)

@router.message(Command("roast"))
async def roast_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)

    uid, uname = extract_mention(m)  # returns (user_id, username|None)

    if not uid and not uname:
        return await m.answer("Кого? Використай: <code>/roast @username</code>")

# name to substitute into the pattern
    name_for_template = (uname or "").lstrip("@") or "ти"
    line = pick_personal_joke(m.chat.id, name_for_template)

# target for response (HTML is already enabled in the bot in Bot(..., parse_mode=HTML))
    target = f"@{uname}" if uname else f"<a href='tg://user?id={uid}'>ти</a>"
    await m.answer(f"{target}, {line}")

@router.message(Command("dice"))
async def dice_cmd(m: Message):
    await m.bot.send_dice(m.chat.id)

@router.message(Command("coin"))
async def coin_cmd(m: Message):
    await m.answer(random.choice(["Орел", "Решка"]))

@router.message(Command("roll"))
async def roll_cmd(m: Message):
    parts = (m.text or "").split(" ", 1)
    if len(parts) == 1:
        dmsg = await m.bot.send_dice(m.chat.id)
        val = dmsg.dice.value if dmsg and dmsg.dice else "?"
        return await m.answer(f"1d6 → <b>{val}</b>")
    mobj = re.match(r"^\s*(\d+)\s*d\s*(\d+)\s*$", parts[1], re.I)
    if not mobj:
        return await m.answer("Формат: <code>/roll</code> або <code>/roll 2d20</code>")
    n, d = max(1, int(mobj.group(1))), max(2, int(mobj.group(2)))
    n = min(n, 50); d = min(d, 1000)
    rolls = [random.randint(1, d) for _ in range(n)]
    s = sum(rolls)
    short = rolls if n <= 10 else (rolls[:10] + ["…"])
    await m.answer(f"{n}d{d}: {short} = <b>{s}</b>")

@router.message(Command("rps"))
async def rps_cmd(m: Message):
    choices = ["камінь", "ножиці", "папір"]
    p1, p2 = random.choice(choices), random.choice(choices)
    def result(a, b):
        if a == b: return "нічия"
        win = {("камінь","ножиці"), ("ножиці","папір"), ("папір","камінь")}
        return "ти виграв" if (a, b) in win else "ти програв"
    await m.answer(f"Ти: <b>{p1}</b> vs бот: <b>{p2}</b> → {result(p1,p2)}")

@router.message(Command("slot"))
async def slot_cmd(m: Message):
    await m.bot.send_dice(m.chat.id, emoji="🎰")
