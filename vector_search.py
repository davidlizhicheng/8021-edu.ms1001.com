"""Lightweight hybrid retrieval: FTS + token-overlap semantic boost (no external embedding API)."""

from __future__ import annotations

import math
import re

from question_search import _TOKEN, normalize_for_search

_NGRAM = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}")


def _ngrams(text: str, n: int = 2) -> set[str]:
    raw = normalize_for_search(text).lower()
    grams: set[str] = set()
    for token in _NGRAM.findall(raw):
        if len(token) <= n:
            grams.add(token)
            continue
        for i in range(len(token) - n + 1):
            grams.add(token[i : i + n])
    return grams


def semantic_overlap_score(query: str, document: str) -> float:
    qg = _ngrams(query)
    dg = _ngrams(document)
    if not qg or not dg:
        return 0.0
    inter = len(qg & dg)
    union = len(qg | dg)
    jaccard = inter / union if union else 0.0
    token_bonus = sum(1 for t in _TOKEN.findall(normalize_for_search(query)) if t.lower() in document.lower()) * 0.8
    return round(jaccard * 40 + min(12.0, token_bonus), 2)


def rerank_hits(query: str, hits: list[dict], *, text_key: str = "stem") -> list[dict]:
    enriched: list[dict] = []
    for hit in hits:
        item = dict(hit)
        base = float(item.get("score") or 0)
        doc = " ".join(str(item.get(k) or "") for k in (text_key, "answer", "analysis", "title", "content"))
        sem = semantic_overlap_score(query, doc)
        item["semantic_score"] = sem
        item["hybrid_score"] = round(base * 0.62 + sem * 0.38, 2)
        enriched.append(item)
    enriched.sort(key=lambda x: float(x.get("hybrid_score") or 0), reverse=True)
    return enriched
