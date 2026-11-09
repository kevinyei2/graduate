"""一次上傳 YouTube / Instagram / TikTok 的本機網頁工具。

啟動：python app.py ，然後用瀏覽器打開 http://127.0.0.1:5000
"""
import json
import logging
import os
import secrets
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

import config
import db
from platforms import PlatformError, compose_text, instagram, tiktok, youtube
from scheduler import Scheduler

ALLOWED_EXT = {".mp4", ".mov", ".m4v"}
PLATFORM_NAMES = {"youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok"}
STATUS_NAMES = {"pending": "等待中", "running": "上傳中", "done": "完成",
                "failed": "失敗", "cancelled": "已取消"}


def _secret_key():
    config.ensure_dirs()
    p = config.DATA_DIR / "secret_key"
    if not p.exists():
        p.write_text(secrets.token_hex(32))
    return p.read_text().strip()


app = Flask(__name__)
app.config["SECRET_KEY"] = _secret_key()
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4GB


@app.template_filter("dt")
def fmt_dt(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M") if ts else ""


@app.context_processor
def inject_globals():
    return {"PLATFORM_NAMES": PLATFORM_NAMES, "STATUS_NAMES": STATUS_NAMES}


def _callback_url(name):
    return f"http://{config.HOST}:{config.PORT}{url_for(name)}"


# ---------------------------------------------------------------- 首頁 / 佇列

@app.route("/")
def index():
    posts = db.list_posts()
    has_active = any(t["status"] in ("pending", "running") for p in posts for t in p["targets"])
    return render_template("index.html", posts=posts, has_active=has_active,
                           now=int(time.time()))


@app.post("/target/<int:target_id>/retry")
def retry(target_id):
    db.retry_target(target_id)
    flash("已重新加入佇列。")
    return redirect(url_for("index"))


@app.post("/target/<int:target_id>/cancel")
def cancel(target_id):
    db.cancel_target(target_id)
    flash("已取消。")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- 新增貼文

def _parse_schedule(form, prefix):
    mode = form.get(f"{prefix}_when", "now")
    if mode == "now":
        return int(time.time())
    raw = form.get(f"{prefix}_at", "").strip()
    if not raw:
        raise ValueError("選了排程但沒有填時間。")
    ts = int(datetime.fromisoformat(raw).timestamp())  # 以這台電腦的時區解讀
    if ts < time.time() - 60:
        raise ValueError(f"排程時間 {raw} 已經過去了。")
    return ts


@app.route("/new", methods=["GET", "POST"])
def new_post():
    settings = config.load_settings()
    enabled = {k: v.get("enabled") for k, v in settings["platforms"].items()}

    if request.method == "GET":
        return render_template("new.html", enabled=enabled, form={})

    form = request.form
    f = request.files.get("video")
    errors = []
    if not f or not f.filename:
        errors.append("請選擇影片檔。")
    elif Path(f.filename).suffix.lower() not in ALLOWED_EXT:
        errors.append("只支援 mp4 / mov / m4v。")

    shared_text = form.get("shared_text", "")
    shared_tags = form.get("shared_tags", "")
    targets = []
    try:
        common_ts = _parse_schedule(form, "common")
    except ValueError as e:
        errors.append(str(e))
        common_ts = None

    def when(prefix):
        if form.get(f"{prefix}_custom_time"):
            return _parse_schedule(form, prefix)
        return common_ts

    for p in ("youtube", "instagram", "tiktok"):
        if not form.get(f"{p}_on"):
            continue
        if not enabled.get(p):
            errors.append(f"{PLATFORM_NAMES[p]} 在設定中是停用的。")
            continue
        tags = form.get(f"{p}_tags") or shared_tags
        text = form.get(f"{p}_text") or shared_text
        if p == "youtube":
            opts = {"title": form.get("youtube_title", "").strip(), "description": text,
                    "hashtags": tags, "privacy": form.get("youtube_privacy", "public"),
                    "made_for_kids": bool(form.get("youtube_kids"))}
            if not opts["title"]:
                errors.append("YouTube 需要標題。")
        elif p == "instagram":
            opts = {"caption": text, "hashtags": tags,
                    "share_to_feed": bool(form.get("instagram_feed"))}
            if len(compose_text(text, tags)) > 2200:
                errors.append("Instagram 說明 + hashtag 超過 2200 字元。")
        else:
            opts = {"caption": text, "hashtags": tags,
                    "mode": form.get("tiktok_mode", "inbox"),
                    "privacy": form.get("tiktok_privacy", "SELF_ONLY")}
        try:
            ts = when(p)
        except ValueError as e:
            errors.append(f"{PLATFORM_NAMES[p]}：{e}")
            continue
        if ts is not None:
            targets.append({"platform": p, "options": opts, "scheduled_at": ts})

    if not targets and not errors:
        errors.append("請至少勾選一個平台。")
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("new.html", enabled=enabled, form=form), 400

    ext = Path(f.filename).suffix.lower()
    stored = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    f.save(stored)
    db.create_post(str(stored), secure_filename(f.filename) or f.filename, targets)
    flash("已加入佇列！" + ("" if all(t["scheduled_at"] <= time.time() + 5 for t in targets)
                       else "排程時間到時會自動上傳（請保持本程式開著）。"))
    return redirect(url_for("index"))


# ---------------------------------------------------------------- 設定

@app.route("/settings")
def settings_page():
    s = config.load_settings()
    yt = {"has_secret": youtube.has_client_secret(), "channel": None, "error": None}
    if yt["has_secret"]:
        try:
            if youtube.load_credentials():
                yt["channel"] = youtube.channel_info()
        except Exception as e:  # noqa: BLE001
            yt["error"] = str(e)
    return render_template("settings.html", s=s, yt=yt,
                           yt_redirect=_callback_url("youtube_callback"),
                           tt_redirect=_callback_url("tiktok_callback"),
                           now=int(time.time()))


@app.post("/settings/platforms")
def save_platforms():
    s = config.load_settings()
    for p in ("youtube", "instagram", "tiktok"):
        s["platforms"][p]["enabled"] = bool(request.form.get(f"{p}_enabled"))
    config.save_settings(s)
    flash("已儲存平台開關。")
    return redirect(url_for("settings_page"))


# --- YouTube

@app.post("/settings/youtube/secret")
def youtube_secret():
    f = request.files.get("client_secret")
    if not f or not f.filename:
        flash("請選擇 JSON 檔。", "error")
        return redirect(url_for("settings_page"))
    try:
        data = json.loads(f.read().decode("utf-8"))
    except ValueError:
        flash("這不是有效的 JSON 檔。", "error")
        return redirect(url_for("settings_page"))
    if "installed" not in data:
        flash("OAuth 用戶端類型需要是「電腦版應用程式 (Desktop app)」。", "error")
        return redirect(url_for("settings_page"))
    config.YOUTUBE_CLIENT_SECRET.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(config.YOUTUBE_CLIENT_SECRET, 0o600)
    flash("已儲存 Google OAuth 用戶端，接著按「連結 YouTube 帳號」。")
    return redirect(url_for("settings_page"))


@app.route("/auth/youtube/start")
def youtube_start():
    try:
        flow = youtube.make_flow(_callback_url("youtube_callback"))
    except PlatformError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_page"))
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent",
                                             include_granted_scopes="true")
    session["yt_state"] = state
    session["yt_verifier"] = flow.code_verifier
    return redirect(auth_url)


