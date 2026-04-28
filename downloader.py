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
import json
from urllib.parse import urlparse
from typing import Optional, List, Tuple, Dict

import requests
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo

try:
    from config import (
        COBALT_ENABLED,
        COBALT_API_URL,
        COBALT_TIMEOUT,
        COBALT_MAX_FILE_MB,
        COBALT_AUTH,
    )
except Exception:
    COBALT_ENABLED = False
    COBALT_API_URL = "https://api.cobalt.tools/api/json"
    COBALT_TIMEOUT = 25
    COBALT_MAX_FILE_MB = 49
    COBALT_AUTH = None


# -------------------- Константи середовища --------------------

# yt-dlp всередині venv бота
YTDLP_BIN = "/var/opt/mieshania/.venv/bin/yt-dlp"

# Лог-файл саме даунлоадера
LOG_FILE = "/var/log/mieshania.downloader.log"

# Куди складаємо тимчасові результати (звідси вже читає бот)
TMP_DIR = "/var/opt/mieshania/tmp"

# Фіксовані шляхи до cookies (ти їх надав)
INSTAGRAM_COOKIES = "/var/opt/mieshania/cookies_instagram.txt"
YOUTUBE_COOKIES   = "/var/opt/mieshania/cookies_youtube.txt"
TIKTOK_COOKIES    = "/var/opt/mieshania/cookies_tiktok.txt"

# Хости, які вважаємо підтримуваними
VIDEO_HOSTS = (
    "youtube.com", "youtu.be",
    "tiktok.com", "vm.tiktok.com",
    "instagram.com", "www.instagram.com", "m.instagram.com",
    "x.com", "twitter.com",
    "reddit.com",
    "pinterest.com",
)

# Regex для звичайних IG постів /reel/p
IG_CODE_RE = re.compile(
    r"https?://(?:www\.|m\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]{5,})",
    re.I,
)

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9\.\-_ ]+")


# ===================== Утиліти =====================

