import re
from datetime import datetime, time as dtime
from aiogram.types import Message, ChatPermissions
from config import ADMINS
from db import db

MENTION_RE = re.compile(r'@([A-Za-z0-9_]{2,})')

def upsert_chat(chat_id: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute("INSERT IGNORE INTO chats (chat_id) VALUES (%s)", (chat_id,))

def get_chat(chat_id: int):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM chats WHERE chat_id=%s", (chat_id,))
        return cur.fetchone()

def remember_user(chat_id: int, user_id: int, username: str|None):
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user_map (chat_id, user_id, username)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username = VALUES(username),
                last_seen = CURRENT_TIMESTAMP
        """, (chat_id, user_id, username))

def resolve_username_to_id(chat_id: int, uname: str):
    with db() as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT user_id FROM user_map
          WHERE chat_id=%s AND username=%s
          ORDER BY last_seen DESC
          LIMIT 1
        """, (chat_id, uname))
        row = cur.fetchone()
        return int(row["user_id"]) if row else None

def extract_mention(m: Message):
    uid = None
    uname = None
    if m.entities:
        for e in m.entities:
            if e.type == "text_mention" and e.user:
                uid = e.user.id; uname = e.user.username; return uid, uname
            if e.type == "mention":
                start, end = e.offset, e.offset + e.length
                uname = (m.text or "")[start + 1:end]; return None, uname
    m2 = MENTION_RE.search(m.text or "")
    if m2: uname = m2.group(1)
    return uid, uname

def is_local_admin(user_id: int) -> bool:
    return user_id in ADMINS

async def is_chat_admin(bot, chat_id: int, user_id: int) -> bool:
    if is_local_admin(user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False

def _after_command_text(m: Message) -> str:
    t = (m.text or "").lstrip()
    sp = t.find(' ')
    return t[sp+1:].strip() if sp != -1 else ""

async def resolve_target_and_reason(m: Message, bot) -> tuple[int|None, str|None, str]:
    if getattr(m, "reply_to_message", None) and m.reply_to_message.from_user:
        target = m.reply_to_message.from_user
        return target.id, (target.username or None), _after_command_text(m)
    if m.entities:
        for e in m.entities:
            if e.type == "text_mention" and e.user:
                end = e.offset + e.length
                reason = (m.text or "")[end:].strip() if m.text else ""
                return e.user.id, (e.user.username or None), reason
    args = _after_command_text(m)
    if args:
        mu = re.search(r'@([A-Za-z0-9_]{2,})', args)
        if mu:
            uname = mu.group(1)
            reason = (args[:mu.start()] + args[mu.end():]).strip()
            uid = resolve_username_to_id(m.chat.id, uname)
            if uid: return uid, uname, reason
            return None, uname, reason
        first = args.split()[0]
        if re.fullmatch(r"\d{5,}", first):
            uid = int(first)
            reason = args[len(first):].strip()
            return uid, None, reason
    return None, None, ""

def in_quiet(chat_row) -> bool:
    qs, qe = chat_row.get("quiet_start"), chat_row.get("quiet_end")
    if not qs or not qe: return False
    try:
        nowt = datetime.now().time()
        s = dtime(int(qs[:2]), int(qs[3:5]))
        e = dtime(int(qe[:2]), int(qe[3:5]))
        if s <= e: return s <= nowt <= e
        else: return nowt >= s or nowt <= e
    except Exception:
        return False

def is_muted_now(chat_id: int, user_id: int) -> bool:
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT muted_until FROM user_moderation WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
        row = cur.fetchone()
        if not row or not row.get("muted_until"): return False
        try:
            from datetime import datetime as _dt
            return _dt.utcnow() < row["muted_until"]
        except Exception:
            return False

async def restrict_for_minutes(bot, chat_id: int, user_id: int, minutes: int):
    from datetime import datetime, timedelta
    until = datetime.utcnow() + timedelta(minutes=minutes)
    await bot.restrict_chat_member(
        chat_id, user_id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=until
    )
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE user_moderation SET muted_until=%s WHERE chat_id=%s AND user_id=%s",
                    (until, chat_id, user_id))
