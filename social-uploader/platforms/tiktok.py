"""TikTok Content Posting API。

目前預設關閉。注意：
- 開發者 App 未通過 TikTok 審核前，「直接發佈」只能設為「僅自己可見 (SELF_ONLY)」。
- 「草稿匣模式 (inbox)」會把影片送到你 TikTok App 的收件匣，由你在手機上編輯後發佈，
  未審核的 App 也可以使用。
"""
import math
import os
import secrets
import time
from urllib.parse import urlencode

import requests

from platforms import PlatformError, compose_text

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.publish,video.upload"

CHUNK = 10 * 1024 * 1024        # TikTok 規定每塊 5MB～64MB
SINGLE_LIMIT = 64 * 1024 * 1024  # 小於這個大小就一次傳完


def _check(resp):
    try:
        data = resp.json()
    except ValueError:
        raise PlatformError(f"TikTok 回傳非 JSON（HTTP {resp.status_code}）：{resp.text[:300]}")
    err = data.get("error") or {}
    if resp.status_code >= 400 or (err.get("code") not in (None, "ok")):
        raise PlatformError(f"TikTok API 錯誤：{err.get('code')} {err.get('message') or data}")
    return data


def authorize_url(client_key, redirect_uri):
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urlencode({
        "client_key": client_key, "scope": SCOPES, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
    })
    return url, state


def _token_request(form):
    resp = requests.post(f"{API}/oauth/token/", data=form, headers={
        "Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    data = resp.json()
    if "access_token" not in data:
        raise PlatformError(f"TikTok 授權失敗：{data.get('error_description') or data}")
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_expires_at": int(time.time()) + int(data.get("expires_in", 86400)),
        "open_id": data.get("open_id", ""),
    }


def exchange_code(client_key, client_secret, code, redirect_uri):
    return _token_request({
        "client_key": client_key, "client_secret": client_secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    })


def ensure_fresh_token(tk):
    """存取權杖 24 小時到期；快到期就用 refresh_token 換新。回傳要更新的欄位或 None。"""
    if not tk.get("refresh_token"):
        return None
    if tk.get("token_expires_at", 0) - time.time() > 600:
        return None
    return _token_request({
        "client_key": tk["client_key"], "client_secret": tk["client_secret"],
        "grant_type": "refresh_token", "refresh_token": tk["refresh_token"],
    })


def creator_info(access_token):
    return _check(requests.post(f"{API}/post/publish/creator_info/query/", headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"}, timeout=30))["data"]


def _upload_file(upload_url, video_path, size, chunk_size, total_chunks):
    with open(video_path, "rb") as f:
        for i in range(total_chunks):
            start = i * chunk_size
            end = size - 1 if i == total_chunks - 1 else start + chunk_size - 1
            f.seek(start)
            chunk = f.read(end - start + 1)
            resp = requests.put(upload_url, data=chunk, headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }, timeout=60 * 10)
            if resp.status_code not in (200, 201, 206):
                raise PlatformError(f"TikTok 影片上傳失敗（第 {i + 1} 塊，HTTP {resp.status_code}）")


def publish(video_path, options, settings):
    tk = settings["tiktok"]
    token = tk.get("access_token")
    if not token:
        raise PlatformError("TikTok 尚未連結，請到設定頁連結帳號。")

    size = os.path.getsize(video_path)
    if size <= SINGLE_LIMIT:
        chunk_size, total = size, 1
    else:
        chunk_size = CHUNK
        total = max(1, math.floor(size / chunk_size))  # 最後一塊吸收餘數
    source = {"source": "FILE_UPLOAD", "video_size": size,
              "chunk_size": chunk_size, "total_chunk_count": total}
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json; charset=UTF-8"}

    mode = options.get("mode") or tk.get("mode") or "inbox"
    if mode == "direct":
        info = creator_info(token)
        privacy = options.get("privacy") or "SELF_ONLY"
        allowed = info.get("privacy_level_options") or []
        if allowed and privacy not in allowed:
            raise PlatformError(f"這個帳號目前不允許隱私設定 {privacy}，可用：{', '.join(allowed)}")
        body = {
            "post_info": {
                "title": compose_text(options.get("caption"), options.get("hashtags"))[:2200],
                "privacy_level": privacy,
                "disable_comment": bool(options.get("disable_comment")),
                "disable_duet": bool(options.get("disable_duet")),
                "disable_stitch": bool(options.get("disable_stitch")),
            },
            "source_info": source,
        }
        url = f"{API}/post/publish/video/init/"
    else:
        body = {"source_info": source}
        url = f"{API}/post/publish/inbox/video/init/"

    data = _check(requests.post(url, json=body, headers=headers, timeout=60))["data"]
    publish_id, upload_url = data["publish_id"], data["upload_url"]
    _upload_file(upload_url, video_path, size, chunk_size, total)

    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        st = _check(requests.post(f"{API}/post/publish/status/fetch/", json={
            "publish_id": publish_id}, headers=headers, timeout=30))["data"]
        status = st.get("status")
        if status == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
            return f"已發佈 post_id={ids[0]}" if ids else f"已發佈 publish_id={publish_id}"
        if status == "SEND_TO_USER_INBOX":
            return "已送到 TikTok 草稿匣，請到手機 TikTok 通知中完成發佈"
        if status == "FAILED":
            raise PlatformError(f"TikTok 處理失敗：{st.get('fail_reason')}")
        time.sleep(10)
    raise PlatformError("TikTok 處理逾時。")
