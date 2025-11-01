# -*- coding: utf-8 -*-
# services/joke.py

from __future__ import annotations
import asyncio, random, html
from typing import List, Optional

from config import (
    OPENAI_API_KEY,
    GPT_JOKES_ON,

)
from db import db

# ---- дефолти  ----
try:
    from config import GPT_JOKES_MODEL
except Exception:
    GPT_JOKES_MODEL = "gpt-4o-mini"
try:
    from config import GPT_JOKES_TEMP
except Exception:
    GPT_JOKES_TEMP = 0.9
try:
    from config import GPT_JOKES_PROB
except Exception:
    GPT_JOKES_PROB = 0.6  #ймов

# ---- локальний пул ----
JOKES_PG13 = [
    "Світло в кінці тунелю — то монітор із продом. Закрий ноут.",
    "План дня: 1) кава 2) паніка 3) імпровізація.",
    "Коли CI червоний — спить лише совість.",
]
JOKES_R18 = [
    "Мій гумор чорніший за логи після релізу у п’ятницю.",
    "Життя дало лимони — зроби ґан-панч і не пінгуй мене до ранку.",
]

# ---- утиліти ----
def _weighted_pool_from_db(sql: str, params: tuple = ()) -> List[str]:
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except Exception:
        rows = []
    pool: List[str] = []
    for r in rows:
        w = 1
        try:
            w = max(1, int(r.get("weight", 1)))
        except Exception:
            pass
        pool.extend([r["text"]] * w)
    return pool

# ---- звичайний жарт ----
def pick_joke(chat_id: int, mode: str) -> str:
    pool = _weighted_pool_from_db(
        "SELECT text, weight FROM jokes WHERE chat_id=%s OR chat_id IS NULL",
        (chat_id,),
    )
    pool.extend(JOKES_PG13 if (mode or "").lower() == "pg13" else JOKES_R18)
    return random.choice(pool) if pool else "(порожній пул жартів)"

# ---- GPT-генерація (не блокує event loop) ----
async def gpt_joke(mode: str = "pg13") -> Optional[str]:
    if not (OPENAI_API_KEY and GPT_JOKES_ON):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        darkness = "легкий чорний гумор" if (mode or "").lower() == "pg13" else "чорний гумор, іронія, сленг"
        sys = (
            "Ти український стендап-комік. Пиши ОДИН дуже короткий дотепний жарт українською, у формі однорядка. "
            "Стиль: " + darkness + ". Без довгих пояснень, без тегів."
        )

        def _call():
            return client.chat.completions.create(
                model=GPT_JOKES_MODEL,
                messages=[
                    {"role": "system", "content": sys},
                    {"role": "user", "content": "Дай один короткий жарт для телеграм-чату (українською)."},
                ],
                max_tokens=64,
                temperature=float(GPT_JOKES_TEMP),
            )

        resp = await asyncio.to_thread(_call)
        line = (resp.choices[0].message.content or "").strip()
        return html.escape(line) if line else None
    except Exception:
        return None

async def pick_joke_maybe_gpt(chat_id: int, mode: str) -> str:
    use_gpt = bool(GPT_JOKES_ON) and (random.random() < float(GPT_JOKES_PROB))
    if use_gpt:
        g = await gpt_joke(mode)
        if g:
            return g
    return pick_joke(chat_id, mode)

# ---- персональний “roast” ----
def pick_personal_joke(chat_id: int, name: str) -> str:
    """
    Повертає персональний підкол з таблиці jokes_personal (тексти з плейсхолдером {name}).
    Якщо таблиця порожня — використовуємо невеликий дефолтний пул.
    """
    pool = _weighted_pool_from_db("SELECT text, weight FROM jokes_personal", ())
    if not pool:
        pool = [
            "якщо {name} каже «все під контролем» — готуйся до продакшну в пʼятницю",
            "{name}, ти як Windows Update — завжди не вчасно 🙃",
            "{name}, ти як SELECT * без WHERE — і працюєш, і страшно",
            "{name}, staging це не для слабаків — це для тебе",
            "{name}, твій код пахне фічею без тестів — готуйся до ревʼю",
        ]
    line = random.choice(pool)
    safe_name = html.escape(name or "ти")
    return line.replace("{name}", safe_name)
