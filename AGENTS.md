# Mieshania Bot — Agent Instructions

## Що це за проект
Telegram-бот для скачки медіа з Instagram, TikTok, YouTube та інших платформ.
Написаний на Python + aiogram 3. Деплоїться на Ubuntu VPS як systemd-сервіс.

## Структура
```
bot.py                  — точка входу, запуск aiogram
config.py               — конфіг з .env (токени, Cobalt, DB)
downloader.py           — вся логіка скачки (Cobalt → yt-dlp → fallback)
handlers/media.py       — обробники команд /dl_hd, /dl_sd, /dl_audio, /dl_info + авто-реакція на лінки
services/media.py       — утиліти: витягування URL з повідомлень, клавіатура кнопок
services/limits.py      — rate limiting по юзеру/чату
.env                    — секрети і конфіг (не в гіт)
```

## Стратегія скачки (downloader.py)
1. **Cobalt API** (`COBALT_ENABLED=1`) — основний шлях, без куків
2. **yt-dlp** — fallback якщо Cobalt не впорався
3. **Instagram scrape** — last-resort fallback для IG

### Статуси відповіді Cobalt і як вони обробляються
| Статус | Що означає | Обробка |
|--------|-----------|---------|
| `tunnel` | Cobalt проксі-тунель | `_download_direct_media()` |
| `redirect` | Прямий CDN URL (Instagram) | `_download_direct_media()` |
| `picker` | Slideshow / фото-карусель (TikTok) | `_download_cobalt_picker()` — качає всі фото як альбом (max 10, Telegram ліміт) |
| `error` | Помилка | fallback на yt-dlp |

## Cobalt API
- **Інстанс:** docker-контейнер `cobalt` на самому VPS (`COBALT_API_URL=http://localhost:9000`). Railway-інстанс більше не існує.
- **Ендпоінт:** `POST /` з JSON `{"url": ..., "videoQuality": ..., "downloadMode": ..., "filenameStyle": "basic"}`
- **Документація:** https://github.com/imputnet/cobalt/blob/main/docs/api.md

## VPS деплой
- **Сервер:** `root@91.98.134.12`
- **Шлях до бота:** `/var/opt/mieshania/`
- **Сервіс:** `systemctl restart mieshania`
- **Логи:** `/var/log/mieshania.downloader.log`

### SSH-доступ (нестандартний ключ!)
Ключ НЕ дефолтний. У `~/.ssh/config` є аліас `mieshania` (→ `root@91.98.134.12`, ключ `~/.ssh/id_ed25519_mieshania`).
Завжди використовуй `ssh mieshania ...` / `scp file mieshania:/path`, а не `root@91.98.134.12` напряму —
інакше буде `Permission denied (publickey,password)`.
(`hetzner_ed25519` — інший ключ, для цього сервера не підходить.)

### Оновлення yt-dlp (Instagram/YouTube ламаються регулярно)
yt-dlp стоїть у venv бота, не в системі. Симптоми: `Instagram sent an empty media response`,
`Unable to extract ...`. Лікується оновленням:
```bash
ssh mieshania "/var/opt/mieshania/.venv/bin/pip install -U 'yt-dlp[default]' && systemctl restart mieshania && systemctl is-active mieshania"
```
Не плутати помилки:
- `There is no video in this post` — IG-пост лише з фото; yt-dlp такі не вміє, їх має брати Cobalt (`picker`/`redirect`). Оновлення не допоможе.
- YouTube `No supported JavaScript runtime` — потрібен `deno` (на VPS стоїть у `/usr/local/bin/deno`).

### YouTube: тільки Shorts
- `is_supported()` пропускає з YouTube лише `/shorts/`; решта → відповідь `YT_NOT_SUPPORTED_MSG` ("Not supported").
- Качає yt-dlp з `cookies_youtube.txt` (Cobalt на VPS для YouTube дає `error.api.youtube.login`).
- **Ключове:** кукі мусять бути ПОВНІ (`SID, HSID, SSID, APISID, SAPISID, __Secure-1PSID, LOGIN_INFO`).
  Неповний набір (лише `__Secure-3PSID`/`3PAPISID`) → `Sign in to confirm you're not a bot`.
  IP датацентру при цьому НЕ проблема; PO-токен плагін (`bgutil`, docker `bgutil-provider`) і `player_client` не потрібні.
- Поки сесія жива, VPS сам підтримує кукі: yt-dlp перезаписує файл ротованими токенами при кожному запуску.
- Якщо знову `Sign in to confirm...` — сесія померла. Залогінься в YouTube акаунтом бота у Firefox на ПК і запусти
  `python scripts/refresh_yt_cookies.py` (перевірить VPS, за потреби експортує з Firefox і залле; `--force` — примусово).
  Логін на самому VPS неможливий (Google блокує датацентр). Скрипт можна повісити на Task Scheduler (команда в докстрингу).
- Ніколи не клади кукі в репо / чат. У файлі сесія акаунта.

### Як задеплоїти зміни
**Перед `scp` порівняй хеші з VPS** — на сервері бувають правки, яких немає в репо (так було з `instagrapi`-fallback у `downloader.py`):
```bash
ssh mieshania "cd /var/opt/mieshania && sha256sum downloader.py handlers/media.py handlers/basic.py"
```
Якщо відрізняється — стягни серверний файл (`scp mieshania:...`), накладай правки поверх нього і онови репо.
```powershell
# Бекап + копіювання (scp інколи рветься з "Connection closed" — перевір хеш після заливки)
scp downloader.py mieshania:/var/opt/mieshania/downloader.py

# Перезапустити
ssh mieshania "systemctl restart mieshania && systemctl status mieshania --no-pager"
```

## Змінні .env (ключові)
```env
BOT_TOKEN=...
COBALT_ENABLED=1
COBALT_API_URL=https://cobalt-api-production-d29c.up.railway.app
COBALT_TIMEOUT=25
COBALT_MAX_FILE_MB=49
DB_HOST=...
```

## Важливі нюанси
- **Куки більше не потрібні** для Instagram/TikTok — Cobalt сам вирішує авторизацію
- `cookies_instagram.txt`, `cookies_tiktok.txt` досі є в проекті — використовуються тільки як fallback yt-dlp
- Telegram ліміт на медіа-альбом — **10 елементів**
- Telegram ліміт на файл — **50 MB** (бот використовує 49 MB як `COBALT_MAX_FILE_MB`)
- `redirect` статус Cobalt — це валідна відповідь з прямим URL (не помилка!)
