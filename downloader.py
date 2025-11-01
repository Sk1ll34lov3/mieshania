# /var/opt/mieshania/downloader.py
# -*- coding: utf-8 -*-

import os
import re
import shlex
import subprocess
import tempfile
import pathlib
import datetime
import asyncio
from typing import Optional, List, Tuple, Dict
from html import unescape as html_unescape

import requests
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

# Шлях до yt-dlp у твоєму venv
YTDLP_BIN = "/var/opt/mieshania/.venv/bin/yt-dlp"

# Лог-фаїл для трейсингу даунлоада
LOG_FILE = "/var/log/mieshania.downloader.log"

# Які домени вважаємо підтримуваними
VIDEO_HOSTS = (
    "youtube.com", "youtu.be",
    "tiktok.com", "vm.tiktok.com",
    "instagram.com", "www.instagram.com", "m.instagram.com",
)

# Регекси для нормалізації IG-URL (витягуємо код і вибираємо p/ або reel/)
IG_CODE_RE = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]{5,})",
    re.I,
)

META_VIDEO_RE = re.compile(
    r'<meta[^>]+property=[\'"]og:(?:video:secure_url|video)[\'"][^>]+content=[\'"]([^\'"]+)[\'"]',
    re.I
)
META_IMAGE_RE = re.compile(
    r'<meta[^>]+property=[\'"]og:(?:image:secure_url|image)[\'"][^>]+content=[\'"]([^\'"]+)[\'"]',
    re.I
)
META_TITLE_RE = re.compile(
    r'<meta[^>]+property=[\'"]og:title[\'"][^>]+content=[\'"]([^\'"]+)[\'"]',
    re.I
)

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9\.\-_ ]+")


