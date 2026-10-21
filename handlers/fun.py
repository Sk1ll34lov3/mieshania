# -*- coding: utf-8 -*-
# handlers/fun.py

import html
import random, re
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils import remember_user, get_chat, extract_mention, resolve_target_and_reason
from services.jokes import pick_joke_maybe_gpt, pick_personal_joke
from services.slap import play_slap, random_opponent, top_slap_players

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


def _slap_name(user_id: int, username: str | None) -> str:
    if username:
        return "@" + html.escape(username.lstrip("@"))
    return f"<a href='tg://user?id={int(user_id)}'>учасник</a>"


@router.message(Command("slap"))
async def slap_cmd(m: Message):
    if not m.from_user:
        return
    remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    target_id, target_username, _ = await resolve_target_and_reason(m, m.bot)
    if target_id is None:
        target = random_opponent(m.chat.id, m.from_user.id)
        if not target:
            return await m.answer(
                "Нема кого лупити. Зроби reply на повідомлення або дочекайся ще одного гравця."
            )
        target_id = int(target["user_id"])
        target_username = target.get("username")
    if int(target_id) == int(m.from_user.id):
        return await m.answer("Сам себе не бий. Зроби reply на іншого гравця.")

    landed = play_slap(
        m.chat.id,
        m.from_user.id,
        m.from_user.username,
        int(target_id),
        target_username,
    )
    attacker = _slap_name(m.from_user.id, m.from_user.username)
    target = _slap_name(int(target_id), target_username)
    if landed:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👊 Вєбати в ответ",
                        callback_data=f"slap:return:{m.from_user.id}",
                    )
                ]
            ]
        )
        await m.answer(
            f"💥 {target}, вас уєбали з ладошкі\nВєбати в ответ?\n\n{attacker} отримує +1 бал",
            reply_markup=keyboard,
        )
    else:
        await m.answer(f"🖐 {attacker} замахнувся на {target}\n🛡 Захистився. +1 бал захиснику")


@router.message(Command("slap_top"))
async def slap_top_cmd(m: Message):
    rows = top_slap_players(m.chat.id)
    if not rows:
        return await m.answer("Топ поки порожній. Напиши /slap і починай роздачу.")
    lines = ["🏆 <b>Топ ладошкі</b>"]
    for index, row in enumerate(rows, 1):
        name = _slap_name(int(row["user_id"]), row.get("username"))
        lines.append(
            f"{index}. {name}  <b>{int(row['points'])}</b> балів "
            f"({int(row['hits'])} влучань, {int(row['blocks'])} захистів)"
        )
    await m.answer("\n".join(lines))


@router.callback_query(F.data.startswith("slap:return:"))
async def slap_return_callback(callback: CallbackQuery):
    if not callback.from_user or not callback.message:
        return await callback.answer()
    try:
        original_attacker_id = int(callback.data.rsplit(":", 1)[1])
    except (AttributeError, ValueError):
        return await callback.answer("Кнопка вже неактивна", show_alert=True)
    if callback.from_user.id == original_attacker_id:
        return await callback.answer("Сам себе не бий", show_alert=True)

    await callback.answer()
    remember_user(
        callback.message.chat.id,
        callback.from_user.id,
        callback.from_user.username,
    )
    landed = play_slap(
        callback.message.chat.id,
        callback.from_user.id,
        callback.from_user.username,
        original_attacker_id,
        None,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    attacker = _slap_name(callback.from_user.id, callback.from_user.username)
    target = _slap_name(original_attacker_id, None)
    if landed:
        await callback.message.answer(
            f"👊 {attacker} вєбав у відповідь {target}\n💥 УЄБАЛО. +1 бал помсти"
        )
    else:
        await callback.message.answer(
            f"🛡 {target} знову захистився від {attacker}\n+😎 Захиснику +1 бал"
        )
