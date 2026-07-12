"""Pure rules for the wrong-answer remediation and spaced-review loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


REVIEW_INTERVAL_DAYS = (1, 3, 7, 14, 30)
PRACTICE_TIERS = (
    (1, "同型巩固", "same_pattern"),
    (2, "轻微变式", "near_transfer"),
    (3, "综合迁移", "far_transfer"),
)
ERROR_TYPES = {
    "knowledge_gap": "知识漏洞",
    "concept_confusion": "概念混淆",
    "reading_error": "审题错误",
    "calculation_error": "计算失误",
    "strategy_error": "方法选择",
    "expression_error": "表达不规范",
}


@dataclass(frozen=True)
class WorkflowState:
    state: str
    mastery_score: int
    review_stage: int
    next_review_at: str | None
    last_reviewed_at: str


def needs_calibration(text: str, confidence: float, threshold: float = 0.80) -> bool:
    compact = "".join((text or "").split())
    return confidence < threshold or len(compact) < 8


def normalize_error_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in ERROR_TYPES:
        return raw
    for key, label in ERROR_TYPES.items():
        if label in raw:
            return key
    return "knowledge_gap"


def practice_tier(level: int) -> dict:
    number, label, code = PRACTICE_TIERS[max(0, min(int(level), 3) - 1)]
    return {"level": number, "label": label, "code": code}


def mastery_score(results: Iterable[dict]) -> int:
    rows = list(results)
    if not rows:
        return 0
    tier_weights = {1: 25, 2: 35, 3: 40}
    score = 0.0
    possible = 0.0
    for row in rows:
        weight = tier_weights.get(int(row.get("level") or 1), 25)
        possible += weight
        if row.get("is_correct"):
            hint_penalty = min(max(int(row.get("hint_count") or 0), 0), 3) * 0.12
            score += weight * max(0.55, 1 - hint_penalty)
    return round(100 * score / possible) if possible else 0


def transition(results: Iterable[dict], review_stage: int = 0, now: datetime | None = None) -> dict:
    rows = list(results)
    now = now or datetime.now(timezone.utc)
    score = mastery_score(rows)
    all_tiers_correct = len({int(r.get("level") or 0) for r in rows if r.get("is_correct")}) >= 3
    if not all_tiers_correct or score < 75:
        state = "remediation"
        stage = 0
        due = None
    else:
        stage = min(max(review_stage, 0), len(REVIEW_INTERVAL_DAYS) - 1)
        state = "mastered" if stage == len(REVIEW_INTERVAL_DAYS) - 1 and score >= 85 else "review_scheduled"
        due = now + timedelta(days=REVIEW_INTERVAL_DAYS[stage])
    return asdict(WorkflowState(
        state=state,
        mastery_score=score,
        review_stage=stage,
        next_review_at=due.isoformat(timespec="seconds") if due else None,
        last_reviewed_at=now.isoformat(timespec="seconds"),
    ))

