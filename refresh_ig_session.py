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
    2. Зберігає сесію в ig_session.json
    3. Пропонує залити файл на VPS і рестартнути бота
"""

import getpass
import json
import os
import subprocess
import sys

VPS_HOST = "root@91.98.134.12"
VPS_SESSION_PATH = "/var/opt/mieshania/ig_session.json"
LOCAL_SESSION_FILE = "ig_session.json"


def ensure_instagrapi():
    try:
        from instagrapi import Client  # noqa
    except ImportError:
        print("📦 Встановлюю instagrapi...")
        subprocess.run([sys.executable, "-m", "pip", "install", "instagrapi"], check=True)


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

    print()
    deploy = input(f"🚀 Залити на VPS ({VPS_HOST})? [Y/n]: ").strip().lower()
    if deploy in ("", "y", "yes", "так", "т", "y"):
        print(f"   SCP {LOCAL_SESSION_FILE} → {VPS_HOST}:{VPS_SESSION_PATH}...")
        result = subprocess.run(
            ["scp", LOCAL_SESSION_FILE, f"{VPS_HOST}:{VPS_SESSION_PATH}"]
        )
        if result.returncode != 0:
            print("❌ SCP не вдався. Задеплой вручну:")
            print(f"   scp {LOCAL_SESSION_FILE} {VPS_HOST}:{VPS_SESSION_PATH}")
            sys.exit(1)

        print("✅ Файл залито!")

        restart = input("🔄 Рестартнути бота? [Y/n]: ").strip().lower()
        if restart in ("", "y", "yes", "так", "т"):
            print("   Рестарт mieshania.service...")
            r = subprocess.run(
                ["ssh", VPS_HOST, "systemctl restart mieshania && sleep 2 && systemctl is-active mieshania"],
                capture_output=True, text=True,
            )
            status = r.stdout.strip() or r.stderr.strip()
            if "active" in status:
                print("✅ Бот запущений!")
            else:
                print(f"   Статус: {status}")
    else:
        print(f"\nЗадеплой вручну:")
        print(f"  scp {LOCAL_SESSION_FILE} {VPS_HOST}:{VPS_SESSION_PATH}")
        print(f"  ssh {VPS_HOST} systemctl restart mieshania")

    print("\n✨ Готово! Сесія оновлена.")


if __name__ == "__main__":
    main()