def _log(msg: str) -> None:
    """Пише рядок у лог-файл (тихо і без вилетів)."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass


def _sanitize_name(name: str, max_len: int = 80) -> str:
    name = name.strip().replace("\n", " ").replace("\r", " ")
    name = SAFE_NAME_RE.sub("_", name)
    if not name:
        name = "file"
    return name[:max_len]


def _try_cobalt(
    url: str,
    *,
    download_mode: str = "auto",
    video_quality: str = "1080",
    audio_format: str = "mp3",
) -> Optional[Dict]:
    """
    Пробує cobalt.tools API.

    Повертає один з варіантів або None:
      - {"url": str, "filename": str, "status": "tunnel"|"redirect"|"success"}  — одиночний файл
      - {"status": "picker", "picker": [...], "audio": str|None, "audioFilename": str|None}  — slideshow (напр. TikTok фото)
    """
    if not COBALT_ENABLED:
        return None

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if COBALT_AUTH:
        headers["Authorization"] = str(COBALT_AUTH)
    payload: Dict[str, object] = {
        "url": url,
        "downloadMode": download_mode,
        "videoQuality": video_quality,
        "filenameStyle": "basic",
    }
    if download_mode == "audio":
        payload["audioFormat"] = audio_format

    try:
        r = requests.post(COBALT_API_URL, headers=headers, json=payload, timeout=COBALT_TIMEOUT)
    except Exception as e:
        _log(f"COBALT FAIL: request error: {e}")
        return None

    if not (200 <= r.status_code < 300):
        try:
            data = r.json()
            if isinstance(data, dict) and str(data.get("status") or "").lower() == "error":
                err = data.get("error") or {}
                code = (err.get("code") if isinstance(err, dict) else None) or ""
                text = str(data.get("text") or "")
                if text and "v7 api has been shut down" in text.lower():
                    _log("COBALT FAIL: v7 api shutdown (wrong endpoint)")
                elif code:
                    _log(f"COBALT FAIL: {code}")
                else:
                    _log(f"COBALT FAIL: http {r.status_code}")
            else:
                _log(f"COBALT FAIL: http {r.status_code}")
        except Exception:
            _log(f"COBALT FAIL: http {r.status_code}")
        return None

    try:
        data = r.json()
    except Exception:
        _log("COBALT FAIL: non-json response")
        return None

    status = str(data.get("status") or "").lower()

    # Slideshow / фото-карусель (напр. TikTok photo post)
    if status == "picker":
        picker = data.get("picker")
        if isinstance(picker, list) and picker:
            _log(f"COBALT PICKER: {len(picker)} item(s)")
            return {
                "status": "picker",
                "picker": picker,
                "audio": data.get("audio"),
                "audioFilename": data.get("audioFilename"),
            }
        _log("COBALT FAIL: picker empty")
        return None

    # "success"/"tunnel" — cobalt proxy, "redirect" — прямий CDN url (напр. Instagram)
    if status not in ("success", "tunnel", "redirect"):
        if status in ("error", "local-processing"):
            err = data.get("error") or {}
            code = (err.get("code") if isinstance(err, dict) else None) or ""
            _log(f"COBALT FAIL: status={status} code={code}".strip())
        else:
            _log(f"COBALT FAIL: status={status or 'unknown'}")
        return None

    direct = data.get("url")
    if not isinstance(direct, str) or not direct.startswith("http"):
        _log("COBALT FAIL: missing url")
        return None

    filename = data.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        filename = "file"

    return {"url": direct, "filename": filename, "status": status}


def _download_cobalt_picker(picker_res: Dict, source_url: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Завантажує slideshow (picker) від cobalt — список фото/відео.
    Telegram приймає максимум 10 елементів в альбомі.
    """
    os.makedirs(TMP_DIR, exist_ok=True)
    items: List[Dict[str, str]] = []
    picker = picker_res.get("picker") or []

    # Telegram limit: max 10 items per album
    for i, entry in enumerate(picker[:10]):
        media_url = entry.get("url") if isinstance(entry, dict) else None
        media_type_hint = (entry.get("type") or "photo").lower() if isinstance(entry, dict) else "photo"
        if not media_url:
            continue
        try:
            resp = requests.get(media_url, stream=True, timeout=COBALT_TIMEOUT, headers={"Referer": source_url})
            if not (200 <= resp.status_code < 300):
                _log(f"COBALT PICKER item {i}: http {resp.status_code}")
                continue

            ctype = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                "video/mp4": ".mp4", "video/webm": ".webm",
            }
            ext = ext_map.get(ctype) or (".jpg" if media_type_hint == "photo" else ".mp4")
            final_path = os.path.join(TMP_DIR, f"picker_{i:03d}{ext}")

            max_bytes = int(COBALT_MAX_FILE_MB) * 1024 * 1024
            wrote = 0
            with open(final_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 128):
                    if not chunk:
                        continue
                    wrote += len(chunk)
                    if wrote > max_bytes:
                        raise RuntimeError("picker item too large")
                    f.write(chunk)

            media_type = "photo" if pathlib.Path(final_path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else "video"
            items.append({"path": final_path, "type": media_type})
        except Exception as e:
            _log(f"COBALT PICKER item {i} FAIL: {e}")
            continue

    if not items:
        raise RuntimeError("cobalt picker: не вдалось завантажити жодного елементу")

    _log(f"COBALT PICKER SUCCESS: {len(items)} item(s)")
    return items, "tiktok_slideshow"


def _download_direct_media(media_url: str, source_url: str, title: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Качає пряме посилання (cobalt tunnel) у TMP_DIR.
    Повертає (items, title) у форматі як після yt-dlp.
    """
    os.makedirs(TMP_DIR, exist_ok=True)

    safe_title = _sanitize_name(title or "file")
    tmp_path = os.path.join(TMP_DIR, f"{safe_title}")

    try:
        resp = requests.get(media_url, stream=True, timeout=COBALT_TIMEOUT, headers={"Referer": source_url})
    except Exception as e:
        raise RuntimeError(f"cobalt download error: {e}")

    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"cobalt download http {resp.status_code}")

    # визначаємо розмір якщо є
    max_bytes = int(COBALT_MAX_FILE_MB) * 1024 * 1024
    clen = resp.headers.get("Content-Length") or resp.headers.get("Estimated-Content-Length") or ""
    try:
        size_hint = int(clen)
    except Exception:
        size_hint = 0
    if size_hint and size_hint > max_bytes:
        raise RuntimeError("cobalt file too large")

    # підбираємо розширення
    ctype = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    ext_map = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = ext_map.get(ctype) or pathlib.Path(urlparse(media_url).path).suffix or ".mp4"
    if not ext.startswith("."):
        ext = "." + ext

    final_path = tmp_path
    if not final_path.lower().endswith(ext.lower()):
        final_path = tmp_path + ext

    # запис у файл
    wrote = 0
    try:
        with open(final_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue
                wrote += len(chunk)
                if wrote > max_bytes:
                    raise RuntimeError("cobalt file too large")
                f.write(chunk)
    except Exception:
        try:
            os.remove(final_path)
        except Exception:
            pass
        raise

    # класифікація медіа
    ext_l = pathlib.Path(final_path).suffix.lower()
    if ext_l in {".jpg", ".jpeg", ".png", ".webp"}:
        media_type = "photo"
    elif ext_l in {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav"}:
        media_type = "audio"
    else:
        media_type = "video"

    return [{"path": final_path, "type": media_type}], _sanitize_name(pathlib.Path(final_path).stem or safe_title)


def _parse_netscape_cookies_file(path: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name = parts[5].strip()
                    value = parts[6].strip()
                    if name:
                        cookies[name] = value
    except Exception:
        pass
    return cookies


def _find_first_media_url(obj) -> Optional[str]:
    """
    Дуже простий пошук першого відео/аудіо URL у JSON.
    Використовується як best-effort для IG fallback.
    """
    try:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("video_url", "contentUrl", "url") and isinstance(v, str) and v.startswith("http"):
                    return v
                got = _find_first_media_url(v)
                if got:
                    return got
        elif isinstance(obj, list):
            for it in obj:
                got = _find_first_media_url(it)
                if got:
                    return got
    except Exception:
        return None
    return None


def _try_instagram_scrape_fallback(url: str) -> Optional[str]:
    """
    Best-effort fallback для Instagram, якщо yt-dlp впав.
    НЕ гарантує успіх (Instagram часто блокує).

    Повертає прямий media url або None.
    """
    url_norm = _normalize_instagram_url(url)
    if "instagram.com" not in (url_norm or "").lower():
        return None

    # пробуємо __a=1 JSON
    probe = url_norm.rstrip("/") + "/?__a=1&__d=dis"
    ua = os.getenv("YDL_UA_IG") or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1"
    )

    cookies = _parse_netscape_cookies_file(INSTAGRAM_COOKIES)
    try:
        r = requests.get(
            probe,
            timeout=COBALT_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": ua, "Referer": url_norm},
            cookies=cookies or None,
        )
        if not (200 <= r.status_code < 300):
            return None
        try:
            j = r.json()
        except Exception:
            # інколи повертає html
            txt = r.text or ""
            m = re.search(r'"video_url"\s*:\s*"([^"]+)"', txt)
            if m:
                return m.group(1).encode("utf-8").decode("unicode_escape")
            return None
        return _find_first_media_url(j)
    except Exception:
        return None


def _download_with_fallbacks_sync(url: str, mode: str = "auto") -> Tuple[List[Dict[str, str]], str]:
    """
    cobalt.tools → yt-dlp → (IG scrape fallback) strategy.

    mode: auto|hd|sd|audio|file
    """
    mode = (mode or "auto").lower()

    # ----- COBALT -----
    if COBALT_ENABLED:
        _log(f"COBALT START: {url} mode={mode}")
        try:
            if mode == "audio":
                res = _try_cobalt(url, download_mode="audio", video_quality="1080")
                if res:
                    _log("COBALT SUCCESS")
                    return _download_direct_media(res["url"], url, res.get("filename") or "audio")
            else:
                qualities = ["1080"]
                if mode in ("hd", "file"):
                    qualities = ["max", "2160", "1440", "1080", "720", "480", "360"]
                elif mode == "sd":
                    qualities = ["480", "360"]

                for q in qualities:
                    res = _try_cobalt(url, download_mode="auto", video_quality=q)
                    if not res:
                        continue

                    # Slideshow / фото-карусель (TikTok photo, тощо)
                    if res.get("status") == "picker":
                        try:
                            items, title = _download_cobalt_picker(res, url)
                            _log("COBALT PICKER SUCCESS")
                            return items, title
                        except Exception as e:
                            _log(f"COBALT PICKER FAIL: {e}")
                        break  # picker не залежить від якості — не повторюємо

                    try:
                        items, title = _download_direct_media(res["url"], url, res.get("filename") or "video")
                        _log("COBALT SUCCESS")
                        return items, title
                    except Exception as e:
                        _log(f"COBALT FAIL: {e}")
                        continue
        except Exception as e:
            _log(f"COBALT FAIL: {e}")

        _log("COBALT FAIL")

    # ----- YT-DLP -----
    _log("FALLBACK YTDLP")
    profile = "auto"
    if mode == "audio":
        profile = "audio"
    elif mode == "sd":
        profile = "sd"
    elif mode in ("hd", "file"):
        profile = "hd"

    try:
        return _download_sync(url, profile=profile)
    except Exception as e:
        # ----- IG scrape fallback -----
        if "instagram.com" in (url or "").lower():
            media = _try_instagram_scrape_fallback(url)
            if media:
                _log("IG SCRAPE FALLBACK SUCCESS")
                return _download_direct_media(media, url, "instagram")
        raise e


def _normalize_instagram_url(url: str) -> str:
    """
    Для звичайних постів/reel нормалізуємо в:
      https://www.instagram.com/p/<CODE>/
      або
      https://www.instagram.com/reel/<CODE>/

    Для stories:
      https://www.instagram.com/stories/<user>/<story_id>/

    Параметри типу utm/... прибираємо.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    host = parsed.netloc.lower()
    if "instagram.com" not in host:
        return url

    path = parsed.path or ""
    parts = [p for p in path.split("/") if p]

    # stories/USER/ID[/...]
    if len(parts) >= 3 and parts[0] == "stories":
        user = parts[1]
        story_id = parts[2]
        return f"https://www.instagram.com/stories/{user}/{story_id}/"

    # Звичайні пости /p/ або /reel/
    m = IG_CODE_RE.search(url)
    if not m:
        return url

    code = m.group(1)
    if "/p/" in path:
        return f"https://www.instagram.com/p/{code}/"
    return f"https://www.instagram.com/reel/{code}/"


def _pick_cookies_for(url: str) -> Optional[str]:
    """Повертає шлях до cookies-файлу за доменом."""
    u = url.lower()
    if "instagram.com" in u:
        return INSTAGRAM_COOKIES
    if "tiktok.com" in u or "vm.tiktok.com" in u:
        return TIKTOK_COOKIES
    if "youtube.com" in u or "youtu.be" in u:
        return YOUTUBE_COOKIES
    return None


def _base_headers(url: str) -> List[str]:
    """Заголовки, корисні для Referer."""
    return ["--add-header", f"Referer:{url}"]


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


# ===================== Конфіг yt-dlp =====================

def _yt_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
    if cookies_file:
        base += ["--cookies", cookies_file]

    # Дві спроби з різними форматами
    cmdA = base[:]  # best авто
    cmdB = base[:] + ["-f", "96/95/94/93/92/91/best[protocol~=m3u8]/best"]
    return [cmdA, cmdB]


def _tt_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
    if cookies_file:
        base += ["--cookies", cookies_file]
    return [base]


def _ig_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    """
    Instagram:
      - для stories додаємо --no-playlist, щоб качати тільки одну stories по її URL
      - для постів/рилів лишаємо плейлисти (каруселі) як є
    """
    url_norm = _normalize_instagram_url(url)
    is_story = "/stories/" in url_norm

    ua = os.getenv("YDL_UA_IG") or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1"
    )

    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url_norm] + _base_headers(url_norm) + [
        "--user-agent", ua,
        "--extractor-args", "instagram:reels_video=1,story=1,high_quality=1,allow_extra=1",
        "--no-warnings",
    ]

    if is_story:
        # Ключовий момент: тільки одна сторі по URL
        base.append("--no-playlist")

    if cookies_file:
        base += ["--cookies", cookies_file]

    # Кілька варіантів форматів
    cmdA = base[:] + ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best", "--merge-output-format", "mp4"]
    cmdB = base[:] + ["--merge-output-format", "mp4"]
    return [cmdA, cmdB]


