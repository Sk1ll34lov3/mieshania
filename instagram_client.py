# /var/opt/mieshania/instagram_client.py
# -*- coding: utf-8 -*-
"""
Singleton-клієнт instagrapi для Instagram Stories.

Сесія зберігається в SESSION_FILE і автоматично відновлюється при протуханні.
Credentials — з .env: IG_USERNAME, IG_PASSWORD.
"""

import os
import json
import pathlib
import datetime
import tempfile
from typing import Optional, List, Dict

try:
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, ClientError, ClientLoginRequired
    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
SESSION_FILE = os.getenv("IG_SESSION_FILE", "/var/opt/mieshania/ig_session.json")
LOG_FILE = "/var/log/mieshania.downloader.log"


def _log(msg: str) -> None:
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} [IG] {msg}\n")
    except Exception:
        pass


_client: Optional["Client"] = None


def _make_client() -> "Client":
    cl = Client()
    cl.delay_range = [1, 3]
    return cl


def _login_fresh(cl: "Client") -> None:
    """Логін з username/password і збереження сесії."""
    if not IG_USERNAME or not IG_PASSWORD:
        raise RuntimeError("IG_USERNAME або IG_PASSWORD не задані в .env")
    _log(f"LOGIN: logging in as {IG_USERNAME}")
    cl.login(IG_USERNAME, IG_PASSWORD)
    _save_session(cl)
    _log("LOGIN: success, session saved")


def _save_session(cl: "Client") -> None:
    try:
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(cl.get_settings(), f)
    except Exception as e:
        _log(f"SESSION SAVE FAIL: {e}")


def _load_session(cl: "Client") -> bool:
    if not pathlib.Path(SESSION_FILE).exists():
        return False
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        cl.set_settings(settings)
        # Перевіряємо сесію без повторного логіну
        cl.get_timeline_feed()
        _log("SESSION: loaded from file OK")
        return True
    except Exception as e:
        _log(f"SESSION LOAD FAIL: {e}")
        return False


def get_client() -> "Client":
    """Повертає готовий (залогінений) клієнт. Thread-unsafe але для asyncio.to_thread ок."""
    global _client
    if not INSTAGRAPI_AVAILABLE:
        raise RuntimeError("instagrapi не встановлений")
    if not IG_USERNAME or not IG_PASSWORD:
        raise RuntimeError("IG_USERNAME або IG_PASSWORD не задані в .env")

    if _client is None:
        cl = _make_client()
        if not _load_session(cl):
            _login_fresh(cl)
        _client = cl

    return _client


def _with_relogin(fn):
    """Виконує fn(client), при LoginRequired — ре-логін і повтор."""
    global _client
    cl = get_client()
    try:
        return fn(cl)
    except (LoginRequired, ClientLoginRequired):
        _log("SESSION EXPIRED: re-logging in")
        _client = None
        cl = get_client()
        _login_fresh(cl)
        return fn(cl)


# =================== Публічний API ===================

def download_story_by_url(story_url: str, dest_dir: str) -> List[Dict[str, str]]:
    """
    Качає одну сторіс за URL вигляду:
      https://www.instagram.com/stories/<username>/<story_id>/

    Повертає список {"path": str, "type": "video"|"photo"}.
    """
    import re
    m = re.search(
        r"instagram\.com/stories/([^/?#]+)/(\d+)",
        story_url, re.I
    )
    if not m:
        raise ValueError(f"Не вдалось розпарсити URL сторіс: {story_url}")

    username, story_id = m.group(1), int(m.group(2))
    _log(f"STORY: {username}/{story_id}")

    os.makedirs(dest_dir, exist_ok=True)

    def _do(cl: "Client") -> List[Dict[str, str]]:
        # Отримуємо сторіс по story_id напряму
        story = cl.story_info(story_id)
        items = []

        if story.video_url:
            path = cl.video_download_by_url(str(story.video_url), dest_dir)
            items.append({"path": str(path), "type": "video"})
        elif story.thumbnail_url:
            path = cl.photo_download_by_url(str(story.thumbnail_url), dest_dir)
            items.append({"path": str(path), "type": "photo"})

        return items

    return _with_relogin(_do)


def download_media_by_url(url: str, dest_dir: str) -> List[Dict[str, str]]:
    """
    Качає пост / reel / carousel за Instagram URL.

    media_type: 1=photo, 2=video/reel, 8=album/carousel
    Повертає список {"path": str, "type": "video"|"photo"}.
    """
    _log(f"POST: {url}")
    os.makedirs(dest_dir, exist_ok=True)

    def _do(cl: "Client") -> List[Dict[str, str]]:
        pk = cl.media_pk_from_url(url)
        info = cl.media_info(pk)
        items: List[Dict[str, str]] = []

        if info.media_type == 8:  # carousel/album
            paths = cl.album_download(pk, dest_dir)
            for path in paths:
                ext = str(path).rsplit(".", 1)[-1].lower()
                t = "video" if ext in ("mp4", "mov", "avi") else "photo"
                items.append({"path": str(path), "type": t})
        elif info.media_type == 2:  # відео / reel
            path = cl.video_download(pk, dest_dir)
            items.append({"path": str(path), "type": "video"})
        else:  # photo (type 1)
            path = cl.photo_download(pk, dest_dir)
            items.append({"path": str(path), "type": "photo"})

        return items

    return _with_relogin(_do)


if __name__ == "__main__":
    print("Testing instagrapi login...")
    try:
        cl = get_client()
        print(f"OK! Logged in as: {cl.username}, user_id: {cl.user_id}")
    except Exception as e:
        print(f"FAIL: {e}")
