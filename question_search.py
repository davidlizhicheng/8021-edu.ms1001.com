"""Fast question-bank search for 搜题模式 (photo/text → indexed gaokao questions)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime

ZONE_GAOKAO_MATH = "gaokao-math"

_LATEX_NOISE = re.compile(
    r"\\(?:documentclass|usepackage|begin|end|title|maketitle|section|subsection|par|textbf|textit|emph|includegraphics)\{[^}]*\}|\\[a-zA-Z]+|\$+"
)
_TOKEN = re.compile(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}")


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_for_search(text: str) -> str:
    raw = str(text or "")
    raw = _LATEX_NOISE.sub(" ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def fts_query(text: str) -> str:
    tokens = _TOKEN.findall(normalize_for_search(text))
    if not tokens:
        return ""
    # Prefer longer Chinese tokens; cap query size for SQLite FTS.
    tokens = sorted(set(tokens), key=len, reverse=True)[:12]
    return " OR ".join(f'"{t}"' if len(t) > 4 else t for t in tokens)


def fallback_score(query: str, haystack: str) -> float:
    q = normalize_for_search(query).lower()
    h = haystack.lower()
    if not q or not h:
        return 0.0
    score = 0.0
    for token in _TOKEN.findall(q):
        if token.lower() in h:
            score += min(6.0, len(token) / 2)
    if len(q) >= 8 and q[:24] in h:
        score += 8.0
    return score


def ensure_gaokao_question_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists gaokao_zone_documents (
          id text primary key,
          title text not null,
          source_filename text,
          doc_type text not null default 'upload',
          pages integer not null default 0,
          question_count integer not null default 0,
          image_count integer not null default 0,
          status text not null default 'ready',
          error text,
          zone text not null default 'gaokao-math',
          created_at text not null
        );

        create table if not exists gaokao_questions (
          id text primary key,
          document_id text,
          zone text not null default 'gaokao-math',
          title text,
          question_no text,
          year text,
          region text,
          lecture_no text,
          stem text not null,
          answer text,
          analysis text,
          stem_md text,
          search_text text not null,
          image_paths text,
          source_page integer,
          created_at text not null,
          foreign key(document_id) references gaokao_zone_documents(id)
        );

        create virtual table if not exists gaokao_questions_fts using fts5(
          question_id unindexed,
          document_id unindexed,
          zone unindexed,
          title,
          search_text,
          answer,
          tokenize = 'unicode61'
        );
        """
    )


def row_to_dict(row: sqlite3.Row | dict | None) -> dict:
    return dict(row) if row else {}


def public_question(row: sqlite3.Row | dict) -> dict:
    item = row_to_dict(row)
    images = []
    try:
        images = json.loads(item.get("image_paths") or "[]")
    except json.JSONDecodeError:
        images = []
    return {
        "id": item.get("id"),
        "document_id": item.get("document_id"),
        "zone": item.get("zone"),
        "title": item.get("title"),
        "question_no": item.get("question_no"),
        "year": item.get("year"),
        "region": item.get("region"),
        "lecture_no": item.get("lecture_no"),
        "stem": item.get("stem"),
        "answer": item.get("answer"),
        "analysis": item.get("analysis"),
        "stem_md": item.get("stem_md"),
        "images": images,
        "source_page": item.get("source_page"),
        "score": item.get("score", 0),
        "created_at": item.get("created_at"),
    }


def insert_question(
    conn: sqlite3.Connection,
    *,
    document_id: str | None,
    title: str,
    stem: str,
    answer: str = "",
    analysis: str = "",
    question_no: str = "",
    year: str = "",
    region: str = "",
    lecture_no: str = "",
    source_page: int | None = None,
    image_paths: list[str] | None = None,
    zone: str = ZONE_GAOKAO_MATH,
) -> dict:
    stem = (stem or "").strip()
    if len(stem) < 12:
        raise ValueError("题干过短，无法入库")
    qid = str(uuid.uuid4())
    created = now_iso()
    search_text = normalize_for_search(stem)
    stem_md = stem
    conn.execute(
        """
        insert into gaokao_questions
        (id, document_id, zone, title, question_no, year, region, lecture_no,
         stem, answer, analysis, stem_md, search_text, image_paths, source_page, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            qid,
            document_id,
            zone,
            title,
            question_no,
            year,
            region,
            lecture_no,
            stem,
            answer,
            analysis,
            stem_md,
            search_text,
            json.dumps(image_paths or [], ensure_ascii=False),
            source_page,
            created,
        ),
    )
    conn.execute(
        """
        insert into gaokao_questions_fts (question_id, document_id, zone, title, search_text, answer)
        values (?, ?, ?, ?, ?, ?)
        """,
        (qid, document_id or "", zone, title, search_text, answer or ""),
    )
    row = conn.execute("select * from gaokao_questions where id = ?", (qid,)).fetchone()
    return public_question(row)


def search_questions(
    conn: sqlite3.Connection,
    query: str,
    *,
    zone: str = ZONE_GAOKAO_MATH,
    limit: int = 8,
    min_score: float = 4.0,
) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit or 8), 20))
    candidates: list[dict] = []
    fts = fts_query(query)
    if fts:
        try:
            rows = conn.execute(
                """
                select q.*, bm25(gaokao_questions_fts) as rank
                from gaokao_questions_fts
                join gaokao_questions q on q.id = gaokao_questions_fts.question_id
                where gaokao_questions_fts match ? and q.zone = ?
                order by rank
                limit ?
                """,
                (fts, zone, limit * 3),
            ).fetchall()
            for row in rows:
                item = public_question(row)
                item["score"] = round(100 / (1 + abs(float(row["rank"] or 0))), 2)
                candidates.append(item)
        except sqlite3.OperationalError:
            candidates = []
    if len(candidates) < limit:
        seen = {c["id"] for c in candidates}
        rows = conn.execute(
            "select * from gaokao_questions where zone = ? order by created_at desc limit 400",
            (zone,),
        ).fetchall()
        fallback: list[dict] = []
        for row in rows:
            item = public_question(row)
            if item["id"] in seen:
                continue
            score = fallback_score(query, f"{item.get('title')}\n{item.get('stem')}\n{item.get('answer')}")
            if score >= min_score:
                item["score"] = round(score, 2)
                fallback.append(item)
        fallback.sort(key=lambda x: x.get("score", 0), reverse=True)
        candidates.extend(fallback[: limit * 2])
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates[:limit]


def zone_stats(conn: sqlite3.Connection, zone: str = ZONE_GAOKAO_MATH) -> dict:
    docs = conn.execute(
        "select count(*) as c from gaokao_zone_documents where zone = ?", (zone,)
    ).fetchone()["c"]
    questions = conn.execute(
        "select count(*) as c from gaokao_questions where zone = ?", (zone,)
    ).fetchone()["c"]
    return {"zone": zone, "documents": int(docs or 0), "questions": int(questions or 0)}


def list_documents(conn: sqlite3.Connection, zone: str = ZONE_GAOKAO_MATH) -> list[dict]:
    rows = conn.execute(
        """
        select * from gaokao_zone_documents
        where zone = ?
        order by created_at desc
        """,
        (zone,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]
