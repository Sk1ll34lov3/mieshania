from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from utils import upsert_chat, remember_user
from downloader import download_url, is_supported
from services.limits import is_download_allowed, record_download
from services.settings import get_chat_settings
from utils import is_chat_admin
from services.xp import add_download
import html

router = Router()

@router.message(Command("start","help"))
async def help_cmd(m: Message):
    upsert_chat(m.chat.id)
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    txt = (
        "<b>МЄШАНЯ 2.0</b> — краща з худших.\n"
        "Команди:\n"
        "<code>/ping</code> — перевірка\n"
        "<code>/id</code> — показати chat_id\n"
        "<code>/get URL</code> — скачати відео (YouTube/TikTok/Instagram)\n"
        "<code>/dl_hd URL</code> — HD\n"
        "<code>/dl_sd URL</code> — SD\n"
        "<code>/dl_audio URL</code> — AUDIO\n"
        "<code>/dl_info URL</code> — інформація\n"
        "<code>/joke</code> — чорний жарт\n"
        "<code>/roast @user</code> — підкол\n"
        "<code>/rps @user</code> — камінь/ножиці/папір\n"
        "<code>/slot</code> — автомати 🎰\n"
        "<code>/save</code> (reply) — зберегти повідомлення\n"
        "<code>/saved</code> — останні збережені\n"
        "<code>/rank</code> — рівень/XP\n"
        "<code>/top_xp</code> — топ XP\n"
        "<code>/stats</code> — статистика 7 днів\n"
        "<code>/stats_today</code> — статистика за сьогодні\n"
        "<code>/top</code> — топ активних\n"
        "<code>/top_links</code> — топ посилань\n"
        "<code>/report причина</code> (reply) — репорт\n"
        "<code>/settings</code> — налаштування чату\n"
        "\n<b>Режими/розклад:</b>\n"
        "<code>/random_on</code> | <code>/random_off</code>\n"
        "<code>/random_window 60 180</code>\n"
        "<code>/mode pg13</code> | <code>/mode r18</code>\n"
        "<code>/quiet 23:00-08:00</code> | <code>/quiet off</code>\n"
        "<code>/morning_on</code> | <code>/morning_off</code> | <code>/morning_time 09:00</code>\n"
        "\n<b>Тривоги:</b>\n"
        "<code>/air_on_kyiv</code> | <code>/air_off_kyiv</code>\n"
        "<code>/air_on_region</code> | <code>/air_off_region</code>\n"
        "<code>/air_status</code>\n"
        "\n<b>Модерація (для адмінів):</b>\n"
        "<code>/warn @user [причина]</code>, <code>/mute @user [хв]</code>, <code>/unmute @user</code>,\n"
        "<code>/ban @user</code>, <code>/kick @user</code>\n"
        "\nЯкщо в чаті кинути лінк — покажу кнопки для завантаження (HD/SD/AUDIO/FILE)."
    )
    await m.answer(txt)

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
    s = get_chat_settings(m.chat.id)
    if not s.get("media_enabled"):
        return await m.answer("Медіа-функції вимкнені в цьому чаті.")
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        allowed, *_ = is_download_allowed(m.chat.id, m.from_user.id)
        if not allowed:
            return await m.answer("Забагато завантажень. Спробуй трохи пізніше.")
        record_download(m.chat.id, m.from_user.id, action="get")
    await m.answer("Секунду, тягну відео…")
    try:
        await download_url(m.chat.id, url, m.bot)
        try:
            if m.from_user:
                add_download(m.chat.id, m.from_user.id, m.from_user.username)
        except Exception:
            pass
    except Exception as e:
        err = html.escape(str(e))[:1500]
        await m.answer(f"Не вийшло завантажити: <code>{err}</code>")
