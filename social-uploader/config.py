"""集中管理路徑與設定檔讀寫。

所有憑證、token、上傳的影片都放在 data/ 底下，這個資料夾已被 .gitignore 排除，
絕對不會被推到 GitHub。
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SOCIAL_UPLOADER_DATA", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "uploader.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

# YouTube：從 Google Cloud 下載的 OAuth 用戶端 JSON 放這裡
YOUTUBE_CLIENT_SECRET = DATA_DIR / "youtube_client_secret.json"
YOUTUBE_TOKEN = DATA_DIR / "youtube_token.json"

HOST = "127.0.0.1"
PORT = int(os.environ.get("SOCIAL_UPLOADER_PORT", "5000"))

DEFAULT_SETTINGS = {
    "platforms": {
        "youtube": {"enabled": True},
        "instagram": {"enabled": True},
        # TikTok 先做好但預設關閉，等開發者 App 審核通過再打開
        "tiktok": {"enabled": False},
    },
    "instagram": {
        "access_token": "",
        "user_id": "",
        "token_expires_at": 0,
        "app_secret": "",
    },
    "tiktok": {
        "client_key": "",
        "client_secret": "",
        "access_token": "",
        "refresh_token": "",
        "token_expires_at": 0,
        "open_id": "",
        # inbox = 傳到 TikTok 草稿匣，由你在手機上按發佈（未審核 App 也能用）
        # direct = 直接發佈（需通過審核才能公開）
        "mode": "inbox",
    },
}


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _merge(default, current):
    out = dict(default)
    for k, v in current.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings():
    ensure_dirs()
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return _merge(DEFAULT_SETTINGS, json.load(f))
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(settings):
    ensure_dirs()
    tmp = SETTINGS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS_PATH)
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass
