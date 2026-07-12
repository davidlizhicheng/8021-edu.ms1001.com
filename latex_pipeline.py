"""Mogan-inspired Magic Paste adapter: normalize educational files to LaTeX.

This is a web-side adapter. The upstream GPL Scheme reference is kept under
third_party/mogan and remains isolated from the application runtime.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


LATEX_ESCAPES = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape_latex(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in str(text or ""))


def wrap_document(body: str, title: str = "结构化试卷") -> str:
    return "\n".join([
        r"\documentclass[UTF8]{ctexart}", r"\usepackage{amsmath,amssymb,geometry,graphicx,longtable}",
        r"\geometry{a4paper,margin=2cm}", rf"\title{{{escape_latex(title)}}}", r"\date{}", r"\begin{document}",
        r"\maketitle", body.strip(), r"\end{document}", "",
    ])


def text_to_latex(text: str, title: str = "结构化试卷") -> str:
    blocks = []
    for raw in re.split(r"\n\s*\n", str(text or "")):
        line = raw.strip()
        if not line:
            continue
        # Preserve already-delimited LaTeX math while escaping surrounding text.
        pieces = re.split(r"(\$\$.*?\$\$|\$.*?\$)", line, flags=re.S)
        content = "".join(piece if piece.startswith("$") else escape_latex(piece).replace("\n", r"\\"+"\n") for piece in pieces)
        blocks.append(content + r"\par")
    return wrap_document("\n\n".join(blocks), title)


def convert_with_pandoc(content: bytes, suffix: str, title: str) -> str | None:
    pandoc = shutil.which("pandoc")
    if not pandoc or suffix not in {".docx", ".md", ".html", ".htm"}:
        return None
    with tempfile.TemporaryDirectory(prefix="edu-latex-") as tmp:
        source = Path(tmp) / ("source" + suffix)
        source.write_bytes(content)
        proc = subprocess.run([pandoc, str(source), "-t", "latex"], capture_output=True, timeout=45)
        if proc.returncode:
            return None
        return wrap_document(proc.stdout.decode("utf-8", "replace"), title)


def convert_bytes(filename: str, content: bytes, extracted_text: str = "") -> dict:
    suffix = Path(filename or "input.txt").suffix.lower()
    title = Path(filename or "结构化试卷").stem
    latex = convert_with_pandoc(content, suffix, title)
    engine = "pandoc-mogan-compatible" if latex else "structured-text-fallback"
    if not latex:
        latex = text_to_latex(extracted_text, title)
    embedded_formula_images = len(re.findall(r"\\includegraphics|\.wmf\b|\.emf\b", latex, re.I))
    return {"filename": f"{title}.tex", "latex": latex, "engine": engine, "requires_formula_review": engine != "pandoc-mogan-compatible" or embedded_formula_images > 0, "embedded_formula_images": embedded_formula_images, "source_type": suffix or ".txt"}


def detect_paste_format(text: str) -> str:
    raw = str(text or "").strip()
    if re.search(r"\\(documentclass|begin|frac|sum|int)\b", raw): return "latex"
    if re.search(r"</?[a-z][^>]*>", raw, re.I): return "html"
    if re.search(r"(^|\n)#{1,6}\s|```|\[[^]]+\]\([^)]+\)", raw): return "markdown"
    return "text"
