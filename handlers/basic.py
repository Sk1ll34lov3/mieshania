import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from downloader import download_url, is_supported
from utils import remember_user, upsert_chat
from handlers.menu import main_menu_keyboard

router = Router()


@router.message(Command("start", "help"))
async def help_cmd(m: Message):
    upsert_chat(m.chat.id)
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    txt = (
        "<b>МЄШАНЯ 2.0</b> на місці.\n"
        "Я новий МЄШАНЯ і ось що вмію:\n"
        "<code>/ping</code> — перевірка\n"
        "<code>/id</code> — показати chat_id\n"
        "<code>/get URL</code> — скачати відео з YouTube/TikTok/Instagram\n"
        "<code>/joke</code> — жарт\n"
        "<code>/roast @user</code> — підкол\n"
        "<code>/rps</code> — камінь/ножиці/папір\n"
        "<code>/slot</code> — автомат\n"
        "<code>/chat_ai_on</code> | <code>/chat_ai_off</code>\n"
        "<code>/chat_ai_intensity 20</code> | <code>/chat_ai_status</code>\n"
        "\n<b>Режими і розклад:</b>\n"
        "<code>/random_on</code> | <code>/random_off</code>\n"
        "<code>/random_window 60 180</code>\n"
        "<code>/mode pg13</code> | <code>/mode r18</code>\n"
        "<code>/quiet 23:00-08:00</code> | <code>/quiet off</code>\n"
        "<code>/morning_on</code> | <code>/morning_off</code> | <code>/morning_time 09:00</code>\n"
        "\n<b>Тривоги:</b>\n"
        "<code>/air_on_kyiv</code> | <code>/air_off_kyiv</code>\n"
        "<code>/air_on_region</code> | <code>/air_off_region</code>\n"
        "<code>/air_status</code>\n"
        "<code>/air_districts</code> — райони та мої підписки\n"
        "<code>/air_district_on 75</code> | <code>/air_district_off 75</code>\n"
        "\n<b>Модерація:</b>\n"
        "<code>/warn @user [причина]</code>\n"
        "<code>/mute @user [хв]</code>\n"
        "<code>/unmute @user</code>\n"
        "<code>/ban @user</code>\n"
        "<code>/kick @user</code>\n"
        "\nПосилання з YouTube/TikTok/Instagram я теж ловлю автоматично.\n"
        "\nСилами і православними стараніями від @stgroupua та @radchenkoleh"
    )
    await m.answer(txt, reply_markup=main_menu_keyboard())


@router.message(Command("ping"))
async def ping_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    await m.answer("pong")


@router.message(Command("id"))
async def id_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    await m.answer(f"chat_id: <code>{m.chat.id}</code>")


@router.message(Command("get"))
async def get_cmd(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Використай: /get <url>")
    url = parts[1].strip()
    if not is_supported(url):
        return await m.answer("Підтримую: YouTube, TikTok, Instagram (публічні).")
    await m.answer("Секунду, тягну відео…")
    try:
        await download_url(m.chat.id, url, m.bot)
    except Exception as e:
        err = html.escape(str(e))[:1500]
        await m.answer(f"Не вийшло завантажити: <code>{err}</code>")
