"""AiPPT 开放平台鉴权 — 服务端签名并换取 iframe code。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


AIPPT_API_KEY = os.environ.get("AIPPT_API_KEY", "").strip()
AIPPT_SECRET_KEY = os.environ.get("AIPPT_SECRET_KEY", "").strip()
AIPPT_BASE_URL = os.environ.get("AIPPT_BASE_URL", "https://co.aippt.cn").rstrip("/")
AIPPT_CHANNEL = os.environ.get("AIPPT_CHANNEL", "edu.ms1001.com").strip()
AIPPT_UID_PREFIX = os.environ.get("AIPPT_UID_PREFIX", "edu-ms1001")


def configured() -> bool:
    return bool(AIPPT_API_KEY and AIPPT_SECRET_KEY)


def build_signature(timestamp: int, api_path: str = "/api/grant/code") -> str:
    payload = f"GET@{api_path}/@{timestamp}"
    digest = hmac.new(AIPPT_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def fetch_grant_code(uid: str | None = None, grant_type: int = 1) -> dict:
    if not configured():
        return {"ok": False, "error": "未配置 AIPPT_API_KEY / AIPPT_SECRET_KEY，请在 .env 中填写开放平台密钥。"}
    user_id = (uid or f"{AIPPT_UID_PREFIX}-{int(time.time())}").strip()
    timestamp = int(time.time())
    signature = build_signature(timestamp, "/api/grant/code")
    query = urllib.parse.urlencode(
        {"uid": user_id, "channel": AIPPT_CHANNEL, "type": str(grant_type)},
        safe="",
    )
    url = f"{AIPPT_BASE_URL}/api/grant/code?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "x-api-key": AIPPT_API_KEY,
            "x-timestamp": str(timestamp),
            "x-signature": signature,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"AiPPT 鉴权失败 ({exc.code}): {detail[:240]}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": f"AiPPT 鉴权请求异常: {exc}"}

    code = payload.get("code")
    data = payload.get("data")
    if not code and isinstance(data, dict):
        code = data.get("code")
    if not code and isinstance(data, str):
        code = data
    if not code:
        return {"ok": False, "error": "AiPPT 未返回 code", "raw": payload}
    return {
        "ok": True,
        "appkey": AIPPT_API_KEY,
        "code": code,
        "channel": AIPPT_CHANNEL,
        "uid": user_id,
        "expires_hint": "code 有效期约 24 小时",
    }
