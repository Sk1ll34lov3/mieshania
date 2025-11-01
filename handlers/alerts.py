# -*- coding: utf-8 -*-
# handlers/alerts.py

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils import is_chat_admin
from services.air_alerts import (   # ✅ новий правильний імпорт
    set_air_city,
    set_air_region,
    air_status_text,
)

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
