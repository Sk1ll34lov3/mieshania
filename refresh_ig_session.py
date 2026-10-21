#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оновлення Instagram сесії для бота Мєшаня.

ВАЖЛИВО: запускай з residential IP (домашній Wi-Fi або мобільний хотспот),
         НЕ з VPS / datacenter — Instagram блокує такі логіни.

Використання:
    python refresh_ig_session.py

Що робить:
    1. Логінить акаунт solov__design в Instagram через instagrapi
    2. Зберігає сесію в ig_session.json і кукі в cookies_instagram.txt
    3. Заливає обидва файли на VPS і рестартить бота (--yes: без питань)
"""

import getpass
import json
import os
import subprocess
import sys

VPS_HOST = "mieshania"  # alias з ~/.ssh/config (root@91.98.134.12)
VPS_SESSION_PATH = "/var/opt/mieshania/ig_session.json"
VPS_COOKIES_PATH = "/var/opt/mieshania/cookies_instagram.txt"
LOCAL_SESSION_FILE = "ig_session.json"
LOCAL_COOKIES_FILE = "cookies_instagram.txt"


def ensure_instagrapi():
    try:
        from instagrapi import Client  # noqa
    except ImportError:
        print("📦 Встановлюю instagrapi...")
        subprocess.run([sys.executable, "-m", "pip", "install", "instagrapi>=3.1.0"], check=True)


def load_env_credentials():
    """Пробує зчитати логін/пароль з .env файлу."""
    username = os.getenv("IG_USERNAME", "")
    password = os.getenv("IG_PASSWORD", "")
    if not username or not password:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            username = os.getenv("IG_USERNAME", "")
            password = os.getenv("IG_PASSWORD", "")
        except Exception:
            pass
    return username, password


def main():
    print("=" * 50)
    print("  Оновлення Instagram сесії Мєшані")
    print("=" * 50)
    print()
    print("⚠️  Запускай з домашнього Wi-Fi або мобільного хотспоту!")
    print()

    ensure_instagrapi()
    from instagrapi import Client

    username, password = load_env_credentials()

    if not username:
        username = input("Instagram username [solov__design]: ").strip() or "solov__design"
    if not password:
        password = getpass.getpass(f"Instagram password for {username}: ")

    print(f"\n🔐 Логінюсь як {username}...")
    cl = Client()
    cl.delay_range = [1, 3]

    try:
        cl.login(username, password)
    except Exception as e:
        print(f"\n❌ Помилка логіну: {e}")
        print("\nПоради:")
        print("  - Спробуй з іншого IP (мобільний хотспот)")
        print("  - Перевір логін/пароль в Instagram через браузер")
        sys.exit(1)

    print(f"✅ Успішно! user_id: {cl.user_id}")

    with open(LOCAL_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(cl.get_settings(), f, indent=2)
    print(f"💾 Сесія збережена: {LOCAL_SESSION_FILE}")

    # Кукі для yt-dlp (Netscape) з тієї ж сесії
    from refresh_ig_cookies import build_cookies, cookies_valid, write_netscape
    import pathlib
    cookies = build_cookies(cl, {})
    push_cookies = cookies_valid(cookies)
    if push_cookies:
        write_netscape(pathlib.Path(LOCAL_COOKIES_FILE), cookies)
        print(f"🍪 Кукі збережені: {LOCAL_COOKIES_FILE}")
    else:
        print("⚠️  Веб не прийняв кукі (mobile sessionid) — кукі на VPS не чіпаю, працюватиме instagrapi fallback.")

    auto = "--yes" in sys.argv
    print()
    deploy = "y" if auto else input(f"🚀 Залити на VPS ({VPS_HOST}) і рестартнути бота? [Y/n]: ").strip().lower()
    if deploy not in ("", "y", "yes", "так", "т"):
        print("\nЗадеплой вручну:")
        print(f"  scp {LOCAL_SESSION_FILE} {VPS_HOST}:{VPS_SESSION_PATH}")
        print(f"  scp {LOCAL_COOKIES_FILE} {VPS_HOST}:{VPS_COOKIES_PATH}")
        return

    files = [(LOCAL_SESSION_FILE, VPS_SESSION_PATH)]
    if push_cookies:
        files.append((LOCAL_COOKIES_FILE, VPS_COOKIES_PATH))
    for local, remote in files:
        print(f"   SCP {local} → {VPS_HOST}:{remote}...")
        if subprocess.run(["scp", local, f"{VPS_HOST}:{remote}"]).returncode != 0:
            print(f"❌ SCP не вдався: scp {local} {VPS_HOST}:{remote}")
            sys.exit(1)

    r = subprocess.run(
        ["ssh", VPS_HOST,
         f"chmod 600 {VPS_SESSION_PATH} && systemctl restart mieshania && sleep 2 && systemctl is-active mieshania"],
        capture_output=True, text=True,
    )
    status = (r.stdout.strip() or r.stderr.strip())
    print("✅ Бот запущений!" if status.endswith("active") else f"   Статус: {status}")
    print("\n✨ Готово! Сесія і кукі оновлені.")


if __name__ == "__main__":
    main()
