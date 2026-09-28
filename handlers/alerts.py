# -*- coding: utf-8 -*-
# handlers/alerts.py

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils import is_chat_admin
from services.air_alerts import (   
    set_air_city,
    set_air_region,
    air_status_text,
    air_districts_text,
    resolve_district,
    set_air_district,
)
from handlers.menu import district_keyboard

router = Router()

# ----------------------- Helpers -----------------------
async def ensure_admin(m: Message) -> bool:
    """Перевіряє, чи є користувач адміном у чаті."""
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("⛔️ Ця команда лише для адміністраторів.")
        return False
    return True

# ----------------------- Commands -----------------------
@router.message(Command("air_on_kyiv"))
async def air_on_city(m: Message):
    if not await ensure_admin(m):
        return
    set_air_city(m.chat.id, True)
    await m.answer("✅ Увімкнув сповіщення про тривогу для м. Київ.")

@router.message(Command("air_off_kyiv"))
async def air_off_city(m: Message):
    if not await ensure_admin(m):
        return
    set_air_city(m.chat.id, False)
    await m.answer("⛔️ Вимкнув сповіщення для м. Київ.")

@router.message(Command("air_on_region"))
async def air_on_region(m: Message):
    if not await ensure_admin(m):
        return
    set_air_region(m.chat.id, True)
    await m.answer("✅ Увімкнув сповіщення для Київської області (вкл. Бучанський р-н).")

@router.message(Command("air_off_region"))
async def air_off_region(m: Message):
    if not await ensure_admin(m):
        return
    set_air_region(m.chat.id, False)
    await m.answer("⛔️ Вимкнув сповіщення для Київської області.")

@router.message(Command("air_status"))
async def air_status(m: Message):
    """Показує поточний стан тривоги."""
    txt = await air_status_text()
    await m.answer(txt)


@router.message(Command("air_districts"))
async def air_districts(m: Message):
    """Показує районні підписки користувача та поточний стан районів."""
    await m.answer(
        await air_districts_text(m.chat.id, m.from_user.id),
        reply_markup=district_keyboard(m.chat.id, m.from_user.id),
    )


async def _set_district_subscription(m: Message, on: bool):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) != 2:
        command = "air_district_on" if on else "air_district_off"
        return await m.answer(f"Використання: <code>/{command} 75</code> або назва району.")

    district = resolve_district(parts[1])
    if district is None:
        return await m.answer("Не знайшов район. Виконай <code>/air_districts</code>, щоб побачити список і UID.")

    district_uid, district_name = district
    set_air_district(m.chat.id, m.from_user.id, district_uid, district_name, on)
    action = "увімкнено" if on else "вимкнено"
    await m.answer(f"✅ Особисті сповіщення для {district_name}: {action}.")


@router.message(Command("air_district_on"))
async def air_district_on(m: Message):
    await _set_district_subscription(m, True)


@router.message(Command("air_district_off"))
async def air_district_off(m: Message):
    await _set_district_subscription(m, False)
