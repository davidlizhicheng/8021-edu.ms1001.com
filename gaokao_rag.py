"""Index gaokao mother-question bank into SQLite RAG (CS101-Copilot-style citations)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime

GAOKAO_RAG_SOURCE_TYPE = "gaokao_zone"
GAOKAO_RAG_SUBJECT = "高中数学"
GAOKAO_RAG_TITLE_PREFIX = "[高考专区]"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def rag_filename_for_doc(gaokao_doc_id: str) -> str:
    return f"{gaokao_doc_id}.gaokao.json"


def rag_title_for_doc(doc_title: str) -> str:
    title = (doc_title or "高考数学母题").strip()
    if title.startswith(GAOKAO_RAG_TITLE_PREFIX):
        return title[:120]
    return f"{GAOKAO_RAG_TITLE_PREFIX} {title}"[:120]


def format_gaokao_chunk_content(
    *,
    doc_title: str,
    lecture_no: str = "",
    year: str = "",
    question_no: str = "",
    source_page: int | None = None,
    stem: str,
) -> str:
    nodes = ["高考数学", doc_title.strip() or "母题文档"]
    if lecture_no:
        nodes.append(lecture_no.strip())
    elif year:
        nodes.append(f"{year}年")
    if question_no:
        nodes.append(f"题{question_no}")
    header = f"[知识节点: {' > '.join(nodes)}]"
    page_line = f"[页码: {source_page}]" if source_page else ""
    body = (stem or "").strip()
    return "\n".join(part for part in [header, page_line, body] if part)


def ensure_rag_schema(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("pragma table_info(rag_documents)").fetchall()}
    if "source_ref" not in cols:
        conn.execute("alter table rag_documents add column source_ref text")


def find_rag_document_id(conn: sqlite3.Connection, gaokao_doc_id: str) -> str | None:
    row = conn.execute(
        """
        select id from rag_documents
        where source_type = ? and (source_ref = ? or filename = ?)
        limit 1
        """,
        (GAOKAO_RAG_SOURCE_TYPE, gaokao_doc_id, rag_filename_for_doc(gaokao_doc_id)),
    ).fetchone()
    return row["id"] if row else None


def delete_rag_for_gaokao_doc(conn: sqlite3.Connection, gaokao_doc_id: str) -> None:
    rag_doc_id = find_rag_document_id(conn, gaokao_doc_id)
    if not rag_doc_id:
        return
    chunk_ids = [
        row["id"]
        for row in conn.execute("select id from rag_chunks where document_id = ?", (rag_doc_id,)).fetchall()
    ]
    for chunk_id in chunk_ids:
        try:
            conn.execute("delete from rag_chunks_fts where chunk_id = ?", (chunk_id,))
        except sqlite3.OperationalError:
            pass
    conn.execute("delete from rag_chunks where document_id = ?", (rag_doc_id,))
    conn.execute("delete from rag_documents where id = ?", (rag_doc_id,))


def ensure_rag_document(conn: sqlite3.Connection, *, gaokao_doc_id: str, doc_title: str) -> str:
    ensure_rag_schema(conn)
    existing = find_rag_document_id(conn, gaokao_doc_id)
    if existing:
        return existing
    rag_doc_id = str(uuid.uuid4())
    title = rag_title_for_doc(doc_title)
    created_at = now_iso()
    conn.execute(
        """
        insert into rag_documents
        (id, user_id, title, filename, subject, source_type, chars, created_at, source_ref)
        values (?, null, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            rag_doc_id,
            title,
            rag_filename_for_doc(gaokao_doc_id),
            GAOKAO_RAG_SUBJECT,
            GAOKAO_RAG_SOURCE_TYPE,
            created_at,
            gaokao_doc_id,
        ),
    )
    return rag_doc_id


def _next_chunk_index(conn: sqlite3.Connection, rag_doc_id: str) -> int:
    row = conn.execute(
        "select coalesce(max(chunk_index), -1) as mx from rag_chunks where document_id = ?",
        (rag_doc_id,),
    ).fetchone()
    return int(row["mx"] or -1) + 1


