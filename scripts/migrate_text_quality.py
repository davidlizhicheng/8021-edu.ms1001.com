"""Repair historical mojibake and replace unhelpful placeholders in persisted output."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import _replace_placeholder_tree, normalize_diagnosis_payload, repair_mojibake_text, repair_text_tree, text_quality_issues


JSON_COLUMNS = {
    "wrong_questions": {"diagnosis": "diagnosis"},
    "paper_questions": {"diagnosis": "diagnosis", "eight_steps": "generic"},
    "paper_pages": {"ocr_result": "generic"},
    "student_answers": {"grading_result": "generic"},
    "agent_runs": {"result": "generic"},
    "mother_questions": {"trigger_features": "generic", "scoring_rules": "generic", "variants": "generic"},
}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"pragma table_info({table})")}


def migrate(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    changed: dict[str, int] = {}
    for table in sorted(tables):
        columns = table_columns(conn, table)
        if "id" not in columns:
            continue
        text_columns = [name for name in columns if name not in {"id"} and name not in JSON_COLUMNS.get(table, {}) and name in {
            "ocr_text", "corrected_text", "student_wrong_answer", "printed_text", "student_work", "teacher_marks",
            "answer_text", "title", "stem", "answer", "analysis", "prompt", "subject", "question_text",
            "student_answer", "tool_label", "input_text", "output_text", "name", "topic", "mnemonic", "content",
        }]
        json_columns = {name: kind for name, kind in JSON_COLUMNS.get(table, {}).items() if name in columns}
        select_columns = ["id", *text_columns, *json_columns]
        table_changes = 0
        for row in conn.execute(f"select {', '.join(select_columns)} from {table}").fetchall():
            updates = {}
            for column in text_columns:
                repaired = repair_mojibake_text(row[column])
                if repaired != (row[column] or ""):
                    updates[column] = repaired
            for column, kind in json_columns.items():
                raw = row[column]
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    repaired = repair_mojibake_text(raw)
                    if repaired != raw:
                        updates[column] = repaired
                    continue
                if kind == "diagnosis":
                    question = row["corrected_text"] if "corrected_text" in columns else row["printed_text"] if "printed_text" in columns else ""
                    answer = row["student_wrong_answer"] if "student_wrong_answer" in columns else row["student_work"] if "student_work" in columns else ""
                    value = normalize_diagnosis_payload(value, question or "", answer or "")
                else:
                    value = _replace_placeholder_tree(repair_text_tree(value))
                encoded = json.dumps(value, ensure_ascii=False)
                if encoded != raw:
                    updates[column] = encoded
            if updates:
                assignments = ", ".join(f"{key} = ?" for key in updates)
                conn.execute(f"update {table} set {assignments} where id = ?", [*updates.values(), row["id"]])
                table_changes += 1
        if table_changes:
            changed[table] = table_changes
    conn.commit()
    audit = []
    if "wrong_questions" in tables:
        for row in conn.execute("select id, diagnosis from wrong_questions where diagnosis is not null and trim(diagnosis) <> ''"):
            try:
                issues = text_quality_issues(json.loads(row["diagnosis"]))
            except json.JSONDecodeError:
                issues = ["invalid_json"]
            if issues:
                audit.append({"table": "wrong_questions", "id": row["id"], "issues": issues})
    conn.close()
    return {"changed": changed, "remaining_issues": audit}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(migrate(args.database), ensure_ascii=False))
