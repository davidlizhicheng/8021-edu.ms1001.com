from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Iterator

BASE_URL = "https://metaso.cn/api/v1"

def is_configured() -> bool:
    return bool(os.environ.get("METASO_API_KEY", "").strip())

def _request(path: str, payload: dict, accept: str = "application/json", timeout: int = 60, api_key: str | None = None) -> str:
    api_key = (api_key or os.environ.get("METASO_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("METASO_API_KEY is not configured")
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(
            f"{BASE_URL}{path}", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Accept": accept, "Content-Type": "application/json; charset=utf-8", "Connection": "close"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Metaso {path} HTTP {exc.code}: {detail[:300]}")
            if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise last_error from exc
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise RuntimeError(f"Metaso {path} 网络错误：{exc}") from exc
        time.sleep(1.0 * (attempt + 1) ** 2)
    raise RuntimeError(f"Metaso {path} 请求失败：{last_error}")

def search(query: str, size: int = 10, page: int = 1) -> list[dict]:
    data = json.loads(_request("/search", {
        "q": query.strip(), "scope": "webpage", "size": str(max(1, min(50, int(size)))),
        "includeSummary": True,
        "includeRawContent": False, "conciseSnippet": False,
    }))
    if data.get("errCode") or data.get("code"):
        raise RuntimeError(data.get("errMsg") or data.get("message") or "Metaso search failed")
    return data.get("webpages") or []

def read_page(url: str) -> str:
    return _request("/reader", {"url": url}, accept="text/plain", timeout=60).strip()

def answer(question: str, model: str | None = None, api_key: str | None = None) -> dict:
    data = json.loads(_request("/chat/completions", {
        "q": question.strip(), "scope": "webpage", "model": model or os.environ.get("METASO_CHAT_MODEL", "fast"),
        "format": "chat_completions", "stream": False, "conciseSnippet": True,
    }, timeout=90, api_key=api_key))
    if data.get("errCode") or data.get("code"):
        raise RuntimeError(data.get("errMsg") or data.get("message") or "Metaso answer failed")
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    return {"content": (message.get("content") or "").strip(), "citations": message.get("citations") or []}

def stream_answer(question: str, model: str | None = None) -> Iterator[str]:
    api_key = os.environ.get("METASO_API_KEY", "").strip()
    if not api_key:
        return
    payload = {"q": question.strip(), "scope": "webpage", "model": model or os.environ.get("METASO_CHAT_MODEL", "fast"), "format": "chat_completions", "stream": True, "conciseSnippet": True}
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Accept": "text/event-stream", "Content-Type": "application/json; charset=utf-8"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data_text = line[5:].strip()
            if not data_text or data_text == "[DONE]":
                continue
            try:
                chunk = json.loads(data_text)
                delta = (((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
                if delta:
                    yield delta
            except json.JSONDecodeError:
                continue

def build_answer_context(question: str) -> str:
    disabled = os.environ.get("METASO_QA_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}
    if not is_configured() or disabled:
        return ""
    result = answer(question)
    content = (result.get("content") or "")[:5000]
    citations = []
    for index, item in enumerate(result.get("citations") or [], start=1):
        title = str(item.get("title") or "来源")[:160]
        link = str(item.get("link") or "")[:500]
        summary = str(item.get("summary") or item.get("snippet") or "")[:400]
        citations.append(f"[{index}] {title}\n{link}\n{summary}".strip())
    if not content:
        return ""
    return "秘塔实时问答（仅作外部补充证据，必须与题干和本地RAG交叉校验）：\n" + content + ("\n\n来源：\n" + "\n\n".join(citations) if citations else "")
