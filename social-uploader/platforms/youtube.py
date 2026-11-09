"""YouTube Data API v3 上傳。

授權方式：Google Cloud 建立「電腦版應用程式 (Desktop app)」類型的 OAuth 用戶端，
下載 JSON 後在本工具「設定」頁上傳，再按「連結 YouTube」登入。
直式且 3 分鐘以內的影片，YouTube 會自動歸類為 Shorts。
"""
import json
import os

from config import YOUTUBE_CLIENT_SECRET, YOUTUBE_TOKEN
from platforms import PlatformError, compose_text, normalize_hashtags

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

# 本機 http 回呼需要這個旗標（只在 127.0.0.1 上使用）
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
# Google 有時回傳的 scope 順序或內容稍有不同，不要因此報錯
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


def has_client_secret():
    return YOUTUBE_CLIENT_SECRET.exists()


def make_flow(redirect_uri, code_verifier=None):
    from google_auth_oauthlib.flow import Flow

    if not has_client_secret():
        raise PlatformError("尚未上傳 Google OAuth 用戶端 JSON（設定頁 → YouTube）。")
    flow = Flow.from_client_secrets_file(
        str(YOUTUBE_CLIENT_SECRET), scopes=SCOPES, redirect_uri=redirect_uri,
        autogenerate_code_verifier=code_verifier is None,
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    return flow


def save_credentials(creds):
    YOUTUBE_TOKEN.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(YOUTUBE_TOKEN, 0o600)
    except OSError:
        pass


def load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not YOUTUBE_TOKEN.exists():
        return None
    creds = Credentials.from_authorized_user_info(
        json.loads(YOUTUBE_TOKEN.read_text(encoding="utf-8")), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds


def disconnect():
    if YOUTUBE_TOKEN.exists():
        YOUTUBE_TOKEN.unlink()


def _service():
    from googleapiclient.discovery import build

    creds = load_credentials()
    if not creds or not creds.valid:
        raise PlatformError("YouTube 尚未連結或授權已失效，請到設定頁重新連結。")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_info():
    """回傳 (頻道名稱, 頻道 ID)，用來在設定頁確認連到哪個頻道。"""
    resp = _service().channels().list(part="snippet", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        return None
    return items[0]["snippet"]["title"], items[0]["id"]


def publish(video_path, options, settings):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    title = (options.get("title") or "").strip()
    if not title:
        raise PlatformError("YouTube 標題不可空白。")
    if len(title) > 100:
        raise PlatformError("YouTube 標題最多 100 個字元。")

    tags = [t.lstrip("#") for t in normalize_hashtags(options.get("hashtags"))]
    body = {
        "snippet": {
            "title": title,
            "description": compose_text(options.get("description"), options.get("hashtags"))[:5000],
            "tags": tags[:30],
            "categoryId": options.get("category_id") or "22",
        },
        "status": {
            "privacyStatus": options.get("privacy") or "public",
            "selfDeclaredMadeForKids": bool(options.get("made_for_kids")),
        },
    }

    try:
        media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
        request = _service().videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _status, response = request.next_chunk()
    except HttpError as e:
        raise PlatformError(f"YouTube API 錯誤：{e}") from e

    video_id = response["id"]
    return f"https://youtu.be/{video_id}"
