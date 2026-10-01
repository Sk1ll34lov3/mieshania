# -*- coding: utf-8 -*-
"""Daily OpenAI horoscope generation and delivery."""

from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from config import (
    OPENAI_API_KEY,
    OPENAI_HOROSCOPE_MODEL,
    OPENAI_HOROSCOPE_TIMEOUT,
    log,
)
from db import db


SIGNS = (
    ("♈️", "Овен"),
    ("♉️", "Телець"),
    ("♊️", "Близнята"),
    ("♋️", "Рак"),
    ("♌️", "Лев"),
    ("♍️", "Діва"),
    ("♎️", "Терези"),
    ("♏️", "Скорпіон"),
    ("⛎", "Змієносець"),
    ("♐️", "Стрілець"),
    ("♑️", "Козоріг"),
    ("♒️", "Водолій"),
    ("♓️", "Риби"),
)

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "horoscope_examples.txt"
try:
    STYLE_EXAMPLES = _DATA_FILE.read_text(encoding="utf-8")
except OSError:
    STYLE_EXAMPLES = "Гумор короткий, абсурдний, нахабний та побутовий"

_FORBIDDEN_PUNCTUATION = ("-", "–", "—", "‑", ":")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


def _clean_text(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    for symbol in _FORBIDDEN_PUNCTUATION:
        text = text.replace(symbol, " ")
    return " ".join(text.split())[:300]


def _parse_json(content: str) -> list[dict] | None:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I | re.S).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = data.get("lines")
    if not isinstance(data, list) or len(data) != len(SIGNS):
        return None
    result = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or not _clean_text(item.get("text")):
            return None
        text = _clean_text(item["text"])
        sign_name = SIGNS[index][1]
        text = re.sub(rf"^{re.escape(sign_name)}(?:\s*[,.;]\s*|\s+)", "", text, flags=re.I)
        result.append({"text": _clean_text(text)})
    if any(not item["text"] for item in result):
        return None
    return result


