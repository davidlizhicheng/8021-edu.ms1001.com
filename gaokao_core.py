"""高考垂直能力：母题检索、八步知识卡与辨识训练。

本模块只保存题型模型和来源元数据；未经授权的真题正文不内置。
"""

from __future__ import annotations

import re
from typing import Iterable


GAOKAO_CARD_STEPS = (
    ("answer_trace", "作答还原"),
    ("error_cause", "易错原因"),
    ("correction_path", "纠错思路"),
    ("standard_solution", "规范解答与评分点"),
    ("formula_model", "解题公式与模型"),
    ("key_reminders", "关键提醒"),
    ("discrimination_training", "辨识训练"),
    ("self_review", "自我复盘"),
)


SEED_MOTHER_QUESTIONS = (
    {"code":"M-MATH-DERIV-01","subject":"数学","name":"导数单调性与极值","keywords":["导数","单调","极值","切线"],"formula":"求定义域→求导→找临界点→列表判号→回答设问","reminders":["先写定义域","临界点必须回代区间","结论要对应设问"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-MATH-GEO-01","subject":"数学","name":"解析几何定点定值","keywords":["椭圆","双曲线","抛物线","直线","定点","定值"],"formula":"建系/识别曲线→设点设线→联立韦达→目标代数化→消元验证","reminders":["避免过早求根","检查判别式与斜率不存在情形"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-MATH-SOLID-01","subject":"数学","name":"立体几何线面关系","keywords":["立体几何","线面","二面角","法向量","空间向量"],"formula":"证垂直/平行→建立坐标系→写向量→求法向量→计算并核对锐钝角","reminders":["建系依据要写清","法向量不唯一但夹角符号需判断"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-MATH-PROB-01","subject":"数学","name":"概率统计决策","keywords":["概率","分布列","期望","方差","统计"],"formula":"定义随机变量→列事件与概率→检查概率和→求期望/方差→解释实际意义","reminders":["事件互斥性","概率和必须为1"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-PHY-MECH-01","subject":"物理","name":"多过程动力学","keywords":["牛顿","加速度","摩擦","动量","机械能"],"formula":"划分过程→选对象→受力图→列动力学/能量方程→连接临界状态","reminders":["每段过程重新受力分析","正方向保持一致"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-CHEM-EQ-01","subject":"化学","name":"化学平衡综合","keywords":["化学平衡","平衡常数","转化率","勒夏特列"],"formula":"写反应→列三段式→代入K→判断移动→解释宏观现象","reminders":["浓度与物质的量勿混用","温度改变才改变平衡常数"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-ENG-READ-01","subject":"英语","name":"阅读理解证据定位","keywords":["阅读","主旨","推断","细节","作者态度"],"formula":"识别题型→定位原文→同义改写比对→排除过度推断→回文验证","reminders":["答案必须有文本证据","区分作者观点与他人观点"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-CHN-READ-01","subject":"语文","name":"现代文阅读作用题","keywords":["作用","赏析","现代文","人物形象","表达效果"],"formula":"内容概括→结构位置→手法效果→主旨/人物→结合文本证据","reminders":["术语后必须跟文本分析","分点对应分值"],"source":"高考题型模型（待绑定授权真题）"},
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", str(text or "").lower()))


def match_mother_question(question: str, subject: str = "", catalog: Iterable[dict] = SEED_MOTHER_QUESTIONS) -> dict | None:
    haystack = str(question or "").lower()
    subject = str(subject or "")
    best, best_score = None, 0
    for item in catalog:
        score = sum(3 for kw in item.get("keywords", []) if str(kw).lower() in haystack)
        if subject and item.get("subject") and item["subject"] in subject:
            score += 2
        if score > best_score:
            best, best_score = item, score
    if not best or best_score < 2:
        return None
    return {**best, "match_score": best_score, "match_basis": [kw for kw in best.get("keywords", []) if kw.lower() in haystack]}


def build_memory_poem(mother: dict | None, diagnosis: dict | None = None) -> dict:
    """生成可复述、可解码的题后记忆诗，不以押韵牺牲解题准确性。"""
    mother, diagnosis = mother or {}, diagnosis or {}
    name = mother.get("name") or diagnosis.get("core_pattern") or "本题模型"
    signals = "、".join((mother.get("match_basis") or mother.get("keywords") or [])[:3]) or "题干信号"
    formula = mother.get("formula") or (diagnosis.get("decomposition") or {}).get("total_formula") or "读题→取条件→建模→求解→校验"
    reminders = "；".join((mother.get("reminders") or [])[:2]) or "条件、步骤、结论都要检查"
    lines = [
        f"题里看见{signals}，先把{str(name)[:10]}想；",
        "设问倒推缺什么，已知条件排成行；",
        f"路径记作：{formula}；",
        "一步一据写清楚，评分要点莫隐藏；",
        f"回头细查：{reminders}；",
        "换题若逢同信号，照着模型再开场。",
    ]
    meanings = [
        "辨识信号并调用母题", "从设问反推条件", "记忆非数学公式的解题流程",
        "规范表达并对应评分点", "检查本题高频错误", "完成同类题迁移",
    ]
    return {
        "title": f"《{name}记忆诗》",
        "lines": lines,
        "line_reviews": [{"line": line, "model_hint": hint} for line, hint in zip(lines, meanings)],
        "formula_path": formula,
        "mother_code": mother.get("code"),
        "purpose": "通俗记忆；诗句不能替代规范解答与正式评分标准",
    }


def build_gaokao_card(question: dict, diagnosis: dict, mother: dict | None = None) -> dict:
    analysis = diagnosis.get("student_answer_analysis") or {}
    strategy = diagnosis.get("learning_strategy") or {}
    standard = diagnosis.get("standard_answer") or {}
    decomposition = diagnosis.get("decomposition") or {}
    mother = mother or {}
    scoring = diagnosis.get("scoring_points") or standard.get("scoring_points") or []
    practice = diagnosis.get("practice_variants") or []
    contents = {
        "answer_trace": analysis.get("extracted_work") or question.get("student_work") or "未检测到有效作答，需补充或人工确认。",
        "error_cause": analysis.get("likely_issue") or "需结合笔迹、得分和教师批注复核。",
        "correction_path": strategy.get("entry_point") or strategy.get("decomposition_answer") or "从设问倒推所需条件，再选择对应模型。",
        "standard_solution": {"solution": standard.get("concise_solution") or "待完善规范解答", "final_answer": standard.get("final_answer") or "待复核", "scoring_points": scoring},
        "formula_model": {"mother_code": mother.get("code"), "mother_name": mother.get("name") or diagnosis.get("core_pattern") or "待归类", "formula": mother.get("formula") or decomposition.get("total_formula") or "读题→建模→求解→校验"},
        "key_reminders": mother.get("reminders") or [strategy.get("make_it_easier") or "检查条件、步骤、单位和结论完整性"],
        "discrimination_training": practice[:3] if practice else [{"title":"同型辨识","instruction":"判断本题应使用哪个母题模型，并说明触发特征。","source":"题型训练模板；正式真题需绑定来源"}],
        "self_review": ["我最初在哪一步偏离？", "下次看到哪些特征应调用本模型？", "我能否不看答案复述评分点并完成一道同型题？"],
    }
    return {
        "version": "gaokao-card-v1",
        "mother_match": mother or None,
        "steps": [{"number": i, "key": key, "label": label, "content": contents[key]} for i, (key, label) in enumerate(GAOKAO_CARD_STEPS, 1)],
        "evidence_status": "matched" if mother else "review_required",
        "memory_poem": build_memory_poem(mother, diagnosis),
    }
