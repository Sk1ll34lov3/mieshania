# -*- coding: utf-8 -*-
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from services.air_alerts import (
    KYIV_DISTRICTS,
    air_districts_text,
    air_status_text,
    get_user_air_districts,
    resolve_district,
    set_air_district,
)

router = Router()


def _row(builder: ReplyKeyboardBuilder, *labels: str) -> None:
    builder.row(*(KeyboardButton(text=label) for label in labels))


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(
        builder,
        "🚨 Повітряні тривоги",
        "📥 Завантаження",
    )
    _row(
        builder,
        "🎮 Розваги",
        "📈 Статистика",
    )
    _row(
        builder,
        "⚙️ Налаштування",
        "📖 Допомога",
    )
    return builder.as_markup(resize_keyboard=True)


def alerts_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(builder, "📊 Статус тривог", "🗺 Райони Київщини")
    _row(builder, "🔔 Мої підписки", "🏠 Головне меню")
    return builder.as_markup(resize_keyboard=True)


def downloads_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(builder, "🎥 HD", "🎞 SD", "🎵 Аудіо")
    _row(builder, "ℹ️ Інфо про файл", "🏠 Головне меню")
    return builder.as_markup(resize_keyboard=True)


def fun_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(builder, "😂 Жарт", "🎰 Слот", "✊ Камінь/ножиці")
    _row(builder, "🔥 Roast", "🏠 Головне меню")
    return builder.as_markup(resize_keyboard=True)


def stats_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(builder, "📊 Статистика", "🏆 Топ XP")
    _row(builder, "👥 Топ активних", "🔗 Топ посилань")
    _row(builder, "🏠 Головне меню")
    return builder.as_markup(resize_keyboard=True)


def settings_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    _row(builder, "🤖 AI статус", "🎲 Рандом ON", "🎲 Рандом OFF")
    _row(builder, "⏰ Ранковий будильник", "🌙 Тихі години")
    _row(builder, "🏠 Головне меню")
    return builder.as_markup(resize_keyboard=True)


def district_keyboard(chat_id: int, user_id: int):
    subscribed = get_user_air_districts(chat_id, user_id)
    builder = InlineKeyboardBuilder()
    for uid, name, _ in KYIV_DISTRICTS:
        mark = "✅" if uid in subscribed else "⬜"
        builder.button(text=f"{mark} {name}", callback_data=f"air:toggle:{uid}")
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="🔄 Оновити", callback_data="air:refresh"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main"),
    )
    return builder.as_markup()


async def send_districts(message: Message):
    await message.answer(
        await air_districts_text(message.chat.id, message.from_user.id),
        reply_markup=district_keyboard(message.chat.id, message.from_user.id),
    )


@router.message(Command("menu"))
async def menu_command(message: Message):
    await message.answer("Головне меню:", reply_markup=main_menu_keyboard())


@router.message(F.text == "🚨 Повітряні тривоги")
async def alerts_menu(message: Message):
    await message.answer("Меню повітряних тривог:", reply_markup=alerts_menu_keyboard())


@router.message(F.text == "📊 Статус тривог")
async def alerts_status_button(message: Message):
    await message.answer(await air_status_text(), reply_markup=alerts_menu_keyboard())


@router.message(F.text.in_({"🗺 Райони Київщини", "🔔 Мої підписки"}))
async def districts_button(message: Message):
    await send_districts(message)


@router.message(F.text == "📥 Завантаження")
async def downloads_menu(message: Message):
    await message.answer(
        "Надішли посилання на відео — я покажу кнопки завантаження.\n"
        "Або обери режим і потім введи команду з URL:",
        reply_markup=downloads_menu_keyboard(),
    )


@router.message(F.text == "🎥 HD")
async def download_hd_button(message: Message):
    await message.answer("Використай: <code>/dl_hd URL</code>", reply_markup=downloads_menu_keyboard())


@router.message(F.text == "🎞 SD")
async def download_sd_button(message: Message):
    await message.answer("Використай: <code>/dl_sd URL</code>", reply_markup=downloads_menu_keyboard())


@router.message(F.text == "🎵 Аудіо")
async def download_audio_button(message: Message):
    await message.answer("Використай: <code>/dl_audio URL</code>", reply_markup=downloads_menu_keyboard())


@router.message(F.text == "ℹ️ Інфо про файл")
async def download_info_button(message: Message):
    await message.answer("Використай: <code>/dl_info URL</code>", reply_markup=downloads_menu_keyboard())


