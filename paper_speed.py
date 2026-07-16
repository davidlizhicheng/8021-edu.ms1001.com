"""Parallel full-paper processing with incremental question visibility."""

from __future__ import annotations

import json
import uuid

import gaokao_rag
from question_search import ensure_gaokao_question_tables


def process_paper_job(server, paper_id: str, model_id: str | None = None) -> None:
    """Drop-in replacement using parallel OCR + batched diagnosis."""
    from speed_pipeline import parallel_run

    try:
        with server.db() as conn:
            server.ensure_gaokao_mother_catalog(conn)
            ensure_gaokao_question_tables(conn)
            gaokao_rag.ensure_rag_schema(conn)
            paper = conn.execute("select * from exam_papers where id = ?", (paper_id,)).fetchone()
            pages = conn.execute("select * from paper_pages where paper_id = ? order by page_no", (paper_id,)).fetchall()
            subject = (paper["subject"] if paper else None) or "自动识别"
            user_id = paper["user_id"] if paper else None
            conn.execute(
                "update exam_papers set status='processing',stage='ocr',progress=2,updated_at=? where id=?",
                (server.now_iso(), paper_id),
            )
            conn.execute(
                "update paper_jobs set status='processing',progress=2,attempts=attempts+1,updated_at=? where paper_id=?",
                (server.now_iso(), paper_id),
            )
        page_rows = [server.row_to_dict(p) for p in pages]

        def ocr_one(page: dict) -> dict:
            if page.get("source_url"):
                return server.best_of_two_paper_ocr(server.image_url_to_data_url(page["source_url"]), model_id)
            source_text = server.validate_paper_source_text(page.get("source_text") or "")
            return {
                "page_text": source_text,
                "page_confidence": 0.82,
                "parse_mode": "document_text",
                "questions": server.split_numbered_questions(source_text),
            }

        ocr_results = parallel_run(page_rows, ocr_one, max_workers=4)
        extracted: list[dict] = []
        for index, (page, result) in enumerate(zip(page_rows, ocr_results), start=1):
            for question in result.get("questions") or []:
                qid = str(uuid.uuid4())
                state = server.normalize_answer_state(question.get("answer_state"), question.get("score"), question.get("max_score"))
                confidence = float(question.get("confidence") or 0.55)
                with server.db() as conn:
                    conn.execute(
                        """insert into paper_questions
                        (id,paper_id,page_id,question_no,printed_text,student_work,teacher_marks,answer_state,score,max_score,confidence,bbox,eight_steps,diagnosis,wrong_question_id,review_required,created_at)
                        values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            qid,
                            paper_id,
                            page["id"],
                            str(question.get("question_no") or len(extracted) + 1),
                            question.get("printed_text") or "",
                            question.get("student_work") or "",
                            question.get("teacher_marks") or "",
                            state,
                            question.get("score"),
                            question.get("max_score"),
                            confidence,
                            json.dumps(question.get("bbox"), ensure_ascii=False),
                            json.dumps([], ensure_ascii=False),
                            json.dumps({"status": "ocr_ready"}, ensure_ascii=False),
                            None,
                            0,
                            server.now_iso(),
                        ),
                    )
                    conn.execute(
                        "update paper_pages set ocr_result=?,confidence=? where id=?",
                        (json.dumps(result, ensure_ascii=False), float(result.get("page_confidence") or 0), page["id"]),
                    )
                extracted.append({**question, "qid": qid, "page_id": page["id"], "answer_state": state, "confidence": confidence})
            progress = min(45, round(index / max(1, len(page_rows)) * 45))
            with server.db() as conn:
                conn.execute("update exam_papers set progress=?,stage='ocr',updated_at=? where id=?", (progress, server.now_iso(), paper_id))
                conn.execute("update paper_jobs set progress=?,updated_at=? where paper_id=?", (progress, server.now_iso(), paper_id))

        wrong_items = [q for q in extracted if q.get("answer_state") != "correct"]

        def diagnose_one(item: dict) -> None:
            text = item.get("printed_text") or ""
            wrong = item.get("student_work") or item.get("teacher_marks") or ""
            with server.db() as conn:
                rag_hits, rag_context = server.retrieve_gaokao_evidence(conn, text, subject)
            try:
                diagnosis = server.diagnose_with_llm(text, wrong, "", model_id, subject, rag_context=rag_context)
            except Exception as exc:
                diagnosis = server.fallback_paper_diagnosis(item, exc)
            diagnosis = server.enrich_gaokao_diagnosis(item, diagnosis, subject)
            steps = server.build_eight_steps(diagnosis, item)
            confidence = float(item.get("confidence") or 0.55)
            review_required = item.get("answer_state") == "review_required" or confidence < 0.72
            wrong_id = None
            with server.db() as conn:
                wrong_id = server.persist_wrong_from_paper(
                    conn,
                    paper_id,
                    item["qid"],
                    user_id,
                    {**item, "review_required": review_required},
                    diagnosis,
                )
                conn.execute(
                    """update paper_questions set eight_steps=?,diagnosis=?,wrong_question_id=?,review_required=?,confidence=?
                    where id=?""",
                    (
                        json.dumps(steps, ensure_ascii=False),
                        json.dumps(diagnosis, ensure_ascii=False),
                        wrong_id,
                        1 if review_required else 0,
                        confidence,
                        item["qid"],
                    ),
                )

        with server.db() as conn:
            conn.execute("update exam_papers set stage='diagnose',updated_at=? where id=?", (server.now_iso(), paper_id))

        total = max(1, len(wrong_items))
        for batch_start in range(0, len(wrong_items), 4):
            batch = wrong_items[batch_start : batch_start + 4]
            parallel_run(batch, diagnose_one, max_workers=min(4, len(batch)))
            progress = 45 + round(min(total, batch_start + len(batch)) / total * 50)
            with server.db() as conn:
                conn.execute("update exam_papers set progress=?,stage='diagnose',updated_at=? where id=?", (progress, server.now_iso(), paper_id))
                conn.execute("update paper_jobs set progress=?,updated_at=? where paper_id=?", (progress, server.now_iso(), paper_id))

        with server.db() as conn:
            rows = [server.row_to_dict(r) for r in conn.execute("select * from paper_questions where paper_id=?", (paper_id,)).fetchall()]
            summary = server.paper_summary(rows)
            matched = sum(
                1
                for row in rows
                if (json.loads(row.get("diagnosis") or "{}") if isinstance(row.get("diagnosis"), str) else row.get("diagnosis") or {}).get("mother_question")
            )
            summary["mother_matched_count"] = matched
            summary["knowledge_card_count"] = sum(1 for row in rows if row.get("answer_state") != "correct")
            summary["question_count_live"] = len(rows)
            conn.execute(
                "update exam_papers set status='completed',stage='report',summary=?,progress=100,updated_at=? where id=?",
                (json.dumps(summary, ensure_ascii=False), server.now_iso(), paper_id),
            )
            conn.execute(
                "update paper_jobs set status='completed',progress=100,message='分析完成',updated_at=? where paper_id=?",
                (server.now_iso(), paper_id),
            )
    except Exception as exc:
        with server.db() as conn:
            conn.execute("update exam_papers set status='failed',stage='failed',error=?,updated_at=? where id=?", (str(exc), server.now_iso(), paper_id))
            conn.execute("update paper_jobs set status='failed',message=?,updated_at=? where paper_id=?", (str(exc), server.now_iso(), paper_id))
