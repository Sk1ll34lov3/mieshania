# -*- coding: utf-8 -*-
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.chat_ai import chat_ai_status_cmd
from handlers.fun import joke_cmd, rps_cmd, slot_cmd
from handlers.schedule import rnd_off, rnd_on
from handlers.stats import stats_7d, top_cmd, top_links_cmd
from handlers.xp import top_xp_cmd
from services.air_alerts import (
    KYIV_DISTRICTS,
    air_districts_text,
    air_status_text,
    get_user_air_districts,
    resolve_district,
    set_air_district,
)

router = Router()


def _menu_markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def main_menu_keyboard() -> None:
    return None


def alerts_menu_keyboard() -> None:
    return None


def downloads_menu_keyboard() -> None:
    return None


def fun_menu_keyboard() -> None:
    return None


def stats_menu_keyboard() -> None:
    return None


def settings_menu_keyboard() -> None:
    return None


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
    await message.answer(
        "Меню доступне командами. Повний список: /help\n"
        "Тривоги: /air_status /air_districts\n"
        "Статистика: /stats /top /top_links /top_xp\n"
        "Завантаження: /get URL або /dl_hd URL"
    )


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
    await joke_cmd(message)


@router.message(F.text == "🎰 Слот")
async def slot_button(message: Message):
    await slot_cmd(message)


@router.message(F.text == "✊ Камінь/ножиці")
async def rps_button(message: Message):
    await rps_cmd(message)


@router.message(F.text == "🔥 Roast")
async def roast_button(message: Message):
    await message.answer("Для roast зроби reply на користувача або використай <code>/roast @user</code>.", reply_markup=fun_menu_keyboard())


@router.message(F.text == "📈 Статистика")
async def stats_menu(message: Message):
    await message.answer("Статистика:", reply_markup=stats_menu_keyboard())


@router.message(F.text == "🏆 Топ XP")
async def top_xp_button(message: Message):
    await top_xp_cmd(message)


@router.message(F.text == "👥 Топ активних")
async def top_active_button(message: Message):
    await top_cmd(message)


@router.message(F.text == "🔗 Топ посилань")
async def top_links_button(message: Message):
    await top_links_cmd(message)


@router.message(F.text == "📊 Статистика")
async def stats_button(message: Message):
    await stats_7d(message)


@router.message(F.text == "⚙️ Налаштування")
async def settings_menu(message: Message):
    await message.answer("Налаштування:", reply_markup=settings_menu_keyboard())


@router.message(F.text == "🤖 AI статус")
async def ai_status_button(message: Message):
    await chat_ai_status_cmd(message)


@router.message(F.text == "🎲 Рандом ON")
async def random_on_button(message: Message):
    await rnd_on(message)


@router.message(F.text == "🎲 Рандом OFF")
async def random_off_button(message: Message):
    await rnd_off(message)


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


async def _edit_menu(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "menu:alerts")
async def alerts_menu_callback(callback: CallbackQuery):
    await _edit_menu(callback, "Меню повітряних тривог:", alerts_menu_keyboard())


@router.callback_query(F.data == "menu:downloads")
async def downloads_menu_callback(callback: CallbackQuery):
    await _edit_menu(
        callback,
        "Надішли посилання на відео — я покажу кнопки завантаження.\n"
        "Або обери режим нижче й введи команду з URL:",
        downloads_menu_keyboard(),
    )


@router.callback_query(F.data == "menu:fun")
async def fun_menu_callback(callback: CallbackQuery):
    await _edit_menu(callback, "Розваги:", fun_menu_keyboard())


@router.callback_query(F.data == "menu:stats")
async def stats_menu_callback(callback: CallbackQuery):
    await _edit_menu(callback, "Статистика:", stats_menu_keyboard())


@router.callback_query(F.data == "menu:settings")
async def settings_menu_callback(callback: CallbackQuery):
    await _edit_menu(callback, "Налаштування:", settings_menu_keyboard())


@router.callback_query(F.data == "menu:help")
async def help_menu_callback(callback: CallbackQuery):
    await _edit_menu(
        callback,
        "Натисни потрібний розділ меню або введи /help для повного списку команд.",
        main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("download:"))
async def download_menu_callback(callback: CallbackQuery):
    mode = (callback.data or "").split(":", 1)[1]
    commands = {"hd": "/dl_hd", "sd": "/dl_sd", "audio": "/dl_audio", "info": "/dl_info"}
    command = commands.get(mode, "/get")
    await _edit_menu(
        callback,
        f"Надішли посилання командою <code>{command} URL</code> або просто надішли URL у чат.",
        downloads_menu_keyboard(),
    )


@router.callback_query(F.data == "fun:joke")
async def joke_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await joke_cmd(callback.message)


@router.callback_query(F.data == "fun:slot")
async def slot_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await slot_cmd(callback.message)


@router.callback_query(F.data == "fun:rps")
async def rps_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await rps_cmd(callback.message)


@router.callback_query(F.data == "fun:roast")
async def roast_menu_callback(callback: CallbackQuery):
    await _edit_menu(
        callback,
        "Для roast зроби reply на користувача або використай <code>/roast @user</code>.",
        fun_menu_keyboard(),
    )


@router.callback_query(F.data == "stats:summary")
async def stats_summary_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await stats_7d(callback.message)


@router.callback_query(F.data == "stats:xp")
async def stats_xp_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await top_xp_cmd(callback.message)


@router.callback_query(F.data == "stats:active")
async def stats_active_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await top_cmd(callback.message)


@router.callback_query(F.data == "stats:links")
async def stats_links_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await top_links_cmd(callback.message)


@router.callback_query(F.data == "settings:ai")
async def ai_status_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await chat_ai_status_cmd(callback.message)


@router.callback_query(F.data == "settings:random_on")
async def random_on_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await rnd_on(callback.message)


@router.callback_query(F.data == "settings:random_off")
async def random_off_menu_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await rnd_off(callback.message)


@router.callback_query(F.data == "settings:morning")
async def morning_menu_callback(callback: CallbackQuery):
    await _edit_menu(
        callback,
        "Використай <code>/morning_on</code>, <code>/morning_off</code> або <code>/morning_time 09:00</code>.",
        settings_menu_keyboard(),
    )


@router.callback_query(F.data == "settings:quiet")
async def quiet_menu_callback(callback: CallbackQuery):
    await _edit_menu(
        callback,
        "Використай <code>/quiet 23:00-08:00</code> або <code>/quiet off</code>.",
        settings_menu_keyboard(),
    )


@router.callback_query(F.data == "air:status")
async def air_status_callback(callback: CallbackQuery):
    await _edit_menu(callback, await air_status_text(), alerts_menu_keyboard())


@router.callback_query(F.data == "air:districts")
async def air_districts_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            await air_districts_text(callback.message.chat.id, callback.from_user.id),
            reply_markup=district_keyboard(callback.message.chat.id, callback.from_user.id),
        )


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
    if callback.message:
        await callback.message.edit_text("Головне меню:", reply_markup=main_menu_keyboard())