def index_gaokao_question(
    conn: sqlite3.Connection,
    *,
    gaokao_doc_id: str,
    doc_title: str,
    question_id: str,
    title: str = "",
    stem: str,
    answer: str = "",
    analysis: str = "",
    lecture_no: str = "",
    year: str = "",
    question_no: str = "",
    source_page: int | None = None,
) -> dict | None:
    stem = (stem or "").strip()
    if len(stem) < 12:
        return None
    rag_doc_id = ensure_rag_document(conn, gaokao_doc_id=gaokao_doc_id, doc_title=doc_title)
    chunk_title = title or lecture_no or year or doc_title
    content = format_gaokao_chunk_content(
        doc_title=doc_title,
        lecture_no=lecture_no,
        year=year,
        question_no=question_no,
        source_page=source_page,
        stem=stem,
    )
    if answer.strip():
        content += f"\n\n[参考答案]\n{answer.strip()[:2000]}"
    if analysis.strip():
        content += f"\n\n[解析片段]\n{analysis.strip()[:2000]}"
    chunk_index = _next_chunk_index(conn, rag_doc_id)
    chunk_id = str(uuid.uuid4())
    created_at = now_iso()
    conn.execute(
        """
        insert into rag_chunks
        (id, document_id, user_id, chunk_index, title, subject, content, chars, created_at)
        values (?, ?, null, ?, ?, ?, ?, ?, ?)
        """,
        (chunk_id, rag_doc_id, chunk_index, chunk_title[:120], GAOKAO_RAG_SUBJECT, content, len(content), created_at),
    )
    try:
        conn.execute(
            """
            insert into rag_chunks_fts (chunk_id, document_id, user_id, title, subject, content)
            values (?, ?, '', ?, ?, ?)
            """,
            (chunk_id, rag_doc_id, chunk_title[:120], GAOKAO_RAG_SUBJECT, content),
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "update rag_documents set chars = coalesce(chars, 0) + ? where id = ?",
        (len(content), rag_doc_id),
    )
    return {
        "chunk_id": chunk_id,
        "document_id": rag_doc_id,
        "gaokao_doc_id": gaokao_doc_id,
        "gaokao_question_id": question_id,
        "chunk_index": chunk_index,
        "title": chunk_title,
    }


def index_gaokao_question_row(conn: sqlite3.Connection, row: sqlite3.Row | dict, doc_title: str) -> dict | None:
    item = dict(row)
    return index_gaokao_question(
        conn,
        gaokao_doc_id=item.get("document_id") or "",
        doc_title=doc_title,
        question_id=item.get("id") or "",
        title=item.get("title") or "",
        stem=item.get("stem") or "",
        answer=item.get("answer") or "",
        analysis=item.get("analysis") or "",
        lecture_no=item.get("lecture_no") or "",
        year=item.get("year") or "",
        question_no=item.get("question_no") or "",
        source_page=item.get("source_page"),
    )


def sync_document_to_rag(conn: sqlite3.Connection, gaokao_doc_id: str, *, rebuild: bool = False) -> dict:
    doc = conn.execute("select * from gaokao_zone_documents where id = ?", (gaokao_doc_id,)).fetchone()
    if not doc:
        raise ValueError("gaokao document not found")
    doc = dict(doc)
    if rebuild:
        delete_rag_for_gaokao_doc(conn, gaokao_doc_id)
    rows = conn.execute(
        "select * from gaokao_questions where document_id = ? order by created_at asc",
        (gaokao_doc_id,),
    ).fetchall()
    indexed = 0
    for row in rows:
        if index_gaokao_question_row(conn, row, doc.get("title") or doc.get("source_filename") or "高考数学"):
            indexed += 1
    return {"gaokao_doc_id": gaokao_doc_id, "title": doc.get("title"), "indexed": indexed, "total": len(rows)}


def sync_all_gaokao_to_rag(conn: sqlite3.Connection, *, rebuild: bool = True) -> dict:
    docs = conn.execute("select id, title from gaokao_zone_documents where status = 'ready' order by created_at asc").fetchall()
    summary = {"documents": 0, "indexed": 0, "details": []}
    for doc in docs:
        if rebuild:
            delete_rag_for_gaokao_doc(conn, doc["id"])
        result = sync_document_to_rag(conn, doc["id"], rebuild=False)
        summary["documents"] += 1
        summary["indexed"] += result["indexed"]
        summary["details"].append(result)
    return summary


