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
KYIV_DISTRICTS = (
    ("73", "Білоцерківський район", "Білоцерківському районі"),
    ("74", "Вишгородський район", "Вишгородському районі"),
    ("75", "Бучанський район", "Бучанському районі"),
    ("76", "Обухівський район", "Обухівському районі"),
    ("77", "Фастівський район", "Фастівському районі"),
    ("78", "Бориспільський район", "Бориспільському районі"),
    ("79", "Броварський район", "Броварському районі"),
)
KYIV_DISTRICT_BY_UID = {uid: name for uid, name, _ in KYIV_DISTRICTS}

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


def set_air_district(chat_id: int, user_id: int, district_uid: str, district_name: str, on: bool):
    with db() as conn, conn.cursor() as cur:
        if on:
            cur.execute(
                """
                INSERT INTO air_district_subscriptions (chat_id, user_id, district_uid, district_name)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE district_name=VALUES(district_name)
                """,
                (chat_id, user_id, district_uid, district_name),
            )
        else:
            cur.execute(
                "DELETE FROM air_district_subscriptions WHERE chat_id=%s AND user_id=%s AND district_uid=%s",
                (chat_id, user_id, district_uid),
            )


def get_user_air_districts(chat_id: int, user_id: int) -> Set[str]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT district_uid FROM air_district_subscriptions WHERE chat_id=%s AND user_id=%s",
            (chat_id, user_id),
        )
        return {str(row["district_uid"]) for row in cur.fetchall()}


def get_air_district_subscriptions() -> List[Tuple[int, int, str]]:
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT chat_id, user_id, district_uid FROM air_district_subscriptions")
        return [(int(row["chat_id"]), int(row["user_id"]), str(row["district_uid"])) for row in cur.fetchall()]


def resolve_district(value: str) -> Optional[Tuple[str, str]]:
    query = _normalize(value)
    for uid, name, _ in KYIV_DISTRICTS:
        if query in {uid, _normalize(name), _normalize(name.removesuffix(" район"))}:
            return uid, name
    return None

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


async def _fetch_states(session: aiohttp.ClientSession) -> Tuple[AlertStates, AlertStates, AlertStates]:
    """
    Повертає мапи нормалізованих назв на стан: (cities, regions, districts).
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
    districts: AlertStates = {}
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

        # Районні та громадські тривоги мають власний location_title,
        # але область-власник передається в location_oblast.
        oblast = a.get("location_oblast")
        oblast_norm = _normalize(oblast) if oblast else ""
        if oblast_norm in KYIV_CITY_ALIASES:
            _put_alert(cities, _normalize(KYIV_CITY), alert)
        if oblast_norm in KYIV_REGION_ALIASES:
            _put_alert(regions, _normalize(KYIV_REGION), alert)
            district_uid = str(a.get("location_uid") or "")
            if lt == "raion" and district_uid in KYIV_DISTRICT_BY_UID:
                _put_alert(districts, district_uid, alert)

    return cities, regions, districts

# ----------------------- Public helpers -----------------------
async def air_status_text() -> str:
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}
    try:
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as s:
            cities, regions, districts = await _fetch_states(s)

        city_state = _state_for_aliases(cities, KYIV_CITY_ALIASES)
        region_state = _state_for_aliases(regions, KYIV_REGION_ALIASES)

        parts = [
            _status_line("Київ", city_state),
            _status_line("Київська область", region_state),
        ]
        district_lines = [
            _status_line(name, districts.get(uid))
            for uid, name, _ in KYIV_DISTRICTS
        ]
        parts.append("Київська область по районах:\n" + "\n".join(district_lines))
        return "\n".join(parts)
    except Exception as e:
        return f"Помилка отримання статусу: {e}"


async def air_districts_text(chat_id: int, user_id: int) -> str:
    if not ALERTS_TOKEN:
        return "⚠️ API ключ alerts.in.ua не задано."

    try:
        headers = {"Authorization": f"Bearer {ALERTS_TOKEN}"}
        async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
            _, _, districts = await _fetch_states(session)
        subscribed = get_user_air_districts(chat_id, user_id)
        lines = ["Ваші районні підписки Київської області:"]
        for uid, name, _ in KYIV_DISTRICTS:
            mark = "✅" if uid in subscribed else "⬜"
            state = districts.get(uid)
            if state is None:
                status = "🟢 відбій"
            else:
                status = f"{LEVEL_EMOJI[state.level]} {LEVEL_LABEL[state.level].lower()}"
            lines.append(f"{mark} <code>{uid}</code> {name} — {status}")
        lines.append("\nУвімкнути: <code>/air_district_on 75</code>")
        lines.append("Вимкнути: <code>/air_district_off 75</code>")
        return "\n".join(lines)
    except Exception as e:
        return f"Помилка отримання районів: {e}"

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
    district_initialized = False
    last_districts: Dict[str, Optional[AlertState]] = {}
    backoff = POLL_SEC

    while True:
        sleep_for = POLL_SEC
        try:
            async with aiohttp.ClientSession(headers=headers, timeout=HTTP_TIMEOUT) as session:
                cities, regions, districts = await _fetch_states(session)

            now_city = _state_for_aliases(cities, KYIV_CITY_ALIASES)
            now_region = _state_for_aliases(regions, KYIV_REGION_ALIASES)

            city_chats, region_chats = get_air_chats()
            district_subscriptions = get_air_district_subscriptions()

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

            for district_uid, district_name, district_locative in KYIV_DISTRICTS:
                current = districts.get(district_uid)
                previous = last_districts.get(district_uid)
                if district_initialized and current != previous:
                    recipients = {
                        user_id
                        for _, user_id, subscribed_uid in district_subscriptions
                        if subscribed_uid == district_uid
                    }
                    text = _change_message(district_locative, previous, current)
                    for user_id in recipients:
                        try:
                            await bot.send_message(user_id, text)
                        except Exception as e:
                            log.warning(f"send district alert failed user={user_id} district={district_uid}: {e}")
                last_districts[district_uid] = current

            last_city = now_city
            last_region = now_region
            city_initialized = True
            region_initialized = True
            district_initialized = True
            backoff = POLL_SEC

        except Exception as e:
            log.warning(f"air_alert_loop error: {e}")
            sleep_for = min(max(backoff, 15), 120)
            backoff = min(backoff + 10, 120)

        finally:
            await asyncio.sleep(sleep_for)