def _audio_cmds(url: str, outtmpl: str, cookies_file: Optional[str]) -> List[List[str]]:
    base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url] + _base_headers(url) + ["--no-warnings"]
    if cookies_file:
        base += ["--cookies", cookies_file]
    cmd = base[:] + ["-x", "--audio-format", "mp3", "--audio-quality", "0", "--no-playlist"]
    return [cmd]


def _build_cmds(url: str, outtmpl: str, profile: str = "auto") -> List[List[str]]:
    """Повертає список команд (різних стратегій) для yt-dlp."""
    u = url.lower()
    cookies = _pick_cookies_for(url)

    if profile == "audio":
        return _audio_cmds(url, outtmpl, cookies)

    if "instagram.com" in u:
        cmds = _ig_cmds(url, outtmpl, cookies)
        if profile == "sd":
            # більш легка якість, якщо доступно
            url_norm = _normalize_instagram_url(url)
            base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url_norm] + _base_headers(url_norm) + [
                "--no-warnings",
                "--extractor-args", "instagram:reels_video=1,story=1,high_quality=1,allow_extra=1",
            ]
            if cookies:
                base += ["--cookies", cookies]
            cmd_sd = base[:] + ["-f", "best[height<=480]/best", "--merge-output-format", "mp4"]
            return [cmd_sd] + cmds
        if profile == "hd":
            return cmds
        return cmds
    if "tiktok.com" in u or "vm.tiktok.com" in u:
        cmds = _tt_cmds(url, outtmpl, cookies)
        if profile == "sd":
            base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
            if cookies:
                base += ["--cookies", cookies]
            cmd_sd = base[:] + ["-f", "best[height<=480]/best"]
            return [cmd_sd] + cmds
        return cmds
    # youtube / інші
    if profile == "sd":
        base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
        if cookies:
            base += ["--cookies", cookies]
        cmdA = base[:] + ["-f", "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best"]
        cmdB = base[:] + ["-f", "best[height<=480]/best"]
        return [cmdA, cmdB]
    if profile == "hd":
        base = [YTDLP_BIN, "--no-progress", "-o", outtmpl, url, "--merge-output-format", "mp4"] + _base_headers(url)
        if cookies:
            base += ["--cookies", cookies]
        cmdA = base[:] + ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best"]
        cmdB = base[:]
        return [cmdA, cmdB]
    return _yt_cmds(url, outtmpl, cookies)


