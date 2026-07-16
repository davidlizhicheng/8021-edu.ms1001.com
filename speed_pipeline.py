"""Speed optimizations: parallel OCR, search-first diagnosis, handwriting OCR."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from handwriting_ocr import (
    HANDWRITING_OCR_HINT,
    HANDWRITING_PHOTO_TIPS,
    fallback_eliminate_variants,
    merge_handwriting_prompt,
    normalize_ocr_confidence,
    preprocess_for_handwriting,
    score_single_ocr_result,
)

SEARCH_HIT_THRESHOLD = 22.0
INSTANT_HIT_THRESHOLD = 15.0

QUICK_DIAGNOSE_PROMPT = """你是高中解题教练。请快速输出 JSON（不要 markdown），字段：
subject, confidence, core_pattern, topic, needs_review,
standard_answer{final_answer, concise_solution},
student_answer_analysis{answer_presence, extracted_work, answer_status, likely_issue, error_type, evidence[], next_action},
decomposition{total_formula, step_formulas[{name, formula, operation, student_trap}]},
learning_strategy{decomposition_answer, make_it_easier, entry_point, cognitive_ladder[], micro_drills[], teacher_hint},
poem{title, lines[]}
要求：简洁、可执行；3-5 个 step_formulas；不要 practice_variants。"""


def parallel_run(tasks: list, worker: Callable, max_workers: int = 4) -> list:
    if not tasks:
        return []
    max_workers = max(1, min(int(max_workers or 4), len(tasks)))
    if len(tasks) == 1:
        return [worker(tasks[0])]
    results: list = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(worker, task): index for index, task in enumerate(tasks)}
        for future in as_completed(future_map):
            index = future_map[future]
            results[index] = future.result()
    return results


def build_instant_diagnosis(
    question_text: str,
    wrong_answer: str,
    subject: str = "自动识别",
    hits: list[dict] | None = None,
    rag_hits: list[dict] | None = None,
) -> dict:
    """Zero-LLM diagnosis path — target <3s end-to-end."""
    if hits:
        fast = build_fast_diagnosis_from_hits(
            question_text, wrong_answer, hits, rag_hits, min_score=INSTANT_HIT_THRESHOLD
        )
        if fast:
            return fast
    diagnosis = build_skeleton_diagnosis(question_text, wrong_answer, subject)
    if hits:
        top = hits[0]
        stem = top.get("stem") or top.get("content") or ""
        analysis = top.get("analysis") or ""
        core = top.get("title") or top.get("lecture_no") or diagnosis.get("core_pattern")
        diagnosis["core_pattern"] = core
        diagnosis["topic"] = core
        if stem:
            diagnosis.setdefault("standard_answer", {})
            diagnosis["standard_answer"]["concise_solution"] = (analysis or stem)[:900]
            diagnosis["student_answer_analysis"]["evidence"] = [
                f"混合检索命中 {round(float(top.get('hybrid_score') or top.get('score') or 0), 1)} 分"
            ]
    if rag_hits:
        snippet = (rag_hits[0].get("content") or "")[:500]
        diagnosis.setdefault("standard_answer", {})
        if snippet and not diagnosis["standard_answer"].get("concise_solution"):
            diagnosis["standard_answer"]["concise_solution"] = snippet
        diagnosis["gaokao_rag"] = {
            "used": True,
            "evidence_count": len(rag_hits),
            "mode": "instant_rag",
        }
    else:
        diagnosis["gaokao_rag"] = {"used": False, "mode": "instant_skeleton"}
    diagnosis["needs_review"] = True
    return diagnosis


def build_skeleton_diagnosis(question_text: str, wrong_answer: str, subject: str = "自动识别") -> dict:
    text = (question_text or "").strip()
    if any(k in text for k in ("充分", "必要", "充要")):
        topic = "逻辑与条件判断：先分清充分、必要方向，再用推导或反例验证"
    elif "函数" in text and any(k in text for k in ("最小", "最大", "最值", "单调")):
        topic = "函数最值与单调性：先识别函数类型，再用配方、判别式或导数确定取值范围"
    elif any(k in text for k in ("向量", "共线", "垂直", "平行")):
        topic = "向量关系判定：把几何条件翻译成系数、数量积或坐标方程逐项核对"
    elif any(k in text for k in ("概率", "随机变量", "期望", "方差")):
        topic = "概率统计模型：先确定样本空间与事件，再选择计数、条件概率或分布公式"
    elif any(k in text for k in ("数列", "通项", "前n项", "前 n 项")):
        topic = "数列通项与求和：先判断等差、等比或递推结构，再选择通项和求和公式"
    elif any(k in text for k in ("圆", "椭圆", "双曲线", "抛物线")):
        topic = "解析几何：把位置关系转成方程组、判别式与韦达关系"
    else:
        topic = f"题型入口初判：提取已知条件与目标，先建立它们之间的公式关系（{text.split(chr(10))[0][:32]}）" if text else "待归纳题型"
    return {
        "subject": subject or "自动识别",
        "confidence": 0.62,
        "core_pattern": topic,
        "topic": topic,
        "needs_review": True,
        "standard_answer": {
            "final_answer": "请先核对题干条件与选项/结论是否对应。",
            "concise_solution": "读题 → 判充分/必要/充要 → 举反例或推导 → 选结论。",
        },
        "student_answer_analysis": {
            "answer_presence": "已提供" if wrong_answer else "未提供",
            "extracted_work": wrong_answer,
            "answer_status": "已记录，待逐步核对",
            "likely_issue": "题型入口或条件方向可能混淆，请对照粉碎步骤逐步检查。",
            "error_type": "概念混淆",
            "evidence": ["未命中高考母题库，已启用快速拆题骨架"],
            "next_action": "先看粉碎步骤，再去做消灭训练题。",
        },
        "decomposition": {
            "total_formula": "读题 → 提取条件 → 判断关系 → 验证 → 结论",
            "step_formulas": [
                {"name": "读题", "formula": text[:120], "operation": "圈出题干条件与问法", "student_trap": "看错条件方向"},
                {"name": "判关系", "formula": topic, "operation": "区分充分/必要/充要", "student_trap": "充分必要搞反"},
                {"name": "验证", "formula": wrong_answer[:120] if wrong_answer else "补作答", "operation": "举反例或推导", "student_trap": "未验证"},
            ],
        },
        "learning_strategy": {
            "decomposition_answer": "先判题型入口，再逐步粉碎错因，最后用变式题消灭。",
            "make_it_easier": "做一个更小的同类判断题再迁移。",
            "entry_point": topic,
            "cognitive_ladder": ["读题", "判关系", "粉碎错因", "消灭巩固"],
            "micro_drills": ["用一句话说清条件关系", "举一个反例"],
            "teacher_hint": "这道题最容易混淆的是哪个条件方向？",
        },
        "practice_variants": [],
        "gaokao_rag": {"used": False, "mode": "skeleton_fast"},
        "poem": {"title": "快速复盘", "lines": ["先读题意别慌张", "条件方向先辨明", "逐步粉碎找断点", "三道训练消灭光"], "line_reviews": []},
    }


def build_fast_diagnosis_from_hits(
    question_text: str,
    wrong_answer: str,
    hits: list[dict],
    rag_hits: list[dict] | None = None,
    *,
    min_score: float | None = None,
) -> dict | None:
    if not hits:
        return None
    top = hits[0]
    score = float(top.get("hybrid_score") or top.get("score") or 0)
    threshold = float(min_score if min_score is not None else SEARCH_HIT_THRESHOLD)
    if score < threshold:
        return None
    stem = top.get("stem") or top.get("content") or question_text
    answer = top.get("answer") or ""
    analysis = top.get("analysis") or ""
    rag_snippet = ""
    if rag_hits:
        rag_snippet = (rag_hits[0].get("content") or "")[:600]
    core = top.get("title") or top.get("lecture_no") or "高考同类母题"
    return {
        "subject": "高中数学",
        "confidence": min(0.92, 0.65 + score / 100),
        "core_pattern": core,
        "topic": core,
        "needs_review": score < 28,
        "standard_answer": {
            "final_answer": answer[:800] or "请对照母题库片段与完整题干完成作答。",
            "concise_solution": (analysis or rag_snippet or stem)[:1200],
        },
        "student_answer_analysis": {
            "answer_presence": "已提供" if wrong_answer else "未提供",
            "extracted_work": wrong_answer,
            "answer_status": "已对照母题检索" if wrong_answer else "未提供作答",
            "likely_issue": "与母题库同类题比对中，请逐步核对断点。" if wrong_answer else "建议补充手写作答后粉碎错因。",
            "error_type": "方法/执行待核对",
            "evidence": [f"母题匹配 {round(score, 1)} 分：{core}"],
            "next_action": "进入粉碎步骤，逐步核对；再做巩固题消灭此题。",
        },
        "decomposition": {
            "total_formula": "识题型 → 提取条件 → 套模型 → 分步计算 → 检验结论",
            "step_formulas": [
                {"name": "识别信号", "formula": core, "operation": "先判断题型入口", "student_trap": "题型误判"},
                {"name": "母题对照", "formula": stem[:240], "operation": "对照标准路径", "student_trap": "跳步"},
                {"name": "错因粉碎", "formula": wrong_answer[:180] if wrong_answer else "补作答", "operation": "逐步找断点", "student_trap": "未验算"},
            ],
        },
        "learning_strategy": {
            "decomposition_answer": "先锁定母题模型，再逐步粉碎错因，最后用变式题消灭。",
            "make_it_easier": "把此题降阶为母题库中的原型题再迁移。",
            "entry_point": core,
            "cognitive_ladder": ["识别题型", "对照母题", "粉碎错因", "消灭巩固"],
            "micro_drills": ["用一句话说题型", "写出第一步公式"],
            "teacher_hint": "这道题与哪道高考真题最像？",
        },
        "practice_variants": [],
        "gaokao_rag": {
            "used": bool(rag_hits),
            "evidence_count": len(rag_hits or []),
            "mode": "search_fast_path",
            "top_score": score,
        },
        "mother_question_reserved": {
            "name": core,
            "abstract_pattern": stem[:300],
            "recognition_signals": [core, "母题库命中"],
            "status": "search_matched",
        },
        "poem": {
            "title": "消灭路线图",
            "lines": ["先识题型不慌张", "对照母题找方向", "粉碎错因逐步量", "巩固三道消灭光"],
            "line_reviews": [],
        },
    }
