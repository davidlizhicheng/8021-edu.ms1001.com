"""Teacher loop: classes, review queue, batch export helpers."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_teacher_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists teacher_classes (
          id text primary key,
          user_id text,
          name text not null,
          grade text,
          note text,
          created_at text not null
        );
        create table if not exists class_members (
          id text primary key,
          class_id text not null,
          student_name text not null,
          parent_contact text,
          created_at text not null
        );
        """
    )


def list_classes(conn: sqlite3.Connection, user_id: str | None) -> list[dict]:
    ensure_teacher_schema(conn)
    if user_id:
        rows = conn.execute(
            "select * from teacher_classes where user_id = ? order by created_at desc",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute("select * from teacher_classes order by created_at desc limit 20").fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["member_count"] = conn.execute(
            "select count(*) from class_members where class_id = ?",
            (item["id"],),
        ).fetchone()[0]
        out.append(item)
    return out


def create_class(conn: sqlite3.Connection, user_id: str | None, payload: dict) -> dict:
    ensure_teacher_schema(conn)
    class_id = str(uuid.uuid4())
    ts = now_iso()
    conn.execute(
        "insert into teacher_classes (id,user_id,name,grade,note,created_at) values (?,?,?,?,?,?)",
        (class_id, user_id, payload.get("name") or "未命名班级", payload.get("grade") or "", payload.get("note") or "", ts),
    )
    for name in payload.get("students") or []:
        if not str(name).strip():
            continue
        conn.execute(
            "insert into class_members (id,class_id,student_name,parent_contact,created_at) values (?,?,?,?,?)",
            (str(uuid.uuid4()), class_id, str(name).strip(), "", ts),
        )
    row = conn.execute("select * from teacher_classes where id = ?", (class_id,)).fetchone()
    item = dict(row)
    item["member_count"] = conn.execute("select count(*) from class_members where class_id = ?", (class_id,)).fetchone()[0]
    return item


def review_queue(conn: sqlite3.Connection, user_id: str | None, limit: int = 50) -> list[dict]:
    ensure_teacher_schema(conn)
    sql = """
        select id, corrected_text, student_wrong_answer, status, confidence, error_type, diagnosis, created_at
        from wrong_questions
        where status in ('review_needed','remediation')
    """
    params: list = []
    if user_id:
        sql += " and user_id = ?"
        params.append(user_id)
    sql += " order by created_at desc limit ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        diag_raw = item.pop("diagnosis", None)
        diag = json.loads(diag_raw or "{}") if isinstance(diag_raw, str) else diag_raw or {}
        item["core_pattern"] = diag.get("core_pattern") or "待复核"
        item["needs_review_reason"] = diag.get("gaokao_rag", {}).get("mode") or item.get("error_type") or "低置信"
        out.append(item)
    return out


def review_export_text(items: list[dict]) -> str:
    lines = ["# 教师待复核清单", ""]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {index}. {item.get('core_pattern') or '题目'}",
                f"- 状态：{item.get('status')}",
                f"- 置信度：{round(float(item.get('confidence') or 0)*100)}%",
                f"- 题干：{(item.get('corrected_text') or '')[:400]}",
                f"- 错答：{(item.get('student_wrong_answer') or '')[:200]}",
                "",
            ]
        )
    return "\n".join(lines)