def should_use_gaokao_rag(subject: str, question_text: str = "") -> bool:
    subject = (subject or "").strip()
    text = (question_text or "").strip()
    if "数学" in subject and ("高中" in subject or "高考" in subject or subject == "自动识别"):
        return True
    if subject in {"", "自动识别"} and re.search(r"函数|数列|导数|向量|圆锥|概率|三角|不等式|集合|复数", text):
        return True
    if re.search(r"高考|全国卷|新高考|理科|文科", text):
        return True
    return subject == "高中数学"


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}", text or "")
    if not tokens:
        return ""
    tokens = sorted(set(tokens), key=len, reverse=True)[:14]
    return " OR ".join(f'"{t}"' if len(t) > 4 else t for t in tokens)


def _fallback_score(query: str, content: str) -> float:
    q = re.sub(r"\s+", "", query or "").lower()
    c = (content or "").lower()
    if not q or not c:
        return 0.0
    score = 0.0
    for token in re.findall(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}", query or ""):
        if token.lower() in c:
            score += min(5.0, len(token) / 2)
    return score


def search_gaokao_rag(conn: sqlite3.Connection, query: str, limit: int = 6) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit or 6), 12))
    ensure_rag_schema(conn)
    candidates: list[dict] = []
    fts = _fts_query(query)
    if fts:
        try:
            rows = conn.execute(
                """
                select c.*, d.title as doc_title, d.source_ref as gaokao_doc_id, bm25(rag_chunks_fts) as rank
                from rag_chunks_fts
                join rag_chunks c on c.id = rag_chunks_fts.chunk_id
                join rag_documents d on d.id = c.document_id
                where rag_chunks_fts match ?
                  and d.source_type = ?
                order by rank
                limit ?
                """,
                (fts, GAOKAO_RAG_SOURCE_TYPE, limit * 4),
            ).fetchall()
            for row in rows:
                item = dict(row)
                item["score"] = round(100 / (1 + abs(float(row["rank"] or 0))), 2)
                item["source"] = "gaokao_rag"
                candidates.append(item)
        except sqlite3.OperationalError:
            candidates = []
    if len(candidates) < limit:
        seen = {c.get("id") for c in candidates}
        rows = conn.execute(
            """
            select c.*, d.title as doc_title, d.source_ref as gaokao_doc_id
            from rag_chunks c
            join rag_documents d on d.id = c.document_id
            where d.source_type = ?
            order by c.created_at desc
            limit 500
            """,
            (GAOKAO_RAG_SOURCE_TYPE,),
        ).fetchall()
        fallback = []
        for row in rows:
            item = dict(row)
            if item.get("id") in seen:
                continue
            score = _fallback_score(query, item.get("content") or "")
            if score >= 3:
                item["score"] = round(score, 2)
                item["source"] = "gaokao_rag"
                fallback.append(item)
        fallback.sort(key=lambda x: x.get("score", 0), reverse=True)
        candidates.extend(fallback[: limit * 2])
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    results = []
    for item in candidates[:limit]:
        results.append(
            {
                "id": item.get("id"),
                "document_id": item.get("document_id"),
                "gaokao_doc_id": item.get("gaokao_doc_id"),
                "chunk_index": item.get("chunk_index"),
                "title": item.get("title") or item.get("doc_title"),
                "subject": GAOKAO_RAG_SUBJECT,
                "content": item.get("content"),
                "score": item.get("score", 0),
                "source": "gaokao_rag",
                "created_at": item.get("created_at"),
            }
        )
    return results


def build_gaokao_rag_context(hits: list[dict]) -> str:
    if not hits:
        return ""
    blocks = []
    for index, chunk in enumerate(hits, start=1):
        label = chunk.get("title") or "高考母题"
        blocks.append(
            f"【母题资料{index}｜{label}｜相关度{chunk.get('score', 0)}】\n{(chunk.get('content') or '')[:1200]}"
        )
    return "\n\n".join(blocks)


def rag_citations_from_hits(hits: list[dict]) -> list[dict]:
    citations = []
    for index, hit in enumerate(hits, start=1):
        citations.append(
            {
                "label": f"母题{index}",
                "title": hit.get("title"),
                "document_id": hit.get("document_id"),
                "gaokao_doc_id": hit.get("gaokao_doc_id"),
                "chunk_id": hit.get("id"),
                "score": hit.get("score", 0),
            }
        )
    return citations
