from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration as hd
from utils import remember_user, is_chat_admin, resolve_target_and_reason, restrict_for_minutes
from db import db

router = Router()

async def ensure_admin(m: Message) -> bool:
    if not await is_chat_admin(m.bot, m.chat.id, m.from_user.id):
        await m.answer("Тільки для адмінів.")
        return False
    return True

def get_mod(chat_id: int, user_id: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM user_moderation WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO user_moderation (chat_id, user_id) VALUES (%s,%s)", (chat_id, user_id))
            return {"chat_id": chat_id, "user_id": user_id, "warns": 0, "muted_until": None, "notes": None}
        return row

def set_warns(chat_id: int, user_id: int, warns: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE user_moderation SET warns=%s WHERE chat_id=%s AND user_id=%s", (warns, chat_id, user_id))

@router.message(Command("warn"))
async def warn_cmd(m: Message):
    if not await ensure_admin(m): return
    if m.from_user: remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    uid, uname, reason = await resolve_target_and_reason(m, m.bot)
    if not uid:
        return await m.answer(("Не знайшов ID для @" + (uname or "") + ". ") + "Зроби реплай або нехай користувач хоч раз напише у чат.")
    row = get_mod(m.chat.id, uid)
    warns = int(row["warns"]) + 1
    set_warns(m.chat.id, uid, warns)
    msg = f"Варн #{warns} для <a href='tg://user?id={uid}'>користувача</a>."
    if reason: msg += f" Причина: {hd.quote(reason)}"
    if warns >= 3:
        await restrict_for_minutes(m.bot, m.chat.id, uid, 30)
        set_warns(m.chat.id, uid, 0)
        msg += "\nДосягнуто 3 варни → автомута на 30 хв."
    await m.answer(msg)

@router.message(Command("mute"))
async def mute_cmd(m: Message):
    if not await ensure_admin(m): return
    uid, uname, reason = await resolve_target_and_reason(m, m.bot)
    minutes = 15
    parts = (m.text or "").split()
    if len(parts) >= 3 and parts[-1].isdigit():
        minutes = max(1, int(parts[-1]))
    if not uid:
        return await m.answer(("Не знайшов ID для @" + (uname or "") + ". ") + "Зроби реплай або нехай користувач хоч раз напише у чат.")
    await restrict_for_minutes(m.bot, m.chat.id, uid, minutes)
    await m.answer(f"Зам'ютив на {minutes} хв: <a href='tg://user?id={uid}'>користувача</a>")

@router.message(Command("unmute"))
async def unmute_cmd(m: Message):
    if not await ensure_admin(m): return
    from aiogram.types import ChatPermissions
    uid, uname, reason = await resolve_target_and_reason(m, m.bot)
    if not uid:
        return await m.answer(("Не знайшов ID для @" + (uname or "") + ". ") + "Зроби реплай або нехай користувач хоч раз напише у чат.")
    await m.bot.restrict_chat_member(
        m.chat.id, uid,
        permissions=ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE user_moderation SET muted_until=NULL WHERE chat_id=%s AND user_id=%s", (m.chat.id, uid))
    await m.answer(f"Знято mute з <a href='tg://user?id={uid}'>користувача</a>")

@router.message(Command("ban"))
async def ban_cmd(m: Message):
    if not await ensure_admin(m): return
    uid, uname, reason = await resolve_target_and_reason(m, m.bot)
    if not uid:
        return await m.answer(("Не знайшов ID для @" + (uname or "") + ". ") + "Зроби реплай або нехай користувач хоч раз напише у чат.")
    await m.bot.ban_chat_member(m.chat.id, uid)
    msg = f"Забанено: <a href='tg://user?id={uid}'>користувача</a>."
    if reason: msg += f" Причина: {hd.quote(reason)}"
    await m.answer(msg)

@router.message(Command("kick"))
async def kick_cmd(m: Message):
    if not await ensure_admin(m): return
    uid, uname, reason = await resolve_target_and_reason(m, m.bot)
    if not uid:
        return await m.answer(("Не знайшов ID для @" + (uname or "") + ". ") + "Зроби реплай або нехай користувач хоч раз напише у чат.")
    await m.bot.ban_chat_member(m.chat.id, uid)
    await m.bot.unban_chat_member(m.chat.id, uid, only_if_banned=True)
    await m.answer(f"Кікнуто: <a href='tg://user?id={uid}'>користувача</a>")
