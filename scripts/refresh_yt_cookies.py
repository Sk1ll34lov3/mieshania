#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оновлення YouTube-кукі на VPS з Firefox на цьому ПК.

Чому з ПК: Google блокує логін з IP датацентру, тому нову сесію на VPS не створити.
Поки сесія жива, VPS сам підтримує куки (yt-dlp перезаписує файл при кожному запуску),
тож скрипт нічого не чіпає, якщо перевірка на VPS проходить.

Логіка:
  1. Перевірка на VPS: yt-dlp --simulate --cookies <файл> <Shorts URL>.
  2. Якщо OK — вихід (код 0), куки не чіпаємо.
  3. Якщо ні — читаємо куки youtube.com з Firefox, перевіряємо повноту,
     заливаємо на VPS (з backup), перевіряємо ще раз; якщо не допомогло — відкат (код 2).

Вимоги: pip install "yt-dlp[default]"; в Firefox залогінений акаунт бота; ssh-аліас `mieshania`.

Запуск:
    python scripts/refresh_yt_cookies.py            # перевірити, оновити лише якщо треба
    python scripts/refresh_yt_cookies.py --force    # оновити в будь-якому разі

Коди виходу: 0 — OK, 1 — помилка локально (немає Firefox/куків/неповний набір), 2 — не допомогло.
Windows Task Scheduler (раз на добу):
    schtasks /Create /SC DAILY /ST 10:00 /TN "MieshaniaYtCookies" /TR "python <шлях>\\scripts\\refresh_yt_cookies.py"
"""

from __future__ import annotations

import argparse
import configparser
import os
import shlex
import subprocess
import sys
import tempfile
from http.cookiejar import MozillaCookieJar

SSH_HOST = "mieshania"
REMOTE_COOKIES = "/var/opt/mieshania/cookies_youtube.txt"
REMOTE_YTDLP = "/var/opt/mieshania/.venv/bin/yt-dlp"
TEST_URL = "https://youtube.com/shorts/H0ozLw4qs1I"
# Без цього набору YouTube не вважає сесію залогіненою (3P-кукі самі по собі не працюють).
REQUIRED = {"SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID", "LOGIN_INFO"}


def log(msg: str) -> None:
    print(msg, flush=True)


def ssh(cmd: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """ssh з повторами: з'єднання з VPS інколи рветься на кілька секунд."""
    last = None
    for _ in range(3):
        last = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", SSH_HOST, cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        if last.returncode != 255:  # 255 = помилка самого ssh
            break
    return last


def remote_ok() -> bool:
    cmd = (
        f"{REMOTE_YTDLP} --simulate --no-warnings --cookies {shlex.quote(REMOTE_COOKIES)} "
        f"{shlex.quote(TEST_URL)}"
    )
    res = ssh(cmd, timeout=240)
    if res.returncode != 0:
        tail = (res.stderr or res.stdout or "").strip().splitlines()[-1:] or ["?"]
        log(f"  перевірка на VPS: FAIL ({tail[0][:140]})")
        return False
    log("  перевірка на VPS: OK")
    return True


def firefox_profile() -> str:
    base = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox")
    ini = configparser.RawConfigParser()
    ini.read(os.path.join(base, "profiles.ini"), encoding="utf-8")
    rel = None
    for sec in ini.sections():  # актуальний профіль інсталяції (його Firefox реально використовує)
        if sec.startswith("Install") and ini.has_option(sec, "Default"):
            rel = ini.get(sec, "Default")
            break
    if rel is None:
        for sec in ini.sections():
            if sec.startswith("Profile") and ini.get(sec, "Default", fallback="0") == "1":
                rel = ini.get(sec, "Path")
                break
    if not rel:
        raise RuntimeError("Не знайшов профіль Firefox у profiles.ini")
    return os.path.join(base, rel.replace("/", os.sep))


def export_cookies(dest: str) -> None:
    from yt_dlp.cookies import extract_cookies_from_browser

    jar = extract_cookies_from_browser("firefox", firefox_profile())
    cookies = [c for c in jar if c.domain.endswith("youtube.com")]
    missing = REQUIRED - {c.name for c in cookies}
    if missing:
        raise RuntimeError(
            "Неповний набір кукі в Firefox (немає: " + ", ".join(sorted(missing)) + "). "
            "Залогінься в YouTube акаунтом бота у Firefox і відкрий будь-яке відео."
        )
    out = MozillaCookieJar(dest)
    for c in cookies:
        out.set_cookie(c)
    out.save(ignore_discard=True, ignore_expires=True)
    log(f"  експортовано {len(cookies)} кукі youtube.com")


def push(local_path: str) -> None:
    tmp_remote = REMOTE_COOKIES + ".new"
    res = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
                          local_path, f"{SSH_HOST}:{tmp_remote}"], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("scp не вдався: " + (res.stderr or "").strip()[:200])
    res = ssh(f"cp -p {REMOTE_COOKIES} {REMOTE_COOKIES}.bak; "
              f"chmod 600 {tmp_remote} && mv {tmp_remote} {REMOTE_COOKIES}")
    if res.returncode != 0:
        raise RuntimeError("не вдалось замінити файл на VPS: " + (res.stderr or "").strip()[:200])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="оновити, навіть якщо перевірка на VPS проходить")
    args = ap.parse_args()

    log("Перевіряю куки на VPS…")
    if remote_ok() and not args.force:
        return 0

    log("Оновлюю куки з Firefox…")
    fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_")
    os.close(fd)
    try:
        try:
            export_cookies(tmp)
            push(tmp)
        except Exception as e:
            log(f"ПОМИЛКА: {e}")
            return 1
    finally:
        try:
            os.remove(tmp)  # у файлі сесія — не лишаємо на диску
        except OSError:
            pass

    if remote_ok():
        log("Готово: куки оновлено.")
        return 0

    ssh(f"cp -p {REMOTE_COOKIES}.bak {REMOTE_COOKIES}")
    log("Не допомогло: YouTube досі не віддає відео. Файл на VPS повернуто з backup. "
        "Ймовірно, акаунт розлогінено або потрібна перевірка (капча/2FA) — зайди в нього у Firefox.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