# ------------------------- Логер -------------------------
def _log(msg: str) -> None:
    """Пише рядок у лог-файл (тихо і без вилетів)."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass


# --------------------- Публічний API ---------------------
def is_supported(url: str) -> bool:
    """Чи схожий URL на підтримуваний відео-хост."""
    u = (url or "").lower()
    return any(h in u for h in VIDEO_HOSTS)


async def download_url(chat_id: int, url: str, bot) -> None:
    """
    Завантажує контент і ВІДПРАВЛЯЄ В ЧАТ.
    Підтримує: одиночне медіа або карусель (альбом до 10 елементів).
    """
    items, title = await asyncio.to_thread(_download_sync, url)  # items: List[{"path":..., "type": "photo"|"video"}]

    # Розкладаємо по групах, враховуючи обмеження Telegram
    photos_group, videos_group, docs = [], [], []
    for it in items:
        p = it["path"]
        t = it["type"]
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0

        if t == "photo":
            if size <= 10 * 1024 * 1024:
                photos_group.append(p)
            else:
                docs.append(p)
        else:
            if size <= 49 * 1024 * 1024:
                videos_group.append(p)
            else:
                docs.append(p)

    album_paths = photos_group + videos_group

    if len(album_paths) > 1:
        # Відправляємо перші 10 елементів альбомом
        media = []
        for idx, p in enumerate(album_paths[:10]):
            inp = FSInputFile(p)
            if p in photos_group:
                media.append(InputMediaPhoto(media=inp, caption=title if idx == 0 else None))
            else:
                media.append(InputMediaVideo(media=inp, caption=title if idx == 0 else None))
        await bot.send_media_group(chat_id, media)

        # Якщо щось не влізло (більше 10) — довантажуємо як документи
        for p in album_paths[10:]:
            await bot.send_document(chat_id, FSInputFile(p), caption=title)

        # Великі файли також як документи
        for p in docs:
            await bot.send_document(chat_id, FSInputFile(p), caption=title)
    else:
        # Один файл → як і раніше
        it = items[0]
        p, t = it["path"], it["type"]
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0

        f = FSInputFile(p)
        if t == "photo":
            if size <= 10 * 1024 * 1024:
                await bot.send_photo(chat_id, f, caption=title)
            else:
                await bot.send_document(chat_id, f, caption=title)
        else:
            if size <= 49 * 1024 * 1024:
                await bot.send_video(chat_id, f, caption=title)
            else:
                await bot.send_document(chat_id, f, caption=title)

    # Прибираємо тимчасові файли
    for it in items:
        try:
            os.remove(it["path"])
        except Exception:
            pass


# --------------------- Внутрішня логіка ------------------
def _sanitize_name(name: str, max_len: int = 80) -> str:
    name = name.strip().replace("\n", " ").replace("\r", " ")
    name = SAFE_NAME_RE.sub("_", name)
    if not name:
        name = "file"
    return name[:max_len]


def _normalize_instagram_url(url: str) -> str:
    """
    Приводить IG-URL до чистого вигляду:
      https://www.instagram.com/p/<CODE>/
      або
      https://www.instagram.com/reel/<CODE>/
    Якщо не можемо визначити — повертаємо як є.
    """
    m = IG_CODE_RE.search(url)
    if not m:
        return url
    code = m.group(1)
    return f"https://www.instagram.com/p/{code}/" if "/p/" in url else f"https://www.instagram.com/reel/{code}/"


def _pick_cookies_for(url: str) -> Optional[str]:
    """
    Вибирає cookies-файл за доменом, читає з ENV:
      YDL_COOKIES_INSTAGRAM (або YDL_COOKIES_IG)
      YDL_COOKIES_TIKTOK (або YDL_COOKIES_TT)
      YDL_COOKIES_YOUTUBE (або YDL_COOKIES_YT)
      YDL_COOKIES (fallback)
    """
    u = url.lower()
    if "instagram.com" in u:
        return os.getenv("YDL_COOKIES_INSTAGRAM") or os.getenv("YDL_COOKIES_IG")
    if "tiktok.com" in u or "vm.tiktok.com" in u:
        return os.getenv("YDL_COOKIES_TIKTOK") or os.getenv("YDL_COOKIES_TT")
    if "youtube.com" in u or "youtu.be" in u:
        return os.getenv("YDL_COOKIES_YOUTUBE") or os.getenv("YDL_COOKIES_YT")
    return os.getenv("YDL_COOKIES")


def _base_headers(url: str) -> List[str]:
    """Заголовки, корисні для реферера."""
    return ["--add-header", f"Referer:{url}"]


def _yt_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
    if cookies_file:
        base += ["--cookies", cookies_file]
    cmdA = base[:]  # best auto
    cmdB = base[:] + ["-f", "96/95/94/93/92/91/best[protocol~=m3u8]/best"]
    return [cmdA, cmdB]


def _tt_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
    if cookies_file:
        base += ["--cookies", cookies_file]
    return [base]


def _ig_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    # Мобільний UA краще себе показує на IG
    ua = os.getenv("YDL_UA_IG") or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1"
    )
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url] + _base_headers(url) + [
        "--user-agent", ua,
        "--extractor-args", "instagram:reels_video=1,story=1,high_quality=1,allow_extra=1",
        "--no-warnings",
    ]
    if cookies_file:
        base += ["--cookies", cookies_file]

    cmdA = base[:] + ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best", "--merge-output-format", "mp4"]
    cmdB = base[:] + ["--merge-output-format", "mp4"]
    cmdC = base[:] + ["--force-generic-extractor", "--merge-output-format", "mp4"]
    return [cmdA, cmdB, cmdC]


def _build_cmds(url: str, outtmpl: str) -> List[List[str]]:
    """Повертає список команд (різних стратегій) для yt-dlp."""
    if "instagram.com" in url.lower():
        url = _normalize_instagram_url(url)
    cookies = _pick_cookies_for(url)

    if "instagram.com" in url.lower():
        return _ig_cmds(url, outtmpl, cookies)
    if "tiktok.com" in url.lower() or "vm.tiktok.com" in url.lower():
        return _tt_cmds(url, outtmpl, cookies)
    return _yt_cmds(url, outtmpl, cookies)


def _run_cmd(cmd: List[str]) -> None:
    """Запускає одну команду yt-dlp та кидає RuntimeError, якщо вона впала."""
    _log("RUN: " + " ".join(shlex.quote(x) for x in cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=340)
    if res.stdout:
        _log("STDOUT: " + res.stdout.strip()[:4000])
    if res.stderr:
        _log("STDERR: " + res.stderr.strip()[:4000])
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or res.stdout.strip() or "yt-dlp error")


def _netscape_to_requests_cookies(cookies_path: str) -> dict:
    """
    Грубе перетворення Netscape cookies у dict для requests:
    шукаємо sessionid/csrftoken/ds_user_id тощо.
    """
    jar = {}
    try:
        with open(cookies_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line or line.startswith("#") or line.strip() == "":
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    name = parts[-2]
                    value = parts[-1]
                    jar[name] = value
    except Exception as e:
        _log(f"cookies parse warn: {e}")
    return jar


def _ig_fetch_html(url: str, cookies_file: Optional[str]) -> str:
    """Завантажує HTML сторінки поста/reel Instagram з кукі та правильним UA/Referer."""
    url_norm = _normalize_instagram_url(url)
    ua = os.getenv("YDL_UA_IG") or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1"
    )
    headers = {
        "User-Agent": ua,
        "Referer": url_norm,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    cookies = _netscape_to_requests_cookies(cookies_file) if cookies_file else {}

    candidates = [
        url_norm,
        url_norm.replace("www.instagram.com", "m.instagram.com"),
        url_norm.replace("m.instagram.com", "www.instagram.com"),
        re.sub(r"/p/([A-Za-z0-9_-]+)/", r"/reel/\1/", url_norm),
        re.sub(r"/reel/([A-Za-z0-9_-]+)/", r"/p/\1/", url_norm),
        url_norm + "?__a=1&__d=dis",
        url_norm.replace("www.instagram.com", "m.instagram.com") + "?__a=1&__d=dis",
    ]

    for u in candidates:
        try:
            _log(f"IG SCRAPE GET: {u}")
            r = requests.get(u, headers=headers, cookies=cookies, timeout=25, allow_redirects=True)
            r.raise_for_status()
            return r.text
        except requests.HTTPError as e:
            _log(f"IG SCRAPE candidate fail: {u} -> {e}")
        except Exception as e:
            _log(f"IG SCRAPE candidate err: {u} -> {e}")

    # остання спроба оригіналом
    r = requests.get(url_norm, headers=headers, cookies=cookies, timeout=25, allow_redirects=True)
    r.raise_for_status()
    return r.text


def _ig_scrape_media(url: str, cookies_file: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Повертає (media_url, media_type, title)
      - media_type: "video" або "photo"
      - якщо відео немає, пробує знайти фото (og:image)
    """
    html = _ig_fetch_html(url, cookies_file)

    m = META_VIDEO_RE.search(html)
    if m:
        media_url = html_unescape(m.group(1))
        title = META_TITLE_RE.search(html).group(1) if META_TITLE_RE.search(html) else "instagram"
        return media_url, "video", title

    m2 = META_IMAGE_RE.search(html)
    if m2:
        media_url = html_unescape(m2.group(1))
        title = META_TITLE_RE.search(html).group(1) if META_TITLE_RE.search(html) else "instagram"
        return media_url, "photo", title

    return None, None, None