# ===================== Основний sync-даунлоадер =====================

def _download_sync(url: str, profile: str = "auto") -> Tuple[List[Dict[str, str]], str]:
    """
    Синхронно качає контент і повертає (items, title):
      items: список {"path": str, "type": "photo"|"video"}
      title: str
    Для IG-каруселей / плейлистів може бути кілька файлів.
    """
    _log(f"download START: {url}")

    with tempfile.TemporaryDirectory() as td:
        # IMPORTANT: у шаблоні є %(id)s — ID трека / сторіс / відео
        outtmpl = os.path.join(td, "%(id)s-%(title).80s-%(autonumber)03d.%(ext)s")
        cmds = _build_cmds(url, outtmpl, profile=profile)

        last_err: Optional[Exception] = None

        for i, cmd in enumerate(cmds, 1):
            try:
                _log(f"[try {i}/{len(cmds)}]")
                _run_cmd(cmd)
                last_err = None
                break
            except Exception as e:
                last_err = e
                _log(f"[try {i}] FAIL: {e}")

        if last_err:
            _log(f"ALL FAIL for {url}")
            raise last_err

        # Забираємо ВСІ файли, що викачав yt-dlp
        paths: List[str] = []
        for p in sorted(pathlib.Path(td).glob("*")):
            if p.is_file():
                paths.append(str(p))

        if not paths:
            raise RuntimeError("Файли після завантаження не знайдено")

        # Переносимо у стабільну TMP_DIR
        os.makedirs(TMP_DIR, exist_ok=True)

        items: List[Dict[str, str]] = []
        for p in paths:
            ext = pathlib.Path(p).suffix.lower()
            media_type = "photo" if ext in {".jpg", ".jpeg", ".png", ".webp"} else "video"
            final_path = os.path.join(TMP_DIR, os.path.basename(p))
            try:
                os.replace(p, final_path)
            except Exception:
                import shutil
                shutil.copy2(p, final_path)
            items.append({"path": final_path, "type": media_type})

        # Тайтл — з першого файлу (до суфікса -NNN)
        base_stem = pathlib.Path(paths[0]).stem
        title_raw = base_stem
        for _ in range(2):
            if "-" in title_raw:
                title_raw = title_raw.rsplit("-", 1)[0]
        title = _sanitize_name(title_raw or "file")

        _log(f"SUCCESS: {len(items)} item(s) [{title}]")
        return items, title


