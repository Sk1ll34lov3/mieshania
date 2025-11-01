# -*- coding: utf-8 -*-
# services/air_alerts.py
import asyncio
import re
from typing import Tuple, Set, List, Optional
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
async def _fetch_states(session: aiohttp.ClientSession) -> Tuple[Set[str], Set[str]]:
    """
    Повертає множини назв: (cities_on, regions_on) для alert_type == "air_raid".
    Формат відповіді: {"alerts":[{"location_title","location_type","alert_type",...}, ...]}
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

    cities_on: Set[str] = set()
    regions_on: Set[str] = set()
    for a in air:
        lt = (a.get("location_type") or "").lower()
        name = _title(a)
        if not name:
            continue

        norm = _normalize(name)

        if lt in CITY_LOCATION_TYPES:
            cities_on.add(norm)
        elif lt in REGION_LOCATION_TYPES:
            regions_on.add(norm)

        if norm in KYIV_CITY_ALIASES:
            cities_on.add(norm)
        if norm in KYIV_REGION_ALIASES:
            regions_on.add(norm)

    return cities_on, regions_on

# ----------------------- Public helpers -----------------------
async def air_status_text() -> str:
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as s:
            cities, regions = await _fetch_states(s)

        city_on = bool(cities & KYIV_CITY_ALIASES)
        region_on = bool(regions & KYIV_REGION_ALIASES)

        parts = [
            "Київ: " + ("🔴 ТРИВОГА" if city_on else "🟢 ВІДБІЙ"),
            "Київська область: " + ("🔴 ТРИВОГА" if region_on else "🟢 ВІДБІЙ"),
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

    last_city: Optional[bool] = None
    last_region: Optional[bool] = None
    backoff = POLL_SEC

    while True:
        sleep_for = POLL_SEC
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
                cities, regions = await _fetch_states(session)

            now_city = bool(cities & KYIV_CITY_ALIASES)
            now_region = bool(regions & KYIV_REGION_ALIASES)

            city_chats, region_chats = get_air_chats()

            if last_city is not None and now_city != last_city:
                text = "🔴 Повітряна тривога в Києві!" if now_city else "🟢 Відбій у Києві."
                for cid in city_chats:
                    try:
                        await bot.send_message(cid, text)
                    except Exception as e:
                        log.warning(f"send city alert failed chat={cid}: {e}")

            if last_region is not None and now_region != last_region:
                text = "🔴 Повітряна тривога в Київській області!" if now_region else "🟢 Відбій у Київській області."
                for cid in region_chats:
                    try:
                        await bot.send_message(cid, text)
                    except Exception as e:
                        log.warning(f"send region alert failed chat={cid}: {e}")

            last_city = now_city
            last_region = now_region
            backoff = POLL_SEC

        except Exception as e:
            log.warning(f"air_alert_loop error: {e}")
            sleep_for = min(max(backoff, 15), 120)
            backoff = min(backoff + 10, 120)

        finally:
            await asyncio.sleep(sleep_for)
