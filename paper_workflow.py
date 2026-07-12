"""Domain rules for full-paper extraction and fixed eight-step analysis."""

from __future__ import annotations

import re


ANSWER_STATES = {"correct", "wrong", "partial", "blank", "review_required"}
EIGHT_STEP_KEYS = (
    "understand", "conditions", "knowledge", "diagnose",
    "model", "solve", "verify", "transfer",
)
EIGHT_STEP_LABELS = (
    "读懂题意", "提取条件", "定位知识点", "诊断错因",
    "选择模型", "分步求解", "验算校核", "迁移巩固",
)


def normalize_answer_state(value: str | None, score: float | None = None, max_score: float | None = None) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "对": "correct", "正确": "correct", "错": "wrong", "错误": "wrong",
        "部分正确": "partial", "半对": "partial", "空白": "blank", "未作答": "blank",
        "需复核": "review_required", "不确定": "review_required",
    }
    state = aliases.get(raw, raw)
    if state in ANSWER_STATES:
        return state
    if score is not None and max_score:
        ratio = float(score) / float(max_score)
        if ratio >= 0.999:
            return "correct"
        if ratio <= 0:
            return "blank" if not raw else "wrong"
        return "partial"
    return "review_required"


def split_numbered_questions(text: str) -> list[dict]:
    """Fallback segmentation for text PDFs; vision OCR remains authoritative."""
    source = (text or "").replace("\r\n", "\n").strip()
    if not source:
        return []
    pattern = re.compile(r"(?m)^\s*(?:第\s*)?(\d{1,3})\s*(?:题|[\.、．)])\s*")
    matches = list(pattern.finditer(source))
    if not matches:
        return [{"question_no": "1", "printed_text": source, "confidence": 0.55}]
    rows = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.end():end].strip()
        if body:
            rows.append({"question_no": match.group(1), "printed_text": body, "confidence": 0.82})
    return rows


def wrong_questions(rows: list[dict]) -> list[dict]:
    return [row for row in rows if normalize_answer_state(
        row.get("answer_state"), row.get("score"), row.get("max_score")
    ) in {"wrong", "partial", "blank", "review_required"}]


def normalize_eight_steps(payload: dict | None) -> list[dict]:
    payload = payload or {}
    supplied = payload.get("eight_steps") or payload.get("steps") or []
    by_key = {str(item.get("key") or ""): item for item in supplied if isinstance(item, dict)}
    result = []
    for index, (key, label) in enumerate(zip(EIGHT_STEP_KEYS, EIGHT_STEP_LABELS), start=1):
        item = by_key.get(key) or (supplied[index - 1] if index <= len(supplied) and isinstance(supplied[index - 1], dict) else {})
        result.append({
            "number": index,
            "key": key,
            "label": label,
            "content": str(item.get("content") or item.get("result") or "").strip(),
            "evidence": [str(x) for x in (item.get("evidence") or []) if str(x).strip()],
        })
    return result


def paper_summary(rows: list[dict]) -> dict:
    counts = {state: 0 for state in ANSWER_STATES}
    earned = possible = 0.0
    for row in rows:
        state = normalize_answer_state(row.get("answer_state"), row.get("score"), row.get("max_score"))
        counts[state] += 1
        earned += float(row.get("score") or 0)
        possible += float(row.get("max_score") or 0)
    return {
        "total_questions": len(rows),
        "counts": counts,
        "earned_score": round(earned, 2),
        "possible_score": round(possible, 2),
        "score_rate": round(earned / possible * 100, 1) if possible else None,
        "wrong_count": sum(counts[x] for x in ("wrong", "partial", "blank", "review_required")),
    }