# ===================== Публічний API для бота =====================

def is_supported(url: str) -> bool:
    """Чи схожий URL на підтримуваний відео-хост."""
    u = (url or "").lower()
    return any(h in u for h in VIDEO_HOSTS)


def _ytdlp_info_sync(url: str) -> Dict[str, object]:
    cookies = _pick_cookies_for(url)
    cmd = [YTDLP_BIN, "--no-warnings", "--no-playlist", "--dump-json", "--no-download", url] + _base_headers(url)
    if cookies:
        cmd += ["--cookies", cookies]
    _log("INFO RUN: " + " ".join(shlex.quote(x) for x in cmd if x != (cookies or "")))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = (res.stdout or "").strip()
    if res.returncode != 0 or not out:
        raise RuntimeError((res.stderr or out or "yt-dlp info error").strip()[:4000])

    # yt-dlp може вивести кілька JSON рядків; беремо останній
    lines = [ln for ln in out.splitlines() if ln.strip().startswith("{") and ln.strip().endswith("}")]
    raw = lines[-1] if lines else out.splitlines()[-1]
    try:
        return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"yt-dlp json parse error: {e}")


async def get_media_info(url: str) -> Dict[str, object]:
    return await asyncio.to_thread(_ytdlp_info_sync, url)


async def download_url(chat_id: int, url: str, bot, mode: str = "auto") -> None:
    """
    Завантажує контент і ВІДПРАВЛЯЄ В ЧАТ.
    Підтримує:
      - одиночне відео/фото
      - альбом (карусель) до 10 елементів
      - Instagram stories (одна сторі за URL)
    """
    items, title = await asyncio.to_thread(_download_with_fallbacks_sync, url, mode)
    force_document = (mode or "").lower() == "file"

    # Розкладаємо по групах з урахуванням лімітів Telegram
    photos_group: List[str] = []
    videos_group: List[str] = []
    docs: List[str] = []
    audios: List[str] = []

    for it in items:
        p = it["path"]
        t = it["type"]
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0

        if force_document:
            docs.append(p)
            continue

        if t == "audio":
            audios.append(p)
        elif t == "photo":
            # Фото до 10 МБ можемо як photo, але одиночні краще як документ (щоб не кропило)
            if size <= 10 * 1024 * 1024:
                photos_group.append(p)
            else:
                docs.append(p)
        else:
            # Відео до ~50 МБ як video, інакше документ
            if size <= 49 * 1024 * 1024:
                videos_group.append(p)
            else:
                docs.append(p)

    album_paths = photos_group + videos_group

    # Якщо багато елементів — шлемо як альбом (media_group)
    if len(album_paths) > 1:
        media = []
        for idx, p in enumerate(album_paths[:10]):
            inp = FSInputFile(p)
            if p in photos_group:
                media.append(InputMediaPhoto(media=inp, caption=title if idx == 0 else None))
            else:
                media.append(InputMediaVideo(media=inp, caption=title if idx == 0 else None))
        await bot.send_media_group(chat_id, media)

        # Якщо ще залишились (більше 10) — шлемо як документи
        for p in album_paths[10:]:
            await bot.send_document(chat_id, FSInputFile(p), caption=title)

        # Великі файли тільки документами
        for p in docs:
            await bot.send_document(chat_id, FSInputFile(p), caption=title)

    else:
        # Один файл → особливий кейс для фото (щоб не кропило)
        it = items[0]
        p, t = it["path"], it["type"]

        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0

        f = FSInputFile(p)

        if force_document:
            await bot.send_document(chat_id, f, caption=title)
        elif t == "audio":
            # аудіо шлемо нижче окремо (щоб не було дубляжу для multi-file)
            pass
        elif t == "photo":
            # ВАЖЛИВО: одиночне фото шлемо як документ, щоб Telegram не обрізав
            await bot.send_document(chat_id, f, caption=title)
        else:
            if size <= 49 * 1024 * 1024:
                await bot.send_video(chat_id, f, caption=title)
            else:
                await bot.send_document(chat_id, f, caption=title)

    # Аудіо — окремо (не входить у media_group)
    for p in audios:
        try:
            size = os.path.getsize(p)
        except OSError:
            size = 0
        f = FSInputFile(p)
        if size <= 49 * 1024 * 1024 and not force_document:
            await bot.send_audio(chat_id, f, caption=title)
        else:
            await bot.send_document(chat_id, f, caption=title)

    # Прибираємо тимчасові файли
    for it in items:
        try:
            os.remove(it["path"])
        except Exception:
            pass
