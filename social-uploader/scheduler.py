"""背景排程器：每 20 秒檢查到期任務並上傳；每天檢查一次權杖續期。

注意：排程只在本程式執行中才會觸發。電腦關機或程式關閉時，
到期的任務會在下次開啟時自動補發。
"""
import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import config
import db
from platforms import PlatformError, instagram, tiktok, youtube

log = logging.getLogger("scheduler")

PUBLISHERS = {
    "youtube": youtube.publish,
    "instagram": instagram.publish,
    "tiktok": tiktok.publish,
}

CHECK_INTERVAL = 20
TOKEN_CHECK_INTERVAL = 6 * 3600

_settings_lock = threading.Lock()


def run_target(target):
    platform = target["platform"]
    import json
    options = json.loads(target["options"])
    try:
        with _settings_lock:
            settings = config.load_settings()
        if not settings["platforms"].get(platform, {}).get("enabled"):
            raise PlatformError(f"{platform} 目前在設定中被停用。")
        if platform == "tiktok":
            refresh_tiktok_token(settings)
            settings = config.load_settings()
        result = PUBLISHERS[platform](target["video_path"], options, settings)
        db.finish_target(target["id"], True, result=result)
        log.info("target %s (%s) done: %s", target["id"], platform, result)
    except PlatformError as e:
        db.finish_target(target["id"], False, error=str(e))
        log.warning("target %s (%s) failed: %s", target["id"], platform, e)
    except Exception as e:  # noqa: BLE001 — 任何錯誤都要記錄到介面上
        db.finish_target(target["id"], False, error=f"{type(e).__name__}: {e}")
        log.error("target %s crashed:\n%s", target["id"], traceback.format_exc())


def refresh_tiktok_token(settings):
    tk = settings["tiktok"]
    updated = tiktok.ensure_fresh_token(tk)
    if updated:
        with _settings_lock:
            s = config.load_settings()
            s["tiktok"].update(updated)
            config.save_settings(s)


def refresh_instagram_token():
    with _settings_lock:
        s = config.load_settings()
    ig = s["instagram"]
    if not ig.get("access_token"):
        return
    # 剩不到 10 天就續期
    if ig.get("token_expires_at", 0) - time.time() > 10 * 86400:
        return
    try:
        token, expires = instagram.refresh_token(ig["access_token"])
    except PlatformError as e:
        log.warning("Instagram token refresh failed: %s", e)
        return
    with _settings_lock:
        s = config.load_settings()
        s["instagram"]["access_token"] = token
        s["instagram"]["token_expires_at"] = expires
        config.save_settings(s)
    log.info("Instagram token refreshed")


class Scheduler:
    def __init__(self, workers=3):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="upload")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)
        self._last_token_check = 0

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def tick(self):
        for target in db.claim_due_targets():
            self.pool.submit(run_target, target)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.tick()
                if time.time() - self._last_token_check > TOKEN_CHECK_INTERVAL:
                    self._last_token_check = time.time()
                    refresh_instagram_token()
            except Exception:  # noqa: BLE001
                log.error("scheduler loop error:\n%s", traceback.format_exc())
            self._stop.wait(CHECK_INTERVAL)
