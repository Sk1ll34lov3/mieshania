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
- **Інстанс:** задеплоєний на Railway, URL в `.env` → `COBALT_API_URL`
- **Ендпоінт:** `POST /` з JSON `{"url": ..., "videoQuality": ..., "downloadMode": ..., "filenameStyle": "basic"}`
- **Документація:** https://github.com/imputnet/cobalt/blob/main/docs/api.md

## VPS деплой
- **Сервер:** `root@91.98.134.12`
- **Шлях до бота:** `/var/opt/mieshania/`
- **Сервіс:** `systemctl restart mieshania`
- **Логи:** `/var/log/mieshania.downloader.log`

### Як задеплоїти зміни
```powershell
# Скопіювати файл
scp downloader.py root@91.98.134.12:/var/opt/mieshania/downloader.py

# Перезапустити
ssh root@91.98.134.12 "systemctl restart mieshania && systemctl status mieshania --no-pager"
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

## Instagram сесія (instagrapi)

Бот використовує `instagrapi` для скачки контенту Instagram коли Cobalt не справляється (пости, каруселі, сторіс).

- **Акаунт:** `solov__design`
- **Файл сесії:** `/var/opt/mieshania/ig_session.json` (на VPS) та `ig_session.json` (локально)
- **Термін дії сесії:** ~2–4 тижні

### Коли сесія протухла

Бот автоматично відправляє адмінам в Telegram:
> ⚠️ Instagram сесія Мєшані протухла! Запусти `python refresh_ig_session.py` локально

### Як оновити сесію

**ВАЖЛИВО:** запускай тільки з residential IP (домашній Wi-Fi або мобільний хотспот). VPS і datacenter IP — заблоковані Instagram.

```powershell
cd C:\repos\git\my-git\mieshania-git
python refresh_ig_session.py
```

Скрипт інтерактивно:
1. Логінить `solov__design` в Instagram
2. Зберігає `ig_session.json` локально
3. Пропонує SCP на VPS + рестарт бота

### Чому не можна авто-реlogin з VPS

Instagram блокує логіни з datacenter IP з challenge типу `com.bloks.www.ig.challenge.redirect.async`. Тому `instagram_client.py` **не намагається ре-логінитись автоматично** — тільки завантажує готову сесію з файлу.

### Структура fallback для Instagram

```
Cobalt API → FAIL
    ↓
instagrapi (ig_session.json) → якщо сесія протухла: IGSessionExpiredError → admin TG alert
    ↓
yt-dlp з cookies_instagram.txt (стаpі куки, може не працювати)
    ↓
Instagram scrape fallback
```

- **Куки більше не потрібні** для Instagram/TikTok — Cobalt сам вирішує авторизацію
- `cookies_instagram.txt`, `cookies_tiktok.txt` досі є в проекті — використовуються тільки як fallback yt-dlp
- Telegram ліміт на медіа-альбом — **10 елементів**
- Telegram ліміт на файл — **50 MB** (бот використовує 49 MB як `COBALT_MAX_FILE_MB`)
- `redirect` статус Cobalt — це валідна відповідь з прямим URL (не помилка!)
