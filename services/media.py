# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import List, Optional

from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from downloader import is_supported


URL_RE = re.compile(r"(https?://\S+)", re.I)


def extract_urls(m: Message) -> List[str]:
    urls: List[str] = []

    def _from_text(text: Optional[str], entities):
        if not text:
            return
        if entities:
            for e in entities:
                if e.type == "text_link" and getattr(e, "url", None):
                    urls.append(e.url)
                elif e.type == "url":
                    s, eoff = e.offset, e.offset + e.length
                    urls.append(text[s:eoff])
        for u in URL_RE.findall(text):
            urls.append(u)

    _from_text(m.text, m.entities)
    _from_text(m.caption, m.caption_entities)

    # normalize/dedupe
    seen = set()
    out: List[str] = []
    for u in [u.strip().strip(".,);]").strip().replace("\u200b", "").replace("\u2060", "") for u in urls]:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def media_action_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎥 HD", callback_data="dl:hd")
    kb.button(text="📉 SD", callback_data="dl:sd")
    kb.button(text="🎵 AUDIO", callback_data="dl:audio")
    kb.button(text="📁 FILE", callback_data="dl:file")
    kb.adjust(2, 2)
    return kb.as_markup()


def pick_first_supported_url(m: Message) -> Optional[str]:
    for u in extract_urls(m):
        if is_supported(u):
            return u
    return None
