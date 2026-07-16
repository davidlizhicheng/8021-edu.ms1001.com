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
    {"code":"M-MATH-DERIV-02","subject":"数学","name":"导数恒成立与参数范围","keywords":["导数","恒成立","参数","不等式恒成立","分离参数"],"formula":"转化恒成立→构造函数→求导判单调→求最值→回代参数","reminders":["端点/开闭区间","分类讨论要完整"],"source":"高考题型模型"},
    {"code":"M-MATH-DERIV-03","subject":"数学","name":"导数零点与方程根","keywords":["导数","零点","方程","根","图像"],"formula":"求导→判单调与极值→结合图像/中间值→确定根个数","reminders":["极值符号判断","注意定义域"],"source":"高考题型模型"},
    {"code":"M-MATH-FUNC-01","subject":"数学","name":"函数奇偶性与对称性","keywords":["奇函数","偶函数","对称","f(-x)"],"formula":"验定义域→算 f(-x)→与 f(x)/-f(x) 比较→下结论","reminders":["定义域关于原点对称","先判奇偶再化简"],"source":"高考题型模型"},
    {"code":"M-MATH-FUNC-02","subject":"数学","name":"函数零点与方程转化","keywords":["函数零点","方程","图像交点","二分法"],"formula":"化为 f(x)=0→分析单调/极值→找符号变化区间→结论","reminders":["连续性与端点值","数形结合"],"source":"高考题型模型"},
    {"code":"M-MATH-FUNC-03","subject":"数学","name":"指数对数比大小","keywords":["指数","对数","比大小","同底","换底"],"formula":"同底比指数/真数→或化为同型→构造函数单调性→比较","reminders":["底数范围影响单调","定义域优先"],"source":"高考题型模型"},
    {"code":"M-MATH-LOGIC-01","subject":"数学","name":"充分必要与条件判断","keywords":["充分","必要","充要","条件","命题"],"formula":"判 p→q 与 q→p→举反例/推导→选关系","reminders":["充分必要别搞反","小推大是充分"],"source":"高考题型模型"},
    {"code":"M-MATH-SEQ-01","subject":"数学","name":"裂项相消与求和","keywords":["裂项","相消","求和","数列","通项"],"formula":"识别通项结构→裂项→写前n项和→消去中间项","reminders":["首尾保留项数","下标别错位"],"source":"高考题型模型"},
    {"code":"M-MATH-SEQ-02","subject":"数学","name":"递推数列求通项","keywords":["递推","通项","构造","等比","等差"],"formula":"写前几项→猜类型→构造辅助数列→求通项→验初值","reminders":["初值单独验证","构造要有依据"],"source":"高考题型模型"},
    {"code":"M-MATH-TRIG-01","subject":"数学","name":"三角恒等变换","keywords":["三角","恒等","sin","cos","tan","公式"],"formula":"识别角关系→选公式→化简→回到设问","reminders":["角倍半关系","符号象限"],"source":"高考题型模型"},
    {"code":"M-MATH-VEC-01","subject":"数学","name":"平面向量数量积","keywords":["向量","数量积","夹角","投影","垂直"],"formula":"选基底/坐标→表示向量→算点积/模→几何意义解释","reminders":["垂直⇔点积为0","夹角取锐角还是钝角"],"source":"高考题型模型"},
    {"code":"M-MATH-INEQ-01","subject":"数学","name":"基本不等式求最值","keywords":["基本不等式","均值","最值","一正二定三相等"],"formula":"验证一正→凑定值→应用不等式→验等号条件","reminders":["等号能否取到","别忘正数条件"],"source":"高考题型模型"},
    {"code":"M-MATH-COUNT-01","subject":"数学","name":"排列组合计数","keywords":["排列","组合","计数","分步","分类"],"formula":"判分步/分类→选公式→计算→回实际语境","reminders":["有序用排列","重复/顺序无关用组合"],"source":"高考题型模型"},
    {"code":"M-MATH-GEO-01","subject":"数学","name":"解析几何定点定值","keywords":["椭圆","双曲线","抛物线","直线","定点","定值"],"formula":"建系/识别曲线→设点设线→联立韦达→目标代数化→消元验证","reminders":["避免过早求根","检查判别式与斜率不存在情形"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-MATH-SOLID-01","subject":"数学","name":"立体几何线面关系","keywords":["立体几何","线面","二面角","法向量","空间向量"],"formula":"证垂直/平行→建立坐标系→写向量→求法向量→计算并核对锐钝角","reminders":["建系依据要写清","法向量不唯一但夹角符号需判断"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-MATH-PROB-01","subject":"数学","name":"概率统计决策","keywords":["概率","分布列","期望","方差","统计"],"formula":"定义随机变量→列事件与概率→检查概率和→求期望/方差→解释实际意义","reminders":["事件互斥性","概率和必须为1"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-PHY-MECH-01","subject":"物理","name":"多过程动力学","keywords":["牛顿","加速度","摩擦","动量","机械能"],"formula":"划分过程→选对象→受力图→列动力学/能量方程→连接临界状态","reminders":["每段过程重新受力分析","正方向保持一致"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-CHEM-EQ-01","subject":"化学","name":"化学平衡综合","keywords":["化学平衡","平衡常数","转化率","勒夏特列"],"formula":"写反应→列三段式→代入K→判断移动→解释宏观现象","reminders":["浓度与物质的量勿混用","温度改变才改变平衡常数"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-ENG-READ-01","subject":"英语","name":"阅读理解证据定位","keywords":["阅读","主旨","推断","细节","作者态度"],"formula":"识别题型→定位原文→同义改写比对→排除过度推断→回文验证","reminders":["答案必须有文本证据","区分作者观点与他人观点"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"M-CHN-READ-01","subject":"语文","name":"现代文阅读作用题","keywords":["作用","赏析","现代文","人物形象","表达效果"],"formula":"内容概括→结构位置→手法效果→主旨/人物→结合文本证据","reminders":["术语后必须跟文本分析","分点对应分值"],"source":"高考题型模型（待绑定授权真题）"},
    {"code":"SZ-MATH-FUNC-01","subject":"数学","name":"深圳中考函数综合","keywords":["一次函数","二次函数","反比例函数","图象","交点"],"formula":"识别变量→确定解析式→读图取点→联立/分类→回到实际意义","reminders":["自变量范围不能漏","数形结论要互相验证"],"source":"义务教育数学课程标准（2022年版）题型模型"},
    {"code":"SZ-MATH-GEO-01","subject":"数学","name":"深圳中考几何证明与计算","keywords":["三角形","圆","相似","全等","证明"],"formula":"标条件→找基本图形→选定理→写推理链→计算并检验","reminders":["每一步写依据","辅助线必须说明目的"],"source":"义务教育数学课程标准（2022年版）题型模型"},
    {"code":"SZ-MATH-EQ-01","subject":"数学","name":"深圳中考方程与不等式","keywords":["方程","不等式","根","解集","应用题"],"formula":"设未知量→建立数量关系→求解→检验→回答实际问题","reminders":["分式方程必须验根","不等号变向要标记"],"source":"义务教育数学课程标准（2022年版）题型模型"},
    {"code":"SZ-MATH-STAT-01","subject":"数学","name":"深圳中考统计与概率","keywords":["统计","概率","频数","平均数","抽样"],"formula":"明确总体样本→整理数据→选统计量→计算→解释结论","reminders":["随机抽样才具代表性","用数据回答题目语境"],"source":"义务教育数学课程标准（2022年版）题型模型"},
    {"code":"SZ-ENG-READ-01","subject":"英语","name":"深圳中考英语阅读证据链","keywords":["阅读理解","main idea","infer","detail","attitude"],"formula":"判题型→圈关键词→定位段落→同义替换→排除过度推断","reminders":["每个答案都回指原文","推断不能超出文本"],"source":"义务教育英语课程标准（2022年版）题型模型"},
    {"code":"SZ-ENG-CLOZE-01","subject":"英语","name":"深圳中考完形填空","keywords":["完形填空","cloze","语境","搭配","上下文"],"formula":"通读主旨→判词性→看近句搭配→看远句逻辑→回读全文","reminders":["先语境后语法","代词指代要回看"],"source":"义务教育英语课程标准（2022年版）题型模型"},
    {"code":"SZ-ENG-GRAMMAR-01","subject":"英语","name":"深圳中考语法填空","keywords":["语法填空","时态","非谓语","从句","词形变化"],"formula":"判句子成分→判词性→找时态语态→处理固定搭配→通读检查","reminders":["有提示词先做词形变化","无提示词优先虚词"],"source":"义务教育英语课程标准（2022年版）题型模型"},
    {"code":"SZ-ENG-WRITE-01","subject":"英语","name":"深圳中考英语书面表达","keywords":["书面表达","作文","writing","email","倡议"],"formula":"审体裁人称时态→列要点→搭结构→句式升级→拼写语法复核","reminders":["覆盖全部要点","复杂句以准确为先"],"source":"义务教育英语课程标准（2022年版）题型模型"},
    {"code":"M-MATH-COMPLEX-01","subject":"数学","name":"复数运算与几何意义","keywords":["复数","虚数","共轭","模","辐角"],"formula":"化为 a+bi→选代数/三角形式→运算→回几何解释","reminders":["分母实数化","注意象限与辐角主值"],"source":"高考题型模型"},
    {"code":"M-MATH-STAT-02","subject":"数学","name":"回归分析与独立性检验","keywords":["回归","相关系数","卡方","独立性","残差"],"formula":"整理数据→算 r/方程→检验→解释实际意义","reminders":["区分相关与因果","注意样本量"],"source":"高考题型模型"},
    {"code":"M-PHY-ELEC-01","subject":"物理","name":"电路动态分析","keywords":["电路","电阻","电压","电流","滑动变阻器"],"formula":"识别结构→局部变化→判断总阻→推导 I/U→验证极值","reminders":["先总后分","注意电表内外接"],"source":"高考题型模型（待绑定授权真题）"},
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