@app.route("/auth/youtube/callback")
def youtube_callback():
    if request.args.get("error"):
        flash(f"YouTube 授權被拒絕：{request.args['error']}", "error")
        return redirect(url_for("settings_page"))
    if request.args.get("state") != session.get("yt_state"):
        flash("授權狀態不符，請重試。", "error")
        return redirect(url_for("settings_page"))
    try:
        flow = youtube.make_flow(_callback_url("youtube_callback"),
                                 code_verifier=session.get("yt_verifier"))
        flow.fetch_token(authorization_response=request.url)
        youtube.save_credentials(flow.credentials)
        flash("YouTube 連結成功！")
    except Exception as e:  # noqa: BLE001
        flash(f"YouTube 連結失敗：{e}", "error")
    return redirect(url_for("settings_page"))


@app.post("/settings/youtube/disconnect")
def youtube_disconnect():
    youtube.disconnect()
    flash("已中斷 YouTube 連結。")
    return redirect(url_for("settings_page"))


# --- Instagram

@app.post("/settings/instagram")
def instagram_save():
    token = request.form.get("access_token", "").strip()
    if not token:
        flash("請貼上 Instagram 存取權杖。", "error")
        return redirect(url_for("settings_page"))
    try:
        username, user_id = instagram.verify_token(token)
    except PlatformError as e:
        flash(f"權杖驗證失敗：{e}", "error")
        return redirect(url_for("settings_page"))
    s = config.load_settings()
    s["instagram"].update({"access_token": token, "user_id": user_id, "username": username,
                           "token_expires_at": int(time.time()) + 60 * 86400})
    config.save_settings(s)
    flash(f"Instagram 已連結：@{username}")
    return redirect(url_for("settings_page"))


@app.post("/settings/instagram/disconnect")
def instagram_disconnect():
    s = config.load_settings()
    s["instagram"].update({"access_token": "", "user_id": "", "username": "",
                           "token_expires_at": 0})
    config.save_settings(s)
    flash("已中斷 Instagram 連結。")
    return redirect(url_for("settings_page"))


# --- TikTok

@app.post("/settings/tiktok")
def tiktok_save():
    s = config.load_settings()
    s["tiktok"]["client_key"] = request.form.get("client_key", "").strip()
    secret = request.form.get("client_secret", "").strip()
    if secret:
        s["tiktok"]["client_secret"] = secret
    s["tiktok"]["mode"] = request.form.get("mode", "inbox")
    config.save_settings(s)
    flash("已儲存 TikTok 設定。")
    return redirect(url_for("settings_page"))


@app.route("/auth/tiktok/start")
def tiktok_start():
    s = config.load_settings()
    if not s["tiktok"].get("client_key"):
        flash("請先填 TikTok Client Key。", "error")
        return redirect(url_for("settings_page"))
    url, state = tiktok.authorize_url(s["tiktok"]["client_key"], _callback_url("tiktok_callback"))
    session["tt_state"] = state
    return redirect(url)


@app.route("/auth/tiktok/callback")
def tiktok_callback():
    if request.args.get("state") != session.get("tt_state") or not request.args.get("code"):
        flash(f"TikTok 授權失敗：{request.args.get('error_description') or '狀態不符'}", "error")
        return redirect(url_for("settings_page"))
    s = config.load_settings()
    try:
        tokens = tiktok.exchange_code(s["tiktok"]["client_key"], s["tiktok"]["client_secret"],
                                      request.args["code"], _callback_url("tiktok_callback"))
    except PlatformError as e:
        flash(str(e), "error")
        return redirect(url_for("settings_page"))
    s["tiktok"].update(tokens)
    config.save_settings(s)
    flash("TikTok 連結成功！")
    return redirect(url_for("settings_page"))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    db.init_db()
    Scheduler().start()
    url = f"http://{config.HOST}:{config.PORT}"
    print(f"\n  開啟瀏覽器前往 {url}\n  （關掉這個視窗 = 停止排程）\n")
    if not os.environ.get("SOCIAL_UPLOADER_NO_BROWSER"):
        webbrowser.open(url)
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