def _recent_history(limit: int = 90) -> list[dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT sign, text FROM horoscope_history ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        return list(reversed(cur.fetchall()))


def _targets() -> list[dict]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chat_id, horoscope_time
            FROM chats
            WHERE horoscope_on=1 AND chat_id < 0
            """
        )
        return cur.fetchall()


def _already_posted(chat_id: int, issue_date: date) -> bool:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM horoscope_posts WHERE chat_id=%s AND issue_date=%s LIMIT 1",
            (chat_id, issue_date),
        )
        return bool(cur.fetchone())


def _disable_target(chat_id: int) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE chats SET horoscope_on=0 WHERE chat_id=%s", (chat_id,))


def _save_post(chat_id: int, issue_date: date, content: str, lines: list[dict]) -> None:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT IGNORE INTO horoscope_posts (chat_id, issue_date, content) VALUES (%s, %s, %s)",
            (chat_id, issue_date, content),
        )
        cur.execute(
            "SELECT 1 FROM horoscope_history WHERE issue_date=%s LIMIT 1",
            (issue_date,),
        )
        if not cur.fetchone():
            for (_, sign), line in zip(SIGNS, lines):
                cur.execute(
                    "INSERT INTO horoscope_history (issue_date, sign, text) VALUES (%s, %s, %s)",
                    (issue_date, sign, line["text"]),
                )


def _format(lines: list[dict]) -> str:
    chunks = ["✨ Щоденний смачний гороскоп", "Шукай себе та надсилай друзям!"]
    for (emoji, sign), line in zip(SIGNS, lines):
        chunks.append(f"{emoji} {sign}\n{html.escape(line['text'], quote=False)}")
    return "\n\n".join(chunks)


def _time_is_due(value: str | None, now: datetime) -> bool:
    match = _TIME_RE.match((value or "09:30").strip())
    if not match:
        hour, minute = 9, 30
    else:
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            hour, minute = 9, 30
    return (now.hour, now.minute) >= (hour, minute)


async def _generate(issue_date: date, history: list[dict]) -> list[dict] | None:
    if not OPENAI_API_KEY:
        log.warning("Horoscope skipped because OPENAI_API_KEY is not configured")
        return None

    previous = "\n".join(f"{row['sign']} | {row['text']}" for row in history)
    prompt = f"""
Створи щоденний гумористичний гороскоп українською мовою на {issue_date.isoformat()}.
Потрібно рівно 13 коротких прогнозів у порядку знаків нижче.
Змієносець обов'язково має бути окремим тринадцятим знаком.

Стиль
Це не мотиваційний гороскоп, а чорний пацанський стібок у формі фальшивого астрологічного прогнозу.
Подача суха і серйозна, ніби астролог сухо повідомляє людині жахливі новини про її життя.
Кожен прогноз це строго ОДНЕ речення, до 110 символів і не більше однієї коми, одна думка і один удар.
Жарт будується на одному конкретному абсурдному або принизливому факті, а не на загальних словах.
Формули які працюють
прогноз який виявляється образою ("Ваша наступна зарплата буде у рублях"),
конкретна дурна ситуація з життя ("ваші друзі створять чат Карпати 2026, а ви нікуди не поїдете"),
злий сюжетний поворот ("ваші колишні одружились суто щоб вас позлити"),
фальшива порада яка насправді діагноз ("Не сприймайте людей серйозно, усі навколо вас клоуни"),
різкий останній поворот у кінці речення.
Мат і грубий сленг уживай як частину жарту там де вони б'ють сильніше
(хуй, хуйня, піздити, срака, йобаний, лох, дрочити та подібне), приблизно у двох третинах прогнозів.
Лайка не прикраса, вона має стояти в самому ударі жарту.
Слова лох і йобаний використовуй не більше ніж у двох прогнозах на випуск, шукай інші лайливі слова та інші образи.
Жартуй про гроші, роботу, бухло, секс, колишніх, друзів, зрадництво, лінь, дурість, ігри, війну з росією у чорному ключі.
Не сиди в офісі, бери теми з усього життя українського пацана
війна і росія у чорному ключі, ТЦК і мобілізація, донати, ігри (кс, доту, фейсіт, танки),
політика і новини (США, Ормузька протока, санкції), мемна дичина, тіндер і колишні,
бухло і похмілля, дружні чати і поїздки які не відбудуться, зарплата, борги, кредити,
крипта, ШІ і ChatGPT, їжа з МакДональдсу, спортзал, сусіди, маршрутки, комуналка.
Максимум два прогнози на випуск можуть бути про офіс чи начальника.
Допускай абсурдні вигадані сюжети, мета жарти про сам гороскоп і короткі добивання на кшталт
"Шоб ви вічно жили", якщо вони смішні.
Звертайся до людини на ви або безособово як у референсах, без слів брат, куме, чувак.
Не починай з привітань і не питай нічого у читача.
Не пиши води, порівнянь на півречення і розмитих образів.
Фрази мають бути граматичними, зрозумілими та смішними з першого прочитання.
Якщо жарт не зрозумілий без пояснення, замін його.
Не повторюй формулювання або саму ідею з історії попередніх прогнозів.
Не пиши пояснення, заголовки або зайві поля.

Обмеження
Не використовуй дефіси або тире та двокрапки у тексті прогнозів.
Не жартуй через ненависть до захищених груп, сексуальне насильство, самопошкодження,
реальні погрози, наркотики або інструкції до незаконних дій.
Ображати можна саму людину за її вигадані вчинки та характер, а не за походження,
національність, релігію, здоров'я чи орієнтацію.

Не додавай назву знака на початку тексту, бот поставить її сам.
Поверни тільки JSON об'єкт такого виду
{{"lines":[{{"text":"текст для Овна"}},{{"text":"текст для Тільця"}}]}}
Масив має містити рівно 13 об'єктів і відповідати цьому порядку
Овен, Телець, Близнята, Рак, Лев, Діва, Терези, Скорпіон, Змієносець,
Стрілець, Козоріг, Водолій, Риби.

Приклади бажаного ритму та гумору
{STYLE_EXAMPLES}

Історія вже використаних прогнозів, які не можна повторювати
{previous or "Історії ще немає"}
""".strip()

    payload = {
        "model": OPENAI_HOROSCOPE_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ти автор паблика з чорним матюкливим гумором, який пише щоденний фальшивий гороскоп для друзів у чаті. Кожен прогноз короткий, жорсткий, з матом у пуанті, природною українською без води. Дотримуйся формату JSON і всіх обмежень.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    if OPENAI_HOROSCOPE_MODEL.startswith(("gpt-5", "o1", "o3", "o4")):
        payload["max_completion_tokens"] = 12000
        payload["reasoning_effort"] = "low"
    else:
        payload["temperature"] = 0.8
        payload["max_tokens"] = 1800
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=OPENAI_HOROSCOPE_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    log.error("Horoscope OpenAI HTTP %s: %s", response.status, body)
                    return None
    except Exception as exc:
        log.exception("Horoscope OpenAI request failed: %s", exc)
        return None

    try:
        content = body["choices"][0]["message"]["content"]
    except Exception:
        log.error("Horoscope OpenAI malformed response: %r", body)
        return None
    parsed = _parse_json(content)
    if not parsed:
        return None
    previous_texts = {_clean_text(row.get("text")).casefold() for row in history}
    current_texts = [_clean_text(row.get("text")).casefold() for row in parsed]
    if len(set(current_texts)) != len(current_texts):
        log.warning("Horoscope OpenAI returned duplicate lines")
        return None
    if any(text in previous_texts for text in current_texts):
        log.warning("Horoscope OpenAI repeated a previous line")
        return None
    return parsed


async def horoscope_loop(bot) -> None:
    tz = ZoneInfo("Europe/Kyiv")
    cached_date: date | None = None
    cached_lines: list[dict] | None = None
    last_generation_attempt: datetime | None = None
    while True:
        try:
            now = datetime.now(tz)
            issue_date = now.date()
            targets = [row for row in _targets() if _time_is_due(row.get("horoscope_time"), now)]
            if targets:
                can_generate = (
                    cached_date != issue_date
                    and (
                        last_generation_attempt is None
                        or (now - last_generation_attempt).total_seconds() >= 300
                    )
                )
                if can_generate:
                    last_generation_attempt = now
                    candidate = await _generate(issue_date, _recent_history())
                    if candidate:
                        cached_date = issue_date
                        cached_lines = candidate
                if cached_lines:
                    content = _format(cached_lines)
                    for row in targets:
                        chat_id = int(row["chat_id"])
                        if _already_posted(chat_id, issue_date):
                            continue
                        try:
                            await bot.send_message(chat_id, content)
                            _save_post(chat_id, issue_date, content, cached_lines)
                        except Exception as exc:
                            log.warning("Horoscope delivery failed for %s: %s", chat_id, exc)
                            error_text = str(exc).lower()
                            if any(
                                marker in error_text
                                for marker in (
                                    "chat not found",
                                    "group chat was upgraded",
                                    "bot was kicked",
                                    "bot is not a member",
                                )
                            ):
                                _disable_target(chat_id)
        except Exception as exc:
            log.exception("Horoscope loop failed: %s", exc)
        await asyncio.sleep(20)
