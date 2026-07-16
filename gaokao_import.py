"""Import PDFs into gaokao question bank + RAG for 高考数学专区."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

from question_search import ZONE_GAOKAO_MATH, insert_question, now_iso, normalize_for_search
import gaokao_rag

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

_IMAGE_DIR_NAME = "gaokao-images"
_LECTURE_SPLIT = re.compile(r"(第\s*\d+\s*讲[^\n]{0,40})")
_YEAR_SPLIT = re.compile(r"(20\d{2})\s*年")
_QUESTION_SPLIT = re.compile(r"(?<=\n)(?:\d{1,2})[\.．、]\s*")


def _ensure_image_dir(public_dir: Path) -> Path:
    target = public_dir / "uploads" / _IMAGE_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def extract_pdf_pages(path: Path) -> list[dict]:
    if PdfReader is None:
        raise RuntimeError("缺少 pypdf，请 pip install pypdf")
    reader = PdfReader(str(path))
    pages: list[dict] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"page_no": index, "text": text})
    return pages


def extract_pdf_images(path: Path, public_dir: Path, doc_id: str, max_pages: int = 200) -> dict[int, list[str]]:
    """Extract embedded images per page when PyMuPDF is available."""
    if fitz is None:
        return {}
    out_dir = _ensure_image_dir(public_dir)
    by_page: dict[int, list[str]] = {}
    doc = fitz.open(str(path))
    try:
        for page_index in range(min(len(doc), max_pages)):
            page = doc[page_index]
            urls: list[str] = []
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n >= 5:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    name = f"{doc_id}-p{page_index + 1}-i{img_index + 1}.png"
                    file_path = out_dir / name
                    pix.save(str(file_path))
                    urls.append(f"/uploads/{_IMAGE_DIR_NAME}/{name}")
                except Exception:
                    continue
            if urls:
                by_page[page_index + 1] = urls
    finally:
        doc.close()
    return by_page


def split_into_chunks(pages: list[dict], doc_type: str) -> list[dict]:
    full = "\n\n".join(p["text"] for p in pages if p.get("text"))
    if not full.strip():
        return []
    chunks: list[dict] = []
    if doc_type == "lecture":
        parts = _LECTURE_SPLIT.split(full)
        current_title = Path(doc_type).stem
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if _LECTURE_SPLIT.match(part):
                current_title = part.strip()
                continue
            if len(part) < 80:
                continue
            chunks.append({"title": current_title, "stem": part[:6000], "lecture_no": current_title[:20]})
    elif doc_type == "exam_collection":
        blocks = _YEAR_SPLIT.split(full)
        current_year = ""
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            if re.fullmatch(r"20\d{2}", block):
                current_year = block
                continue
            subparts = _QUESTION_SPLIT.split(block)
            for sub in subparts:
                sub = sub.strip()
                if len(sub) < 40:
                    continue
                chunks.append({"title": f"{current_year}年高考数学" if current_year else "全国卷", "year": current_year, "stem": sub[:5000]})
    else:
        merged = full
        step = 1200
        overlap = 180
        start = 0
        idx = 0
        while start < len(merged):
            piece = merged[start : start + step].strip()
            if len(piece) >= 80:
                idx += 1
                chunks.append({"title": f"片段 {idx}", "stem": piece})
            start += step - overlap
    return chunks


def create_document_record(
    conn: sqlite3.Connection,
    *,
    title: str,
    source_filename: str,
    doc_type: str,
    pages: int,
    zone: str = ZONE_GAOKAO_MATH,
) -> str:
    doc_id = str(uuid.uuid4())
    conn.execute(
        """
        insert into gaokao_zone_documents
        (id, title, source_filename, doc_type, pages, question_count, image_count, status, error, zone, created_at)
        values (?, ?, ?, ?, ?, 0, 0, 'processing', '', ?, ?)
        """,
        (doc_id, title, source_filename, doc_type, pages, zone, now_iso()),
    )
    return doc_id


def finalize_document(
    conn: sqlite3.Connection,
    doc_id: str,
    *,
    question_count: int,
    image_count: int,
    status: str = "ready",
    error: str = "",
) -> None:
    conn.execute(
        """
        update gaokao_zone_documents
        set question_count = ?, image_count = ?, status = ?, error = ?
        where id = ?
        """,
        (question_count, image_count, status, error, doc_id),
    )


def import_pdf_file(
    conn: sqlite3.Connection,
    pdf_path: Path,
    *,
    public_dir: Path,
    doc_type: str = "upload",
    title: str | None = None,
    also_rag: bool = True,
) -> dict:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))
    pages = extract_pdf_pages(pdf_path)
    doc_id = create_document_record(
        conn,
        title=title or pdf_path.stem,
        source_filename=pdf_path.name,
        doc_type=doc_type,
        pages=len(pages),
    )
    if also_rag:
        gaokao_rag.delete_rag_for_gaokao_doc(conn, doc_id)
    images_by_page = extract_pdf_images(pdf_path, public_dir, doc_id)
    chunks = split_into_chunks(pages, doc_type)
    inserted = 0
    rag_indexed = 0
    image_total = sum(len(v) for v in images_by_page.values())
    doc_title = title or pdf_path.stem
    try:
        for chunk in chunks:
            page_images: list[str] = []
            record = insert_question(
                conn,
                document_id=doc_id,
                title=chunk.get("title") or doc_title,
                stem=chunk["stem"],
                answer=chunk.get("answer") or "",
                analysis=chunk.get("analysis") or "",
                question_no=chunk.get("question_no") or "",
                year=chunk.get("year") or "",
                region=chunk.get("region") or "",
                lecture_no=chunk.get("lecture_no") or "",
                source_page=chunk.get("source_page"),
                image_paths=page_images,
            )
            inserted += 1
            if also_rag:
                indexed = gaokao_rag.index_gaokao_question(
                    conn,
                    gaokao_doc_id=doc_id,
                    doc_title=doc_title,
                    question_id=record["id"],
                    title=record.get("title") or "",
                    stem=record.get("stem") or chunk["stem"],
                    answer=chunk.get("answer") or "",
                    analysis=chunk.get("analysis") or "",
                    lecture_no=chunk.get("lecture_no") or "",
                    year=chunk.get("year") or "",
                    question_no=chunk.get("question_no") or "",
                    source_page=chunk.get("source_page"),
                )
                if indexed:
                    rag_indexed += 1
        finalize_document(conn, doc_id, question_count=inserted, image_count=image_total, status="ready")
    except Exception as exc:
        finalize_document(conn, doc_id, question_count=inserted, image_count=image_total, status="failed", error=str(exc))
        raise
    return {
        "document_id": doc_id,
        "title": title or pdf_path.stem,
        "pages": len(pages),
        "questions": inserted,
        "images": image_total,
        "rag_indexed": rag_indexed,
        "chunks_preview": [normalize_for_search(c["stem"])[:120] for c in chunks[:3]],
    }


def guess_doc_type(filename: str) -> str:
    name = filename.lower()
    if "xiaoxiaole" in name or "消消乐" in name or "92" in name or "讲" in name:
        return "lecture"
    if "collection" in name or "15year" in name or "合集" in name or "全国卷" in name:
        return "exam_collection"
    return "upload"