@router.message(F.text == "🎮 Розваги")
async def fun_menu(message: Message):
    await message.answer("Розваги:", reply_markup=fun_menu_keyboard())


@router.message(F.text == "😂 Жарт")
async def joke_button(message: Message):
    await message.answer("Використай команду <code>/joke</code>.", reply_markup=fun_menu_keyboard())


@router.message(F.text == "🎰 Слот")
async def slot_button(message: Message):
    await message.answer("Використай команду <code>/slot</code>.", reply_markup=fun_menu_keyboard())


@router.message(F.text == "✊ Камінь/ножиці")
async def rps_button(message: Message):
    await message.answer("Використай команду <code>/rps</code>.", reply_markup=fun_menu_keyboard())


@router.message(F.text == "🔥 Roast")
async def roast_button(message: Message):
    await message.answer("Використай команду <code>/roast @user</code>.", reply_markup=fun_menu_keyboard())


@router.message(F.text == "📈 Статистика")
async def stats_menu(message: Message):
    await message.answer("Статистика:", reply_markup=stats_menu_keyboard())


@router.message(F.text == "🏆 Топ XP")
async def top_xp_button(message: Message):
    await message.answer("Використай команду <code>/top_xp</code>.", reply_markup=stats_menu_keyboard())


@router.message(F.text == "👥 Топ активних")
async def top_active_button(message: Message):
    await message.answer("Використай команду <code>/top</code>.", reply_markup=stats_menu_keyboard())


@router.message(F.text == "🔗 Топ посилань")
async def top_links_button(message: Message):
    await message.answer("Використай команду <code>/top_links</code>.", reply_markup=stats_menu_keyboard())


@router.message(F.text == "⚙️ Налаштування")
async def settings_menu(message: Message):
    await message.answer("Налаштування:", reply_markup=settings_menu_keyboard())


@router.message(F.text == "🤖 AI статус")
async def ai_status_button(message: Message):
    await message.answer("Використай команду <code>/chat_ai_status</code>.", reply_markup=settings_menu_keyboard())


@router.message(F.text == "🎲 Рандом ON")
async def random_on_button(message: Message):
    await message.answer("Використай команду <code>/random_on</code>.", reply_markup=settings_menu_keyboard())


@router.message(F.text == "🎲 Рандом OFF")
async def random_off_button(message: Message):
    await message.answer("Використай команду <code>/random_off</code>.", reply_markup=settings_menu_keyboard())


@router.message(F.text == "⏰ Ранковий будильник")
async def morning_button(message: Message):
    await message.answer(
        "Використай <code>/morning_on</code>, <code>/morning_off</code> або <code>/morning_time 09:00</code>.",
        reply_markup=settings_menu_keyboard(),
    )


@router.message(F.text == "🌙 Тихі години")
async def quiet_button(message: Message):
    await message.answer("Використай <code>/quiet 23:00-08:00</code> або <code>/quiet off</code>.", reply_markup=settings_menu_keyboard())


@router.message(F.text == "📖 Допомога")
async def help_button(message: Message):
    await message.answer("Натисни потрібний розділ меню або введи /help для повного списку команд.", reply_markup=main_menu_keyboard())


@router.message(F.text == "🏠 Головне меню")
async def home_button(message: Message):
    await message.answer("Головне меню:", reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("air:"))
async def district_callback(callback: CallbackQuery):
    data = callback.data or ""
    if data == "air:refresh":
        await callback.answer("Оновлюю")
        await callback.message.edit_text(
            await air_districts_text(callback.message.chat.id, callback.from_user.id),
            reply_markup=district_keyboard(callback.message.chat.id, callback.from_user.id),
        )
        return

    parts = data.split(":")
    if len(parts) != 3 or parts[1] != "toggle":
        await callback.answer("Невідома дія", show_alert=True)
        return

    district = resolve_district(parts[2])
    if district is None:
        await callback.answer("Район не знайдено", show_alert=True)
        return
    district_uid, district_name = district
    subscribed = get_user_air_districts(callback.message.chat.id, callback.from_user.id)
    enabled = district_uid not in subscribed
    set_air_district(callback.message.chat.id, callback.from_user.id, district_uid, district_name, enabled)
    await callback.answer("Сповіщення увімкнено" if enabled else "Сповіщення вимкнено")
    await callback.message.edit_reply_markup(
        reply_markup=district_keyboard(callback.message.chat.id, callback.from_user.id)
    )


@router.callback_query(F.data == "menu:main")
async def menu_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Головне меню:", reply_markup=main_menu_keyboard())
