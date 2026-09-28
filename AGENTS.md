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

## Важливі нюанси
- **Куки більше не потрібні** для Instagram/TikTok — Cobalt сам вирішує авторизацію
- `cookies_instagram.txt`, `cookies_tiktok.txt` досі є в проекті — використовуються тільки як fallback yt-dlp
- Telegram ліміт на медіа-альбом — **10 елементів**
- Telegram ліміт на файл — **50 MB** (бот використовує 49 MB як `COBALT_MAX_FILE_MB`)
- `redirect` статус Cobalt — це валідна відповідь з прямим URL (не помилка!)
