"""Parent weekly learning report from wrong-question stats."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def build_weekly_report(conn: sqlite3.Connection, user_id: str | None) -> dict:
    since = (datetime.utcnow() - timedelta(days=7)).replace(microsecond=0).isoformat() + "Z"
    sql = "select id, corrected_text, status, confidence, error_type, diagnosis, created_at from wrong_questions"
    params: list = []
    if user_id:
        sql += " where user_id = ?"
        params.append(user_id)
    rows = conn.execute(sql, params).fetchall()
    recent = []
    for row in rows:
        item = dict(row)
        ts = _parse_ts(item.get("created_at"))
        if ts and item.get("created_at", "") >= since:
            recent.append(item)
    patterns: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    passed = 0
    for item in recent:
        diag = json.loads(item.get("diagnosis") or "{}") if isinstance(item.get("diagnosis"), str) else item.get("diagnosis") or {}
        patterns[diag.get("core_pattern") or "未分类"] += 1
        errors[item.get("error_type") or "待分析"] += 1
        if item.get("status") == "passed":
            passed += 1
    total = len(recent)
    mastery_rate = round(passed / total * 100, 1) if total else 0.0
    summary_lines = [
        f"本周共记录 {total} 道错题，已消灭 {passed} 道（{mastery_rate}%）。",
        "高频题型：" + ("、".join(p for p, _ in patterns.most_common(3)) if patterns else "暂无"),
        "主要错因：" + ("、".join(e for e, _ in errors.most_common(3)) if errors else "暂无"),
        "建议：优先复习「待间隔复习」任务，每天 15 分钟完成 2–3 道消灭训练。",
    ]
    return {
        "period_days": 7,
        "total_wrongs": total,
        "passed_count": passed,
        "mastery_rate": mastery_rate,
        "top_patterns": [{"name": k, "count": v} for k, v in patterns.most_common(5)],
        "top_errors": [{"name": k, "count": v} for k, v in errors.most_common(5)],
        "summary": "\n".join(summary_lines),
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
