# -*- coding: utf-8 -*-
# services/air_alerts.py
import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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

@dataclass(frozen=True)
class AlertState:
    level: str
    threats: Tuple[str, ...] = ()
    started_at: Optional[datetime] = None


AlertStates = Dict[str, AlertState]
LEVEL_PRIORITY = {"yellow": 1, "red": 2}
LEVEL_EMOJI = {"yellow": "🟡", "red": "🔴"}
LEVEL_LABEL = {"yellow": "ЖОВТИЙ РІВЕНЬ", "red": "ЧЕРВОНИЙ РІВЕНЬ"}
THREAT_LABELS = {
    "tactic_aircraft_activity": "активність тактичної авіації",
    "strategic_aircraft_activity": "активність стратегічної авіації",
    "mig31k_departure": "зліт МіГ-31К",
    "ballistic_missiles": "загроза балістичних ракет",
    "cruise_missiles": "загроза крилатих ракет",
    "unspecified_missiles": "ракетна загроза",
    "drones": "дронова загроза",
    "guided_aerial_bombs": "загроза КАБ",
    "air_defense": "робота ППО",
    "unknown": "невідома загроза",
}

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


def _parse_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        log.warning("Invalid air alert timestamp %r", value)
        return None


def _threats(alert: dict) -> Tuple[str, ...]:
    result: List[str] = []
    for threat in alert.get("threats") or []:
        if not isinstance(threat, dict):
            continue
        source_message = str(threat.get("source_message") or "").strip()
        threat_type = str(threat.get("threat_type") or "unknown").strip().lower()
        label = source_message or THREAT_LABELS.get(threat_type, threat_type.replace("_", " "))
        if label and label not in result:
            result.append(label)
    return tuple(result)


def _merge_alerts(current: Optional[AlertState], candidate: AlertState) -> AlertState:
    if current is None:
        return candidate

    started_at = current.started_at
    if started_at is None or (candidate.started_at is not None and candidate.started_at < started_at):
        started_at = candidate.started_at

    threats = tuple(dict.fromkeys(current.threats + candidate.threats))
    level = candidate.level if LEVEL_PRIORITY[candidate.level] > LEVEL_PRIORITY[current.level] else current.level
    return AlertState(level=level, threats=threats, started_at=started_at)


def _put_alert(states: AlertStates, name: str, alert: AlertState) -> None:
    states[name] = _merge_alerts(states.get(name), alert)


def _state_for_aliases(states: AlertStates, aliases: Set[str]) -> Optional[AlertState]:
    matching = [states[name] for name in aliases if name in states]
    if not matching:
        return None
    result = matching[0]
    for state in matching[1:]:
        result = _merge_alerts(result, state)
    return result


def _duration_text(started_at: Optional[datetime], now: Optional[datetime] = None) -> Optional[str]:
    if started_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - started_at).total_seconds()))
    minutes, _ = divmod(seconds, 60)
    if minutes < 1:
        return "менше хвилини"
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} год {minutes} хв" if minutes else f"{hours} год"
    return f"{minutes} хв"


def _alert_details(state: AlertState) -> str:
    parts = []
    if state.threats:
        parts.append("⚠️ Небезпека: " + "; ".join(state.threats))
    duration = _duration_text(state.started_at)
    if duration:
        parts.append(f"⏱ Триває: {duration}")
    return "\n".join(parts)


def _status_line(title: str, state: Optional[AlertState]) -> str:
    if state is None:
        return f"{title}: 🟢 ВІДБІЙ"
    details = _alert_details(state)
    return "\n".join(filter(None, [f"{title}: {LEVEL_EMOJI[state.level]} {LEVEL_LABEL[state.level]}", details]))


def _change_message(title: str, previous: Optional[AlertState], current: Optional[AlertState]) -> str:
    if current is None:
        return f"🟢 Відбій у {title}."

    if previous is None:
        prefix = "🔔 Нова повітряна тривога"
    elif LEVEL_PRIORITY[current.level] > LEVEL_PRIORITY[previous.level]:
        prefix = "🔴 ПІДВИЩЕННЯ РІВНЯ ТРИВОГИ"
    else:
        prefix = "⚠️ ОНОВЛЕННЯ ТРИВОГИ"

    message = f"{prefix} у {title}: {LEVEL_EMOJI[current.level]} {LEVEL_LABEL[current.level]}!"
    details = _alert_details(current)
    return "\n".join(filter(None, [message, details]))


async def _fetch_states(session: aiohttp.ClientSession) -> Tuple[AlertStates, AlertStates]:
    """
    Повертає мапи нормалізованих назв на стан: (cities, regions).
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
        alert = AlertState(
            level=_normalize_level(a.get("alert_level")),
            threats=_threats(a),
            started_at=_parse_datetime(a.get("started_at")),
        )

        if lt in CITY_LOCATION_TYPES:
            _put_alert(cities, norm, alert)
        elif lt in REGION_LOCATION_TYPES:
            _put_alert(regions, norm, alert)

        if norm in KYIV_CITY_ALIASES:
            _put_alert(cities, norm, alert)
        if norm in KYIV_REGION_ALIASES:
            _put_alert(regions, norm, alert)

    return cities, regions

# ----------------------- Public helpers -----------------------
async def air_status_text() -> str:
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as s:
            cities, regions = await _fetch_states(s)

        city_state = _state_for_aliases(cities, KYIV_CITY_ALIASES)
        region_state = _state_for_aliases(regions, KYIV_REGION_ALIASES)

        parts = [
            _status_line("Київ", city_state),
            _status_line("Київська область", region_state),
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

    last_city: Optional[AlertState] = None
    last_region: Optional[AlertState] = None
    city_initialized = False
    region_initialized = False
    startup_announced = False
    backoff = POLL_SEC

    while True:
        sleep_for = POLL_SEC
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
                cities, regions = await _fetch_states(session)

            now_city = _state_for_aliases(cities, KYIV_CITY_ALIASES)
            now_region = _state_for_aliases(regions, KYIV_REGION_ALIASES)

            city_chats, region_chats = get_air_chats()

            if not startup_announced:
                startup_text = "✅ Я оновився і тепер розрізняю рівні тривог та типи небезпек.\n\n"
                startup_text += "\n\n".join([
                    _status_line("Київ", now_city),
                    _status_line("Київська область", now_region),
                ])
                for cid in set(city_chats + region_chats):
                    try:
                        await bot.send_message(cid, startup_text)
                    except Exception as e:
                        log.warning(f"send startup alert update failed chat={cid}: {e}")
                startup_announced = True

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
