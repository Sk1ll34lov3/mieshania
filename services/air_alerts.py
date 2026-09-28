# -*- coding: utf-8 -*-
# services/air_alerts.py
import asyncio
import re
from typing import Dict, List, Optional, Set, Tuple
import aiohttp

from config import ALERTS_TOKEN, log
from db import db

KYIV_CITY = "м. Київ"
KYIV_REGION = "Київська область"


def _normalize(title: str) -> str:
    """Нормалізує назви з API для порівняння."""
    return re.sub(r"\s+", " ", title.strip()).lower()


KYIV_CITY_ALIASES: Set[str] = {
    _normalize(name)
    for name in {
        "м. Київ",
        "місто Київ",
        "Київ",
        "Kyiv",
        "Kyiv City",
    }
}

KYIV_REGION_ALIASES: Set[str] = {
    _normalize(name)
    for name in {
        "Київська область",
        "Kyivska oblast",
        "Kyiv Oblast",
    }
}

CITY_LOCATION_TYPES = {"city", "capital", "settlement"}
REGION_LOCATION_TYPES = {"oblast", "region", "state"}

API_URL = "https://api.alerts.in.ua/v1/alerts/active.json"
POLL_SEC = 30
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)

AlertStates = Dict[str, str]
LEVEL_PRIORITY = {"yellow": 1, "red": 2}
LEVEL_EMOJI = {"yellow": "🟡", "red": "🔴"}
LEVEL_LABEL = {"yellow": "ЖОВТИЙ РІВЕНЬ", "red": "ЧЕРВОНИЙ РІВЕНЬ"}

# ----------------------- DB switches -----------------------
def set_air_city(chat_id: int, on: bool):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE chats SET air_city_on=%s WHERE chat_id=%s", (1 if on else 0, chat_id))

def set_air_region(chat_id: int, on: bool):
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE chats SET air_region_on=%s WHERE chat_id=%s", (1 if on else 0, chat_id))

def get_air_chats() -> Tuple[List[int], List[int]]:
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT chat_id FROM chats WHERE air_city_on=1")
        city = [r["chat_id"] for r in cur.fetchall()]
        cur.execute("SELECT chat_id FROM chats WHERE air_region_on=1")
        region = [r["chat_id"] for r in cur.fetchall()]
    return city, region

# ----------------------- HTTP client -----------------------
def _normalize_level(value: object) -> str:
    """Повертає відомий рівень; старі відповіді без рівня вважаємо червоними."""
    level = str(value or "red").strip().lower()
    if level not in LEVEL_PRIORITY:
        log.warning("Unknown air alert level %r; treating it as red", value)
        return "red"
    return level


def _put_highest_level(states: AlertStates, name: str, level: str) -> None:
    current = states.get(name)
    if current is None or LEVEL_PRIORITY[level] > LEVEL_PRIORITY[current]:
        states[name] = level


def _level_for_aliases(states: AlertStates, aliases: Set[str]) -> Optional[str]:
    levels = [states[name] for name in aliases if name in states]
    if not levels:
        return None
    return max(levels, key=LEVEL_PRIORITY.get)


def _status_line(title: str, level: Optional[str]) -> str:
    if level is None:
        return f"{title}: 🟢 ВІДБІЙ"
    return f"{title}: {LEVEL_EMOJI[level]} {LEVEL_LABEL[level]}"


def _change_message(title: str, previous: Optional[str], current: Optional[str]) -> str:
    if current is None:
        return f"🟢 Відбій у {title}."

    level_text = f"{LEVEL_EMOJI[current]} {LEVEL_LABEL[current]}"
    if previous is None:
        return f"{level_text} повітряної тривоги в {title}!"
    if LEVEL_PRIORITY[current] > LEVEL_PRIORITY[previous]:
        return f"🔴 ПІДВИЩЕННЯ РІВНЯ: у {title} {level_text.lower()}!"
    return f"{level_text} повітряної тривоги в {title}."


async def _fetch_states(session: aiohttp.ClientSession) -> Tuple[AlertStates, AlertStates]:
    """
    Повертає мапи нормалізованих назв на рівень: (cities, regions).
    Обробляються лише події з alert_type == "air_raid".
    API передає рівень у полі alert_level: yellow або red.
    """
    async with session.get(API_URL) as r:
        if r.status == 401:
            raise RuntimeError("Невірний або відсутній API-ключ (401).")
        r.raise_for_status()
        data = await r.json()

    alerts = data.get("alerts", []) or []
    air = [a for a in alerts if a.get("alert_type") == "air_raid"]

    def _title(a: dict) -> Optional[str]:
        return a.get("location_title") or a.get("title") or a.get("name")

    cities: AlertStates = {}
    regions: AlertStates = {}
    for a in air:
        lt = (a.get("location_type") or "").lower()
        name = _title(a)
        if not name:
            continue

        norm = _normalize(name)
        level = _normalize_level(a.get("alert_level"))

        if lt in CITY_LOCATION_TYPES:
            _put_highest_level(cities, norm, level)
        elif lt in REGION_LOCATION_TYPES:
            _put_highest_level(regions, norm, level)

        if norm in KYIV_CITY_ALIASES:
            _put_highest_level(cities, norm, level)
        if norm in KYIV_REGION_ALIASES:
            _put_highest_level(regions, norm, level)

    return cities, regions

# ----------------------- Public helpers -----------------------
async def air_status_text() -> str:
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as s:
            cities, regions = await _fetch_states(s)

        city_level = _level_for_aliases(cities, KYIV_CITY_ALIASES)
        region_level = _level_for_aliases(regions, KYIV_REGION_ALIASES)

        parts = [
            _status_line("Київ", city_level),
            _status_line("Київська область", region_level),
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Помилка отримання статусу: {e}"

# ----------------------- Main loop -----------------------
async def air_alert_loop(bot):
    if not ALERTS_TOKEN:
        log.warning("ALERTS_TOKEN not set; air_alert_loop disabled.")
        return

    headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}

    last_city: Optional[str] = None
    last_region: Optional[str] = None
    city_initialized = False
    region_initialized = False
    backoff = POLL_SEC

    while True:
        sleep_for = POLL_SEC
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
                cities, regions = await _fetch_states(session)

            now_city = _level_for_aliases(cities, KYIV_CITY_ALIASES)
            now_region = _level_for_aliases(regions, KYIV_REGION_ALIASES)

            city_chats, region_chats = get_air_chats()

            if city_initialized and now_city != last_city:
                text = _change_message("Києві", last_city, now_city)
                for cid in city_chats:
                    try:
                        await bot.send_message(cid, text)
                    except Exception as e:
                        log.warning(f"send city alert failed chat={cid}: {e}")

            if region_initialized and now_region != last_region:
                text = _change_message("Київській області", last_region, now_region)
                for cid in region_chats:
                    try:
                        await bot.send_message(cid, text)
                    except Exception as e:
                        log.warning(f"send region alert failed chat={cid}: {e}")

            last_city = now_city
            last_region = now_region
            city_initialized = True
            region_initialized = True
            backoff = POLL_SEC

        except Exception as e:
            log.warning(f"air_alert_loop error: {e}")
            sleep_for = min(max(backoff, 15), 120)
            backoff = min(backoff + 10, 120)

        finally:
            await asyncio.sleep(sleep_for)
