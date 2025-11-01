import re
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from utils import remember_user

router = Router()

@router.message(F.text.regexp(re.compile(r"^(кто|хто)\s+создател[ья]\s*[\?\!]+$", re.I)))
async def creator_answer(m: Message):
    if m.from_user:
        remember_user(m.chat.id, m.from_user.id, m.from_user.username)
    await m.answer("НАС ВСІХ СТВОРИВ @lambork!!!!!")

@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated):
    try:
        new_status = update.new_chat_member.status
        if new_status in ("member", "administrator", "creator"):
            await update.bot.send_message(update.chat.id, "ОПАПА ХАТА ХТО БУДЄТ ТРАХАТЬСЯ?")
    except Exception:
        pass

@router.message()
async def mute_guard_and_autodl(m: Message):
    from utils import is_muted_now
    from aiogram.types import MessageEntity
    from downloader import is_supported, download_url
    try:
        if m.from_user:
            remember_user(m.chat.id, m.from_user.id, m.from_user.username)
        if getattr(m, "reply_to_message", None) and m.reply_to_message.from_user:
            u = m.reply_to_message.from_user
            remember_user(m.chat.id, u.id, u.username)
    except Exception:
        pass
    try:
        if m.from_user and is_muted_now(m.chat.id, m.from_user.id):
            try:
                await m.bot.delete_message(m.chat.id, m.message_id)
            except Exception:
                pass
            return
    except Exception:
        pass
    if (m.text or "").startswith('/'):
        return
    URLs = []
    def _from_text(text, entities):
        if not text: return
        if entities:
            for e in entities:
                if e.type == "text_link" and getattr(e, "url", None):
                    URLs.append(e.url)
                elif e.type == "url":
                    s, eoff = e.offset, e.offset + e.length
                    URLs.append(text[s:eoff])
        import re
        for u in re.findall(r'(https?://\S+)', text, flags=re.I):
            URLs.append(u)
    _from_text(m.text, m.entities)
    _from_text(m.caption, m.caption_entities)
    seen, out = set(), []
    for u in [u.strip().strip('.,);]').strip().replace("\u200b","").replace("\u2060","") for u in URLs]:
        if u not in seen:
            seen.add(u); out.append(u)
    for url in out:
        if not is_supported(url):
            continue
        await m.answer("Секунду, тягну відео…")
        try:
            await download_url(m.chat.id, url, m.bot)
        except Exception:
            await m.answer("Не вийшло витягнути відео. Спробуй інше посилання.")
