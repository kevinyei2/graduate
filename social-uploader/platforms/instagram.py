"""Instagram API（使用 Instagram 登入）發佈 Reels。

適用：Instagram 創作者或商業帳號，不需要連結 Facebook 粉絲專頁。
權杖：在 Meta 開發者後台「API setup with Instagram login」產生長效權杖，貼到設定頁。
長效權杖 60 天到期，本工具會在到期前自動續期。

上傳流程（直接從電腦上傳，不需要把影片放到公開網址）：
  1. 建立 REELS 容器 (upload_type=resumable)
  2. 把影片檔傳到 rupload.facebook.com
  3. 輪詢容器狀態直到 FINISHED
  4. media_publish 正式發佈
"""
import os
import time

import requests

from platforms import PlatformError, compose_text

API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
GRAPH = f"https://graph.instagram.com/{API_VERSION}"
RUPLOAD = f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}"

POLL_INTERVAL = 10
POLL_TIMEOUT = 30 * 60


def _check(resp):
    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise PlatformError(f"Instagram 回傳非 JSON：{resp.text[:300]}")
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", data)
        msg = err.get("error_user_msg") or err.get("message") if isinstance(err, dict) else err
        raise PlatformError(f"Instagram API 錯誤：{msg}")
    return data


def verify_token(access_token):
    """回傳 (使用者名稱, IG 專業帳號 ID)。"""
    resp = requests.get(f"{GRAPH}/me", params={
        "fields": "user_id,username,account_type", "access_token": access_token}, timeout=30)
    data = _check(resp)
    return data.get("username"), str(data.get("user_id") or data.get("id"))


def refresh_token(access_token):
    """長效權杖續期（權杖需已發出超過 24 小時）。回傳 (新權杖, 到期 Unix 秒)。"""
    resp = requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": access_token}, timeout=30)
    data = _check(resp)
    return data["access_token"], int(time.time()) + int(data.get("expires_in", 60 * 86400))


def publish(video_path, options, settings):
    ig = settings["instagram"]
    token, user_id = ig.get("access_token"), ig.get("user_id")
    if not token or not user_id:
        raise PlatformError("Instagram 尚未設定權杖，請到設定頁貼上並驗證。")

    caption = compose_text(options.get("caption"), options.get("hashtags"))
    if len(caption) > 2200:
        raise PlatformError("Instagram 說明文字最多 2200 字元。")
    if len([w for w in caption.split() if w.startswith("#")]) > 30:
        raise PlatformError("Instagram 每則貼文最多 30 個 hashtag。")

    # 1. 建立容器
    data = _check(requests.post(f"{GRAPH}/{user_id}/media", data={
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true" if options.get("share_to_feed", True) else "false",
        "access_token": token,
    }, timeout=60))
    container_id = data["id"]

    # 2. 上傳影片檔
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        resp = requests.post(f"{RUPLOAD}/{container_id}", headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(size),
        }, data=f, timeout=60 * 60)
    up = _check(resp)
    if up.get("success") is False:
        raise PlatformError(f"Instagram 影片上傳失敗：{up}")

    # 3. 等待 IG 轉檔完成
    deadline = time.time() + POLL_TIMEOUT
    while True:
        st = _check(requests.get(f"{GRAPH}/{container_id}", params={
            "fields": "status_code,status", "access_token": token}, timeout=30))
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PlatformError(f"Instagram 轉檔失敗：{st.get('status') or code}"
                                "（常見原因：格式不支援、長度不符 3 秒～15 分鐘）")
        if time.time() > deadline:
            raise PlatformError("Instagram 轉檔逾時（超過 30 分鐘）。")
        time.sleep(POLL_INTERVAL)

    # 4. 發佈
    pub = _check(requests.post(f"{GRAPH}/{user_id}/media_publish", data={
        "creation_id": container_id, "access_token": token}, timeout=60))
    media_id = pub["id"]

    try:
        info = _check(requests.get(f"{GRAPH}/{media_id}", params={
            "fields": "permalink", "access_token": token}, timeout=30))
        return info.get("permalink") or f"media_id={media_id}"
    except PlatformError:
        return f"media_id={media_id}"