def _save_url_to_file(media_url: str, referer: str, cookies_file: Optional[str], preferred_ext: str) -> Tuple[str, str]:
    """
    Качає media_url у файл, повертає (final_path, title_stub).
    """
    ua = os.getenv("YDL_UA_IG") or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1"
    )
    headers = {
        "User-Agent": ua,
        "Referer": referer,
        "Accept": "*/*",
    }
    cookies = _netscape_to_requests_cookies(cookies_file) if cookies_file else {}

    with tempfile.TemporaryDirectory() as td2:
        out_file = os.path.join(td2, f"ig.{preferred_ext}")
        with requests.get(media_url, headers=headers, cookies=cookies, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(out_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        f.write(chunk)

        final_dir = "/var/opt/mieshania/tmp"
        os.makedirs(final_dir, exist_ok=True)
        final_path = os.path.join(final_dir, os.path.basename(out_file))
        try:
            os.replace(out_file, final_path)
        except Exception:
            import shutil
            shutil.copy2(out_file, final_path)
        return final_path, "instagram"


def _download_sync(url: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Синхронно качає контент і повертає (items, title):
      items: список {"path": str, "type": "photo"|"video"}
      title: str
    Для IG-каруселей залишає кілька файлів (через %(autonumber)).
    """
    _log(f"download START: {url}")
    with tempfile.TemporaryDirectory() as td:
        # ВАЖЛИВО: унікальні імена для multi-entry (каруселі)
        outtmpl = os.path.join(td, "%(title).80s-%(autonumber)03d.%(ext)s")
        cmds = _build_cmds(url, outtmpl)

        last_err: Optional[Exception] = None

        # 1) yt-dlp спроби
        for i, cmd in enumerate(cmds, 1):
            try:
                _log(f"[try {i}/{len(cmds)}]")
                _run_cmd(cmd)
                last_err = None
                break
            except Exception as e:
                last_err = e
                _log(f"[try {i}] FAIL: {e}")

        # 2) Якщо IG і yt-dlp не вдалося — fallback (1 медіа)
        if last_err and "instagram.com" in url.lower():
            try:
                cookies_path = _pick_cookies_for(url)
                media_url, media_type, title = _ig_scrape_media(url, cookies_path)
                if media_url and media_type:
                    preferred_ext = "mp4" if media_type == "video" else "jpg"
                    final_path, _ = _save_url_to_file(media_url, _normalize_instagram_url(url), cookies_path, preferred_ext)
                    safe_title = _sanitize_name(title or "instagram")
                    return ([{"path": final_path, "type": media_type}], safe_title)
            except Exception as e2:
                _log(f"IG SCRAPE FAIL: {e2}")

        if last_err:
            _log(f"ALL FAIL for {url}")
            raise last_err

        # 3) Забираємо ВСІ файли, що викачав yt-dlp (карусель → кілька)
        paths = []
        for p in sorted(pathlib.Path(td).glob("*")):
            if p.is_file():
                paths.append(str(p))
        if not paths:
            raise RuntimeError("Файли після завантаження не знайдено")

        # 4) Визначимо типи та перенесемо у стабільну папку
        final_dir = "/var/opt/mieshania/tmp"
        os.makedirs(final_dir, exist_ok=True)

        items: List[Dict[str, str]] = []
        for p in paths:
            ext = pathlib.Path(p).suffix.lower()
            media_type = "photo" if ext in {".jpg", ".jpeg", ".png", ".webp"} else "video"
            final_path = os.path.join(final_dir, os.path.basename(p))
            try:
                os.replace(p, final_path)
            except Exception:
                import shutil
                shutil.copy2(p, final_path)
            items.append({"path": final_path, "type": media_type})

        # 5) Тайтл — з першого файлу (до суфікса -NNN)
        base_stem = pathlib.Path(paths[0]).stem
        # відрізаємо -001/-002...
        if "-" in base_stem and base_stem.rsplit("-", 1)[-1].isdigit():
            title_raw = base_stem.rsplit("-", 1)[0]
        else:
            title_raw = base_stem
        title = _sanitize_name(title_raw or "file")

        _log(f"SUCCESS: {len(items)} item(s) [{title}]")
        return items, title
