# -*- coding: utf-8 -*-
# services/air_alerts.py
import asyncio
from typing import Tuple, Set, List
import aiohttp

from config import ALERTS_TOKEN, log
from db import db

# Константи для сповіщень
KYIV_CITY = "м. Київ"
KYIV_REGION = "Київська область"

API_BASE = "https://alerts.in.ua/api/"  # базовий URL API
POLL_SEC = 30                           # інтервал опитування у секундах
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)

# ----------------------- DB switches -----------------------
def set_air_city(chat_id: int, on: bool):
    """Увімкнути/вимкнути сповіщення про місто Київ для чату."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET air_city_on=%s WHERE chat_id=%s",
            (1 if on else 0, chat_id)
        )

def set_air_region(chat_id: int, on: bool):
    """Увімкнути/вимкнути сповіщення про Київську область для чату."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET air_region_on=%s WHERE chat_id=%s",
            (1 if on else 0, chat_id)
        )

def get_air_chats() -> Tuple[List[int], List[int]]:
    """Отримати списки чатів, підписаних на місто та область."""
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT chat_id FROM chats WHERE air_city_on=1")
        city = [r["chat_id"] for r in cur.fetchall()]
        cur.execute("SELECT chat_id FROM chats WHERE air_region_on=1")
        region = [r["chat_id"] for r in cur.fetchall()]
    return city, region

# ----------------------- HTTP client -----------------------
async def _fetch_states(session: aiohttp.ClientSession) -> Tuple[Set[str], Set[str]]:
    """
    Повертає множини назв:
      - cities_on  : міста, де активна повітряна тривога
      - regions_on : області, де активна повітряна тривога
    Працює напряму з офіційним API. Структура відповіді:
      { "cities": [{"name": "...", "alert": true/false}, ...],
        "regions": [{"name": "...", "alert": true/false}, ...] }
    """
    url = API_BASE + "states"
    async with session.get(url) as r:
        if r.status == 401:
            raise RuntimeError("Невірний або відсутній API-ключ (401).")
        r.raise_for_status()
        data = await r.json()

    def _names_on(items):
        out = set()
        for it in items or []:
            name = it.get("name") or it.get("title") or it.get("location_title")
            if name and bool(it.get("alert")):
                out.add(name)
        return out

    cities_on = _names_on(data.get("cities"))
    regions_on = _names_on(data.get("regions"))
    return cities_on, regions_on

# ----------------------- Public helpers -----------------------
async def air_status_text() -> str:
    """Повертає короткий текстовий статус для /status."""
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    headers = {"X-API-Key": ALERTS_TOKEN}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as s:
            cities, regions = await _fetch_states(s)
        parts = [
            "Київ: " + ("🔴 ТРИВОГА" if KYIV_CITY in cities else "🟢 ВІДБІЙ"),
            "Київська область: " + ("🔴 ТРИВОГА" if KYIV_REGION in regions else "🟢 ВІДБІЙ"),
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Помилка отримання статусу: {e}"

# ----------------------- Main loop -----------------------
async def air_alert_loop(bot):
    """
    Фоновий цикл:
      - кожні POLL_SEC секунд запитує стан;
      - надсилає повідомлення лише при зміні стану (on/off);
      - тримає одну HTTP-сесію, автоматично відновлюється після помилок.
    """
    if not ALERTS_TOKEN:
        log.warning("ALERTS_TOKEN not set; air_alert_loop disabled.")
        return

    headers = {"X-API-Key": ALERTS_TOKEN}

    # Останній відомий стан (None = ще не визначено, щоб уникнути «першого» спаму)
    last_city: bool | None = None
    last_region: bool | None = None

    backoff = POLL_SEC  # простий лінійний «бекоф» при помилках
    while True:
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
                cities, regions = await _fetch_states(session)

            now_city = KYIV_CITY in cities
            now_region = KYIV_REGION in regions

            city_chats, region_chats = get_air_chats()

            # Повідомляємо лише при зміні
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

            # Оновлюємо стани
            last_city = now_city
            last_region = now_region

            # при успіху — нормальний інтервал
            backoff = POLL_SEC
            await asyncio.sleep(POLL_SEC)

        except Exception as e:
            log.warning(f"air_alert_loop error: {e}")
            # невелика затримка перед наступною спробою
            await asyncio.sleep(min(max(backoff, 15), 120))
            backoff = min(backoff + 10, 120)
