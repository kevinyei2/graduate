"""各平台上傳模組。每個模組都提供 publish(video_path, options, settings) -> str。"""


class PlatformError(Exception):
    """平台回傳錯誤或設定不完整時拋出，訊息會顯示在介面上。"""


def normalize_hashtags(text):
    """把 "旅行, #美食  vlog" 轉成 ["#旅行", "#美食", "#vlog"]。"""
    if not text:
        return []
    parts = text.replace("，", " ").replace(",", " ").replace("、", " ").split()
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        tag = p if p.startswith("#") else f"#{p}"
        if tag != "#" and tag not in out:
            out.append(tag)
    return out


def compose_text(body, hashtags):
    tags = " ".join(normalize_hashtags(hashtags))
    body = (body or "").strip()
    if body and tags:
        return f"{body}\n\n{tags}"
    return body or tags
