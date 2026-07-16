"""Handwriting-aware image preprocessing and OCR result scoring."""

from __future__ import annotations

import base64
import re
from io import BytesIO

HANDWRITING_OCR_HINT = """
【手写识别模式 — 高精度要求】
1. 图片含学生手写作答、演算、草稿、红叉/勾、圈画或教师批注。
2. 严格区分：印刷题干（printed_question） vs 手写作答（student_work） vs 批改痕迹（teacher_marks）。
3. 手写字逐行识别，保留算式顺序；连笔字结合上下文推断；看不清写 [?]，绝不编造。
4. 红笔批改、打叉、扣分、圈画单独写入 teacher_marks。
5. 数学公式转 LaTeX 或清晰文本；分数/根号/上下标尽量保留结构。
6. uncertain_parts 列出所有 [?] 或低置信片段。
"""

HANDWRITING_PHOTO_TIPS = [
    "光线均匀、避免反光和阴影",
    "手机正对纸面，减少透视变形",
    "单题裁剪比整页缩小更清晰",
    "手写字与印刷字分区明显时识别更准",
]


def preprocess_red_marks(image_data_url: str, *, max_long_side: int = 2600) -> tuple[str, dict]:
    """Boost red-ink strokes for teacher marks / crosses."""
    metadata = {"mode": "red_channel_boost", "processed": False}
    try:
        from PIL import Image, ImageEnhance, ImageOps

        _header, source_bytes = _decode_data_url(image_data_url)
        with Image.open(BytesIO(source_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            if max(image.size) > max_long_side:
                image.thumbnail((max_long_side, max_long_side), Image.Resampling.LANCZOS)
            r, g, b = image.split()
            # Emphasize red-dominant pixels typical of teacher pen marks.
            red_boost = r.point(lambda p: min(255, int(p * 1.25)))
            merged = Image.merge("RGB", (red_boost, g, b))
            enhanced = ImageEnhance.Contrast(merged).enhance(1.25)
            data_url = _encode_jpeg(enhanced, quality=93)
            metadata.update({"processed": True, "output_size": list(enhanced.size)})
            return data_url, metadata
    except Exception as exc:
        metadata["error"] = str(exc)[:160]
        return image_data_url, metadata


def merge_ocr_passes(*results: dict) -> dict:
    """Merge printed/student/teacher fields from multiple OCR passes."""
    if not results:
        return {}
    chosen = max(results, key=score_single_ocr_result)
    merged = dict(chosen)
    for result in results:
        for key in ("student_work", "teacher_marks", "printed_question", "ocr_text"):
            if not str(merged.get(key) or "").strip() and str(result.get(key) or "").strip():
                merged[key] = result.get(key)
        for part in result.get("uncertain_parts") or []:
            bucket = merged.setdefault("uncertain_parts", [])
            if part not in bucket:
                bucket.append(part)
    merged["confidence"] = normalize_ocr_confidence(merged)
    return merged


def merge_handwriting_prompt(base_prompt: str, handwriting: bool) -> str:
    if not handwriting:
        return base_prompt
    return f"{base_prompt.strip()}\n\n{HANDWRITING_OCR_HINT.strip()}"


def _decode_data_url(image_data_url: str) -> tuple[str, bytes]:
    header, encoded = image_data_url.split(",", 1)
    return header, base64.b64decode(encoded, validate=True)


def _encode_jpeg(image, *, quality: int = 92) -> str:
    from PIL import Image

    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def preprocess_for_handwriting(image_data_url: str, *, max_long_side: int = 2600) -> tuple[str, dict]:
    """Enhance contrast/sharpness for pencil/pen strokes; keep original on failure."""
    metadata = {"mode": "handwriting_enhanced", "processed": False}
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps

        _header, source_bytes = _decode_data_url(image_data_url)
        with Image.open(BytesIO(source_bytes)) as source:
            image = ImageOps.exif_transpose(source)
            original_size = list(image.size)
            if max(image.size) > max_long_side:
                image.thumbnail((max_long_side, max_long_side), Image.Resampling.LANCZOS)
            gray = image.convert("L")
            # Boost local contrast for faint pencil, then sharpen stroke edges.
            enhanced = ImageOps.autocontrast(gray, cutoff=1)
            enhanced = ImageEnhance.Contrast(enhanced).enhance(1.35)
            enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.6)
            enhanced = enhanced.filter(ImageFilter.UnsharpMask(radius=1.2, percent=140, threshold=2))
            rgb = Image.merge("RGB", (enhanced, enhanced, enhanced))
            data_url = _encode_jpeg(rgb, quality=93)
            metadata.update(
                {
                    "processed": True,
                    "original_size": original_size,
                    "output_size": list(rgb.size),
                    "max_long_side": max_long_side,
                }
            )
            return data_url, metadata
    except Exception as exc:
        metadata["error"] = str(exc)[:160]
        return image_data_url, metadata


def score_single_ocr_result(result: dict) -> float:
    """Higher is better — used to pick best_of_two passes."""
    text = " ".join(
        str(result.get(key) or "")
        for key in ("printed_question", "ocr_text", "student_work", "teacher_marks")
    ).strip()
    if not text:
        return 0.0
    confidence = float(result.get("confidence") or result.get("ocr_confidence") or 0.55)
    uncertain = result.get("uncertain_parts") or []
    question_marks = text.count("[?]") + text.count("?")
    has_student = 1.0 if str(result.get("student_work") or "").strip() else 0.0
    has_printed = 1.0 if len(str(result.get("printed_question") or text).strip()) >= 8 else 0.0
    penalty = min(0.35, question_marks * 0.04 + len(uncertain) * 0.06)
    length_bonus = min(0.15, len(text) / 1200)
    return confidence * 0.55 + has_printed * 0.2 + has_student * 0.1 + length_bonus - penalty


def normalize_ocr_confidence(result: dict) -> float:
    base = float(result.get("confidence") or result.get("ocr_confidence") or 0.75)
    text = str(result.get("ocr_text") or result.get("printed_question") or "")
    uncertain = result.get("uncertain_parts") or []
    marks = text.count("[?]")
    adjusted = base - min(0.25, marks * 0.03 + len(uncertain) * 0.04)
    return max(0.35, min(0.98, round(adjusted, 3)))


def fallback_eliminate_variants(question_text: str, core_pattern: str, wrong_answer: str) -> list[dict]:
    stem = (question_text or "本题").strip()[:320]
    core = core_pattern or "同类母题"
    hint = (wrong_answer or "补全手写作答").strip()[:120]
    return [
        {
            "level": 1,
            "title": "同型巩固",
            "stem": f"【消灭·同型】{stem}\n要求：按「{core}」标准路径分步完成，写出关键公式与结论。",
            "answer": "对照拆题粉碎步骤逐步核对。",
            "analysis": f"先复现母题模型，再对照你的作答断点：{hint}",
        },
        {
            "level": 2,
            "title": "轻微变式",
            "stem": f"【消灭·变式】在「{core}」框架下，改变一个条件或问法，重新求解。\n原题参考：{stem[:180]}",
            "answer": "写出完整推导并检验边界条件。",
            "analysis": "检验是否真正掌握模型，而非只会背步骤。",
        },
        {
            "level": 3,
            "title": "综合迁移",
            "stem": f"【消灭·迁移】把「{core}」方法迁移到新情境：{stem[:140]}…（自行补全可解版本）",
            "answer": "给出可检验的最终结论。",
            "analysis": "三道全对即宣告此题已消灭，可进入间隔复习。",
        },
    ]
