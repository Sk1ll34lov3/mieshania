---
name: refresh-ig-cookies
description: Перегенерувати Instagram кукі (cookies_instagram.txt) і сесію instagrapi (ig_session.json) з локального residential IP та залити на VPS мєшані. Використовуй, коли сторіси/IG не качаються з "This content is unreachable" або в кукі немає sessionid.
---

# Refresh Instagram cookies from local IP

Логін в Instagram з датацентрового IP (VPS) часто блокується, тому оновлюємо з домашнього IP користувача.

## Кроки

1. **Діагностика** (read-only): `ssh mieshania "awk -F'\t' '!/^#/ && NF>=7 {print \$6}' /var/opt/mieshania/cookies_instagram.txt | tr '\n' ' '"` — якщо немає `sessionid`, кукі мертві. Також перевір `grep -a 'unreachable\|INSTAGRAPI' /var/log/mieshania.downloader.log | tail`.
2. **Логін робить користувач, не ти.** Скрипт питає пароль інтерактивно (`getpass`) або бере `IG_USERNAME`/`IG_PASSWORD` з оточення користувача. Ніколи не проси пароль у чат і не передавай його аргументами. Попроси користувача виконати в терміналі сесії (префікс `!`) з кореня репо:
   ```
   ! python refresh_ig_session.py --yes
   ```
   (потрібен `pip install instagrapi requests python-dotenv`). Скрипт сам логіниться, перевіряє кукі, зберігає `ig_session.json` + `cookies_instagram.txt`, scp на VPS (`mieshania` з ~/.ssh/config), chmod 600, `systemctl restart mieshania`.
3. **Перевірка**: `ssh mieshania "/var/opt/mieshania/.venv/bin/python /var/opt/mieshania/refresh_ig_cookies.py --check"` (exit 0 = валідні), потім попроси користувача кинути боту сторіс-лінк і подивись `tail` логу.
4. Якщо Instagram просить challenge/2FA — користувач підтверджує в застосунку Instagram і запускає скрипт ще раз. Для 2FA через authenticator задай `IG_TOTP_SECRET` у оточенні.

## Правила
- Файли `ig_session.json`, `cookies_instagram.txt` не комітити (є в .gitignore) і не виводити їх вміст у чат.
- Деплой/рестарт на VPS — тільки з відома користувача.
