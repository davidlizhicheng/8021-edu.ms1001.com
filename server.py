from __future__ import annotations

import env_local  # noqa: F401 â€” åŠ è½½ .env / .env.local
import aippt_auth
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import export_utils
import institution_store as org_inst_store
from learning_workflow import normalize_error_type, practice_tier, transition
from paper_workflow import normalize_answer_state, normalize_eight_steps, paper_summary, split_numbered_questions
from gaokao_core import SEED_MOTHER_QUESTIONS, build_gaokao_card, match_mother_question


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = PUBLIC_DIR / "uploads"
CARD_DIR = PUBLIC_DIR / "cards"
EXPORT_DIR = PUBLIC_DIR / "exports"
DB_PATH = DATA_DIR / "gaokao.db"

MINIMAX_ENDPOINT = "https://api.minimax.chat/v1/chat/completions"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
OPENAI_IMAGE_ENDPOINT = "https://api.openai.com/v1/images/generations"
FENNO_BASE_URL = os.environ.get("FENNO_BASE_URL", "https://api.fenno.ai")
DEFAULT_OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5")
DEFAULT_OPENAI_IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1536")
DEFAULT_OPENAI_IMAGE_QUALITY = os.environ.get("OPENAI_IMAGE_QUALITY", "high")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@edu.ms1001.com").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "GaoKao2026-edu-ms1001-admin").strip()
PASS_REQUIRED_CORRECT = 2
AUTH_BASE_URL = os.environ.get("AUTH_BASE_URL", "https://ai.ms1001.com").strip().rstrip("/")
PUBLIC_AUTH_BASE_URL = os.environ.get("PUBLIC_AUTH_BASE_URL", AUTH_BASE_URL or "https://ai.ms1001.com").strip().rstrip("/")
USE_UNIFIED_AUTH = os.environ.get("USE_UNIFIED_AUTH", "1").strip().lower() not in {"0", "false", "no", "off"}
UNIFIED_PLATFORM_ID = os.environ.get("UNIFIED_PLATFORM_ID", "edu.ms1001.com").strip()


PORTAL_TOOLS = [
    {"id": "wrong-transfer", "number": "01", "label": "é”™é¢˜æ‹†è§£æ ¸å¿ƒ", "tagline": "æ ¸å¿ƒé—­çŽ¯ Â· å½’å› æ‹†é¢˜ã€å˜å¼è®­ç»ƒã€è¿‡å…³ç§»é™¤", "category": "é”™é¢˜çªç ´", "route": "diagnose", "mode": "wrong", "delivery": "diagnose", "featured": True},
    {"id": "paper-analysis", "number": "02", "label": "å·é¢å­¦æƒ…åˆ†æž", "tagline": "ä¸Šä¼ è¯•å·ç”Ÿæˆè¯Šæ–­æŠ¥å‘Šä¸Ž Word", "category": "å­¦æƒ…è¯Šæ–­", "route": "tool", "mode": "analysis", "delivery": "report"},
    {"id": "paper-variant", "number": "03", "label": "è¯•é¢˜å˜å¼ç”Ÿæˆ", "tagline": "ç”Ÿæˆå¯æ‰“å°å˜å¼å· Word", "category": "å‘½é¢˜è®­ç»ƒ", "route": "tool", "mode": "variant", "delivery": "docx"},
    {"id": "ai-paper", "number": "04", "label": "æ™ºèƒ½æ‰¹é‡å‘½é¢˜", "tagline": "åˆ†å±‚å‘½é¢˜å¹¶å¯¼å‡º Word å·", "category": "å‘½é¢˜è®­ç»ƒ", "route": "tool", "mode": "question", "delivery": "docx"},
    {"id": "paper-word", "number": "05", "label": "è¯•é¢˜æ–‡æ¡£æ•´ç†", "tagline": "å¯¼å‡º Word / Markdown æ–‡æ¡£", "category": "æ–‡æ¡£æ•´ç†", "route": "tool", "mode": "document", "delivery": "docx"},
    {"id": "image-teacher", "number": "06", "label": "æ•™æ¡ˆé…å›¾ç”Ÿæˆ", "tagline": "ç›´æŽ¥ç”Ÿæˆæ•™å­¦é…å›¾ PNG", "category": "é…å›¾ç”Ÿæˆ", "route": "tool", "mode": "image", "delivery": "image"},
    {"id": "ppt-review", "number": "07", "label": "è®²è¯„è¯¾ä»¶ç”Ÿæˆ", "tagline": "å¯¼å‡ºå¯ç¼–è¾‘ PowerPoint è¯¾ä»¶", "category": "è¯¾ä»¶è¾…åŠ©", "route": "tool", "mode": "ppt", "delivery": "pptx"},
    {"id": "aippt-online3", "number": "08", "label": "åœ¨çº¿ç”Ÿæˆ3ï¼ˆæµ‹è¯•ï¼‰", "tagline": "AiPPT é¢„è£…ç‰ˆ iframe Â· PC åœ¨çº¿ç”Ÿæˆè¯¾ä»¶", "category": "è¯¾ä»¶è¾…åŠ©", "route": "aippt", "mode": "aippt", "delivery": "iframe"},
    {"id": "review-skill", "number": "09", "label": "è¯»é¢˜ç ´é¢˜è®­ç»ƒ", "tagline": "å®¡é¢˜è®­ç»ƒæ–¹æ¡ˆ Word å¯¼å‡º", "category": "å®¡é¢˜è®­ç»ƒ", "route": "tool", "mode": "review", "delivery": "docx"},
    {"id": "big-question", "number": "10", "label": "ä¸»è§‚é¢˜é‡‡åˆ†æ‹†è§£", "tagline": "é‡‡åˆ†ç‚¹æ‹†è§£ Word å¯¼å‡º", "category": "è§£é¢˜æ‹†è§£", "route": "tool", "mode": "decompose", "delivery": "docx"},
    {"id": "word-paper", "number": "11", "label": "è¯æ±‡ç»ƒä¹ ç»„å·", "tagline": "è¯æ±‡å· Word å¯¼å‡º", "category": "è¯­è¨€è®­ç»ƒ", "route": "tool", "mode": "english", "delivery": "docx"},
    {"id": "coverage-check", "number": "12", "label": "å¤‡è€ƒè¦†ç›–æ‰«æ", "tagline": "è€ƒç‚¹è¦†ç›–æŠ¥å‘Š Word å¯¼å‡º", "category": "å¤‡è€ƒè§„åˆ’", "route": "tool", "mode": "coverage", "delivery": "docx"},
    {"id": "sprint-plan", "number": "13", "label": "ä¸´è€ƒå†²åˆºè§„åˆ’", "tagline": "å†²åˆºæ–¹æ¡ˆ Word å¯¼å‡º", "category": "å¤‡è€ƒè§„åˆ’", "route": "tool", "mode": "plan", "delivery": "docx"},
    {"id": "class-notes", "number": "14", "label": "æŽˆè¯¾çºªè¦æ•´ç†", "tagline": "è¯¾å ‚ç¬”è®° Word å¯¼å‡º", "category": "è¯¾ä»¶è¾…åŠ©", "route": "tool", "mode": "notes", "delivery": "docx"},
    {"id": "preview-sheet", "number": "15", "label": "è¯¾å‰é¢„ä¹ åŠ©æ‰‹", "tagline": "é¢„ä¹ å• Word å¯¼å‡º", "category": "é¢„ä¹ è¾…åŠ©", "route": "tool", "mode": "preview", "delivery": "docx"},
    {"id": "loss-analysis", "number": "16", "label": "å¤±åˆ†åŽŸå› è¯Šæ–­", "tagline": "å¤±åˆ†è¯Šæ–­æŠ¥å‘Š Word å¯¼å‡º", "category": "å­¦æƒ…è¯Šæ–­", "route": "tool", "mode": "loss", "delivery": "docx"},
    {"id": "question-sense", "number": "17", "label": "é¢˜åž‹ç›´è§‰ç»ƒä¹ ", "tagline": "é¢˜æ„Ÿè®­ç»ƒ Word å¯¼å‡º", "category": "å®¡é¢˜è®­ç»ƒ", "route": "tool", "mode": "sense", "delivery": "docx"},
    {"id": "knowledge-map", "number": "18", "label": "çŸ¥è¯†å›¾è°±ç»˜åˆ¶", "tagline": "å¯¼å‡º HTML å›¾è°±ä¸Žé…å›¾ PNG", "category": "é…å›¾ç”Ÿæˆ", "route": "tool", "mode": "map", "delivery": "map"},
    {"id": "ten-solutions", "number": "19", "label": "å¤šè·¯å¾„è§£æ³•æŽ¢ç´¢", "tagline": "å¤šè§£æ³•æ–¹æ¡ˆ Word å¯¼å‡º", "category": "è§£é¢˜æ‹†è§£", "route": "tool", "mode": "multi", "delivery": "docx"},
    {"id": "knowledge-explain", "number": "20", "label": "æ¦‚å¿µç²¾è®²åŠ©æ‰‹", "tagline": "è®²è§£ç¨¿ Word å¯¼å‡º", "category": "æ¦‚å¿µè®²è§£", "route": "tool", "mode": "explain", "delivery": "docx"},
    {"id": "essay-polish", "number": "21", "label": "è¡¨è¾¾æ¶¦è‰²æ•™ç»ƒ", "tagline": "æ¶¦è‰²ç¨¿ Word å¯¼å‡º", "category": "è¯­è¨€è®­ç»ƒ", "route": "tool", "mode": "writing", "delivery": "docx"},
    {"id": "score-action", "number": "22", "label": "æåˆ†è¡ŒåŠ¨è·¯çº¿å›¾", "tagline": "è¡ŒåŠ¨æ–¹æ¡ˆ Word å¯¼å‡º", "category": "å¤‡è€ƒè§„åˆ’", "route": "tool", "mode": "score", "delivery": "docx"},
]

# 历史版本曾以错误编码写入中文常量。这里使用规范中文作为唯一线上工具目录，
# 保持既有 id/mode/route，避免只在前端掩盖乱码。
_TOOL_ZH = {
    "wrong-transfer": ("错题八步拆解", "作答还原、错因诊断、母题模型与巩固过关", "错题突破"),
    "paper-analysis": ("全卷学情分析", "上传试卷生成逐题诊断与分析报告", "学情诊断"),
    "paper-variant": ("试卷变式机", "基于原卷生成同型变式训练卷", "命题训练"),
    "ai-paper": ("AI分层出题", "按知识点、难度和题量智能命题", "命题训练"),
    "paper-word": ("题卷重排Word", "整理题卷并导出可编辑Word", "文档整理"),
    "image-teacher": ("教学配图生成", "生成课堂、讲义和课件配图", "配图生成"),
    "ppt-review": ("试卷讲评课件", "生成可编辑的讲评PowerPoint", "课件辅助"),
    "aippt-online3": ("AI课件在线生成", "在线生成并编辑教学课件", "课件辅助"),
    "review-skill": ("审题破题训练", "训练题干识别、条件提取和切入点", "审题训练"),
    "big-question": ("主观题采分拆解", "按步骤拆出规范答案与评分点", "解题拆解"),
    "word-paper": ("英语词汇组卷", "生成词汇练习与答案Word", "语言训练"),
    "coverage-check": ("考点覆盖扫描", "检查试卷考点、难度与遗漏", "备考规划"),
    "sprint-plan": ("临考冲刺规划", "依据薄弱项生成冲刺计划", "备考规划"),
    "class-notes": ("课堂纪要整理", "把课堂材料整理为结构化笔记", "课件辅助"),
    "preview-sheet": ("课前预习助手", "生成目标、问题链和预习单", "预习辅助"),
    "loss-analysis": ("失分原因诊断", "归类知识、方法、计算与表达失分", "学情诊断"),
    "question-sense": ("题型直觉训练", "训练题型辨识和母题调用", "审题训练"),
    "knowledge-map": ("知识图谱绘制", "生成知识关系图谱与配图", "配图生成"),
    "ten-solutions": ("一题多解探索", "比较多种路径、条件与适用边界", "解题拆解"),
    "knowledge-explain": ("概念精讲助手", "生成例题、反例与通俗讲解", "概念讲解"),
    "essay-polish": ("表达润色教练", "改进作文表达并说明修改依据", "语言训练"),
    "score-action": ("提分行动路线图", "把学情诊断转成每日行动清单", "备考规划"),
}
PORTAL_TOOLS = [
    {**tool, "label": _TOOL_ZH[tool["id"]][0], "tagline": _TOOL_ZH[tool["id"]][1], "category": _TOOL_ZH[tool["id"]][2]}
    for tool in PORTAL_TOOLS
]


def get_portal_tool(tool_id: str) -> dict | None:
    return next((tool for tool in PORTAL_TOOLS if tool["id"] == tool_id), None)


OCR_PROMPT = """ä½ æ˜¯ä¸€ä¸ªä¸¥è°¨çš„ä¸­é«˜è€ƒå…¨ç§‘ OCR åŠ©æ‰‹ã€‚

ä»»åŠ¡ï¼šåªä»Žå›¾ç‰‡ä¸­è¯†åˆ«é¢˜ç›®æ–‡å­—ã€å…¬å¼ã€å›¾è¡¨ã€ææ–™ã€é€‰é¡¹ã€å­¦ç”Ÿæ‰‹å†™/æ‰¹æ³¨ä¿¡æ¯ï¼Œä¸è¦è§£é¢˜ã€‚

è¦æ±‚ï¼š
1. ä¿ç•™é¢˜å·ã€å·²çŸ¥æ¡ä»¶ã€æ±‚è§£ç›®æ ‡ã€‚
2. æ•°å­¦/ç‰©ç†/åŒ–å­¦å…¬å¼å°½é‡è½¬å†™æˆ LaTeX æˆ–æ¸…æ™°çº¯æ–‡æœ¬ã€‚
3. è¯­æ–‡/è‹±è¯­/æ”¿æ²»/åŽ†å²/åœ°ç†ç­‰ææ–™é¢˜è¦å®Œæ•´ä¿ç•™ææ–™ã€è®¾é—®å’Œé€‰é¡¹ã€‚
4. å¦‚æžœå›¾ç‰‡ä¸­æœ‰å­¦ç”Ÿç­”æ¡ˆã€çº¢å‰ã€åœˆç”»ã€è€å¸ˆæ‰¹æ³¨ï¼Œè¯·å•ç‹¬åˆ—å‡ºã€‚
5. æ— æ³•ç¡®å®šçš„å­—ç¬¦ç”¨ [?] æ ‡è®°ï¼Œä¸è¦ç¼–é€ ã€‚
6. è¾“å‡º JSONï¼Œä¸è¦è¾“å‡º Markdownã€‚

JSON æ ¼å¼ï¼š
{
  "ocr_text": "å®Œæ•´è¯†åˆ«æ–‡æœ¬",
  "printed_question": "å°åˆ·é¢˜å¹²",
  "student_work": "å­¦ç”Ÿä½œç­”æˆ–ç©ºå­—ç¬¦ä¸²",
  "teacher_marks": "æ‰¹æ”¹ç—•è¿¹æˆ–ç©ºå­—ç¬¦ä¸²",
  "uncertain_parts": ["ä¸ç¡®å®šå†…å®¹1"]
}
"""


DIAGNOSIS_PROMPT = """ä½ æ˜¯ä¸€ä¸ªä¸­é«˜è€ƒå…¨ç§‘æ‹†é¢˜æ•™ç»ƒï¼Œä¸æ˜¯æ‹ç…§æœç­”æ¡ˆå·¥å…·ã€‚

äº§å“ç›®æ ‡ï¼š
æŠŠä¸€é“é¢˜æ‹†å¾—éžå¸¸ç»†ï¼Œè®©å­¦ç”ŸçŸ¥é“â€œé¢˜ç›®å¦‚ä½•è¢«æ‹†å¼€ã€åº”è¯¥å¥—å“ªä¸ªç­”é¢˜/è§£é¢˜æ¨¡åž‹ã€æœ‰æ²¡æœ‰å¯¹åº”é¢˜åž‹åŽŸåž‹/æ¯é¢˜é›å½¢ã€è¿˜èƒ½æ€Žä¹ˆè§£ã€æœ€åŽç”¨æœ‰è¶£å°è¯—å¤ç›˜â€ã€‚

å½“å‰é˜¶æ®µè¯´æ˜Žï¼š
- æš‚æ—¶ä¸åš RAGã€‚
- æš‚æ—¶ä¸åšæ­£å¼æ¯é¢˜åº“æ£€ç´¢ã€‚
- æ•°ç†å­¦ç§‘å¯ä»¥è¾“å‡ºâ€œæ¯é¢˜é›å½¢/æ¯é¢˜å½’çº³â€ï¼›æ–‡ç§‘å’Œè¯­è¨€å­¦ç§‘è¾“å‡ºâ€œé¢˜åž‹åŽŸåž‹/ç­”é¢˜æ¨¡åž‹é›å½¢â€ã€‚
- è¯¥å­—æ®µå¿…é¡»æ ‡è®°ä¸º prompt_reservedï¼Œè¡¨ç¤ºåŽç»­ä¼šæŽ¥å…¥æ¯é¢˜/é¢˜åž‹æ¨¡åž‹æŽ¥å£ã€‚
- ä¸è¦å‡è£…æŸ¥åˆ°äº†é¢˜åº“ã€‚

å¿…é¡»ä½“çŽ°ä¸‰å¤§äº®ç‚¹ï¼š
1. æ‹†é¢˜ã€ç­”é¢˜/è§£é¢˜æ¨¡åž‹ã€é¢˜åž‹åŽŸåž‹/æ¯é¢˜é›å½¢ã€‚
2. ä¸€é¢˜å¤šè§£/å¤šè§†è§’ï¼šè‡³å°‘ç»™å‡º 2 ç§è§£æ³•ã€ç­”é¢˜è·¯å¾„æˆ–æ€è€ƒè§†è§’ï¼›å¦‚æžœé¢˜ç›®ä¸é€‚åˆå¤šè§£ï¼Œè¯´æ˜ŽåŽŸå› å¹¶ç»™å‡º 1 ä¸ªæ›¿ä»£è§†è§’ã€‚
3. è§£å®Œæ¥ç‚¹è¶£å‘³ï¼šç”¨ç”Ÿæ´»åŒ–æ¯”å–»æ‹†è§£å…¨è¿‡ç¨‹ï¼Œå¹¶å†™ä¸€é¦–å°è¯—/å£è¯€ï¼Œå†é€å¥å¤ç›˜ã€‚

ç§‘ç›®é€‚é…ï¼š
- æ•°å­¦ï¼šå¼ºè°ƒåˆ¤åž‹ã€æ‹†å…¬å¼ã€è§£é¢˜æ¨¡åž‹ã€æ¯é¢˜é›å½¢ã€ä¸€é¢˜å¤šè§£ã€‚
- ç‰©ç†/åŒ–å­¦ï¼šå¼ºè°ƒæƒ…å¢ƒå»ºæ¨¡ã€å·²çŸ¥é‡/æœªçŸ¥é‡ã€å…¬å¼é€‰æ‹©ã€å®žéªŒ/å®ˆæ’/ååº”æ¨¡åž‹ã€‚
- è¯­æ–‡ï¼šå¼ºè°ƒææ–™æ‹†è¯»ã€è®¾é—®ç±»åž‹ã€ç­”é¢˜æ¨¡æ¿ã€é‡‡åˆ†ç‚¹ã€è¯­è¨€ç»„ç»‡ã€‚
- è‹±è¯­ï¼šå¼ºè°ƒé¢˜åž‹ã€å®šä½å¥ã€è¯­æ³•/è¯­ä¹‰çº¿ç´¢ã€é€‰é¡¹æŽ’é™¤ã€è¡¨è¾¾æ¨¡æ¿ã€‚
- æ”¿å²åœ°ç”Ÿï¼šå¼ºè°ƒææ–™ä¿¡æ¯ã€æ¦‚å¿µè°ƒç”¨ã€å› æžœé“¾ã€ç­”é¢˜è§’åº¦å’Œè§„èŒƒè¡¨è¿°ã€‚

è¾“å‡ºå¿…é¡»æ˜¯åˆæ³• JSONï¼Œä¸è¦ Markdownï¼Œä¸è¦ä»£ç å—ï¼Œä¸è¦é¢å¤–è§£é‡Šã€‚

JSON æ ¼å¼ï¼š
{
  "cleaned_question": "ä¿®æ­£åŽçš„é¢˜å¹²",
  "subject": "è¯†åˆ«æˆ–ç”¨æˆ·æŒ‡å®šçš„å­¦ç§‘",
  "topic": "ä¸“é¢˜åç§°",
  "difficulty": 1,
  "confidence": 0.85,
  "core_pattern": "æ ‡å‡†é¢˜åž‹/æ¯é¢˜é›å½¢/ç­”é¢˜æ¨¡åž‹åç§°",
  "knowledge_points": ["çŸ¥è¯†ç‚¹1"],
  "problem_goal": "è¿™é¢˜æœ€ç»ˆè¦æ±‚ä»€ä¹ˆ",
  "student_answer_analysis": {
    "answer_presence": "æœªæä¾›/åªç»™ç»“è®º/æœ‰è¿‡ç¨‹/æœ‰æ‰¹æ”¹ç—•è¿¹",
    "extracted_work": "ä»Žå­¦ç”Ÿä½œç­”æˆ–æ‰¹æ³¨ä¸­æ•´ç†å‡ºçš„å…³é”®ä½œç­”å†…å®¹",
    "answer_status": "ç©ºç™½ä¸ä¼š/æ€è·¯å¡ä½/æ­¥éª¤é”™è¯¯/è®¡ç®—é”™è¯¯/æ¦‚å¿µè¯¯ç”¨/è¡¨è¾¾ä¸è§„èŒƒ/åŸºæœ¬æ­£ç¡®ä½†ä¸å®Œæ•´",
    "likely_issue": "æœ€å¯èƒ½çš„é—®é¢˜è¯Šæ–­",
    "evidence": ["ä¾æ®1", "ä¾æ®2"],
    "next_action": "ä¸‹ä¸€æ­¥æœ€åº”è¯¥è¡¥çš„åŠ¨ä½œ"
  },
  "learning_strategy": {
    "decomposition_answer": "ç›´æŽ¥å›žç­”ï¼šè¿™é“é¢˜åˆ°åº•æ€Žä¹ˆæ‹†è§£ï¼ŒæŒ‰ä»€ä¹ˆé¡ºåºæ‹†",
    "make_it_easier": "ç›´æŽ¥å›žç­”ï¼šç”¨ä»€ä¹ˆæ–¹æ³•å¯ä»¥è®©è¿™é¢˜æ›´å®¹æ˜“å­¦",
    "entry_point": "å­¦ç”Ÿç¬¬ä¸€çœ¼åº”è¯¥å…ˆæŠ“å“ªä¸ªå…¥å£",
    "cognitive_ladder": ["å…ˆä¼šä»€ä¹ˆ", "å†ä¼šä»€ä¹ˆ", "æœ€åŽè¿ç§»ä»€ä¹ˆ"],
    "micro_drills": ["1åˆ†é’Ÿå°ç»ƒä¹ 1", "1åˆ†é’Ÿå°ç»ƒä¹ 2"],
    "teacher_hint": "è€å¸ˆ/äº§å“å¼•å¯¼å­¦ç”Ÿæ—¶æœ€è¯¥é—®çš„ä¸€å¥è¯"
  },
  "decomposition": {
    "total_formula": "è¯†åˆ«é¢˜åž‹â†’æ‹†æ¡ä»¶â†’é€‰æ¨¡åž‹â†’è®¡ç®—â†’éªŒè¯â†’æ€»ç»“",
    "step_formulas": [
      {
        "name": "åˆ¤åž‹å…¬å¼",
        "formula": "çœ‹åˆ°...â†’åˆ¤å®šä¸º...",
        "operation": "è¿™ä¸€æ­¥å…·ä½“åšä»€ä¹ˆ",
        "student_trap": "å­¦ç”Ÿå®¹æ˜“é”™åœ¨å“ªé‡Œ"
      }
    ]
  },
  "fun_analogy": {
    "theme": "ç”Ÿæ´»åŒ–æ¯”å–»ä¸»é¢˜ï¼Œä¾‹å¦‚æ‹†å¿«é€’/é€ æˆ¿å­/ç ´æ¡ˆ/åšèœ",
    "overview": "ä¸€å¥è¯è¯´æ˜Žè¿™ä¸ªæ¯”å–»å¦‚ä½•å¯¹åº”é¢˜ç›®",
    "steps": [
      {
        "step": "æ­¥éª¤å",
        "analogy": "æœ‰è¶£æ¯”å–»",
        "math_action": "å¯¹åº”æ•°å­¦åŠ¨ä½œ"
      }
    ]
  },
  "solution_models": [
    {
      "model_name": "æ ‡å‡†åŒ–é€šç”¨è§£é¢˜/ç­”é¢˜æ¨¡åž‹åç§°",
      "applies_when": "é€‚ç”¨æ¡ä»¶",
      "steps": ["æ­¥éª¤1", "æ­¥éª¤2"],
      "checkpoints": ["æ£€æŸ¥ç‚¹1"],
      "common_mistakes": ["å¸¸è§é”™è¯¯1"]
    }
  ],
  "mother_question_reserved": {
    "status": "prompt_reserved",
    "name": "æ¯é¢˜é›å½¢/é¢˜åž‹åŽŸåž‹åç§°",
    "abstract_pattern": "åŽ»æŽ‰æ•°å­—ã€ææ–™èƒŒæ™¯åŽçš„æŠ½è±¡é¢˜åž‹æˆ–ç­”é¢˜æ¨¡åž‹",
    "recognition_signals": ["è¯†åˆ«ä¿¡å·1"],
    "future_interface_hint": "åŽç»­å¯æŽ¥å…¥ /api/mother-questions åšæ­£å¼æ²‰æ·€"
  },
  "multiple_solutions": [
    {
      "method_name": "æ–¹æ³•ä¸€åç§°",
      "idea": "æ ¸å¿ƒæ€è·¯",
      "steps": ["æ­¥éª¤1", "æ­¥éª¤2"],
      "pros_cons": "ä¼˜ç¼ºç‚¹"
    },
    {
      "method_name": "æ–¹æ³•äºŒåç§°",
      "idea": "æ ¸å¿ƒæ€è·¯",
      "steps": ["æ­¥éª¤1", "æ­¥éª¤2"],
      "pros_cons": "ä¼˜ç¼ºç‚¹"
    }
  ],
  "standard_answer": {
    "final_answer": "æœ€ç»ˆç­”æ¡ˆ",
    "concise_solution": "æ ‡å‡†ç®€æ´è§£ç­”"
  },
  "poem": {
    "title": "å°è¯—æ ‡é¢˜",
    "lines": ["è¯—å¥1", "è¯—å¥2", "è¯—å¥3"],
    "line_reviews": [
      {
        "line": "è¯—å¥1",
        "review": "è¿™å¥å¯¹åº”å“ªä¸€æ­¥è§£é¢˜æ“ä½œ"
      }
    ]
  },
  "practice_variants": [
    {
      "level": 1,
      "title": "åŒç»“æž„å·©å›º",
      "stem": "å˜å¼é¢˜é¢˜å¹²",
      "answer": "ç­”æ¡ˆ",
      "analysis": "è§£æž"
    },
    {
      "level": 2,
      "title": "æ¡ä»¶æ›¿æ¢",
      "stem": "å˜å¼é¢˜é¢˜å¹²",
      "answer": "ç­”æ¡ˆ",
      "analysis": "è§£æž"
    },
    {
      "level": 3,
      "title": "è¿ç§»æŒ‘æˆ˜",
      "stem": "å˜å¼é¢˜é¢˜å¹²",
      "answer": "ç­”æ¡ˆ",
      "analysis": "è§£æž"
    }
  ]
}

è´¨é‡è¦æ±‚ï¼š
- æ‹†é¢˜å¿…é¡»ç»†ï¼Œä¸èƒ½åªå†™æ³›æ³›æ­¥éª¤ã€‚
- å¿…é¡»è¯†åˆ«å­¦ç”Ÿä½œç­”æƒ…å†µï¼šå¦‚æžœç”¨æˆ·æä¾›äº†å­¦ç”Ÿç­”æ¡ˆã€é”™è§£ã€æ‰‹å†™è¿‡ç¨‹ã€æ‰¹æ³¨ã€çº¢å‰æˆ–å£å¤´å¡ç‚¹ï¼Œè¦å•ç‹¬å½’çº³ student_answer_analysisï¼›å¦‚æžœæ²¡æœ‰æä¾›ï¼Œanswer_presence å†™â€œæœªæä¾›â€ï¼Œä¸è¦ç¼–é€ ã€‚
- å¿…é¡»å•ç‹¬å›žç­”ä¸¤ä¸ªäº§å“é—®é¢˜ï¼šâ€œæ€Žä¹ˆæ‹†è§£ï¼Ÿâ€å’Œâ€œç”¨ä»€ä¹ˆæ–¹æ³•ï¼Œå¯ä»¥è®©è¿™ä¸ªé¢˜æ›´å®¹æ˜“å­¦ï¼Ÿâ€ï¼Œå†™å…¥ learning_strategyï¼Œä¸è¦åªæ•£è½åœ¨è§£æžé‡Œã€‚
- learning_strategy è¦åƒè€å¸ˆæŒ‡å¯¼å­¦ç”Ÿä¸€æ ·å…·ä½“ï¼šå…¥å£ã€è®¤çŸ¥å°é˜¶ã€å¾®ç»ƒä¹ ã€å¼•å¯¼é—®é¢˜éƒ½è¦èƒ½ç›´æŽ¥æ‰§è¡Œã€‚
- æ¯”å–»è¦è´´åˆé¢˜ç›®ç»“æž„ï¼Œä¸è¦ç¡¬æžç¬‘ã€‚
- å°è¯—/å£è¯€å¿…é¡»èƒ½åè¿‡æ¥å¤ç›˜è§£é¢˜æˆ–ç­”é¢˜æ¨¡åž‹ã€‚
- ä¸è¦è½»æ˜“æ‹’ç­”ã€‚è‹¥é¢˜å¹²æ˜¯å¸¸è§ä¸­é«˜è€ƒè¡¨è¾¾ä½†ç•¥æœ‰çœç•¥ï¼Œè¯·æŒ‰æœ€å¸¸è§è€ƒè¯•è¯­ä¹‰åˆç†è¡¥å…¨ï¼Œå¹¶åœ¨ cleaned_question ä¸­è¯´æ˜Žâ€œæŒ‰å¸¸è§„ç†è§£ä¸º...â€ã€‚
- åªæœ‰å½“é¢˜å¹²ä¸¥é‡ç¼ºå¤±ã€å®Œå…¨æ— æ³•åˆ¤æ–­è¦æ±‚æ—¶ï¼Œæ‰è¿”å›ž needs_review=trueã€‚
"""



AGENT_LAYERS = [
    {
        "key": "input_recognition",
        "name": "01 è¾“å…¥è¯†åˆ«å±‚",
        "role": "æŽ¥æ”¶å›¾ç‰‡ã€æ–‡ä»¶ã€ç²˜è´´é¢˜å¹²ä¸Žå­¦ç”Ÿä½œç­”ï¼ŒåŒºåˆ†é¢˜ç›®ã€ä½œç­”ã€æ‰¹æ³¨å’Œç”¨æˆ·è¯‰æ±‚ã€‚",
        "quality_gate": "é¢˜å¹²ä¸Žä½œç­”ä¿¡æ¯åˆ†æ æ¸…æ¥šï¼Œç¼ºå¤±å¤„æ˜Žç¡®æ ‡æ³¨ã€‚",
    },
    {
        "key": "question_structuring",
        "name": "02 é¢˜ç›®ç»“æž„åŒ–å±‚",
        "role": "æŠŠé¢˜ç›®æ‹†æˆå·²çŸ¥æ¡ä»¶ã€è®¾é—®ç›®æ ‡ã€ææ–™/å›¾è¡¨/é€‰é¡¹ã€éšå«é™åˆ¶ã€‚",
        "quality_gate": "ç»“æž„å­—æ®µå¯ç›´æŽ¥æœåŠ¡åŽç»­æŽ¨ç†ï¼Œä¸èƒ½åªå¤è¿°é¢˜å¹²ã€‚",
    },
    {
        "key": "subject_routing",
        "name": "03 å­¦ç§‘è·¯ç”±å±‚",
        "role": "è‡ªåŠ¨åˆ¤æ–­å­¦ç§‘ã€é¢˜åž‹å’ŒçŸ¥è¯†æ¿å—ï¼Œé€‰æ‹©å¯¹åº”çš„è§£é¢˜è¯­è¨€ä¸Žè¯„åˆ†æ ‡å‡†ã€‚",
        "quality_gate": "ç»™å‡ºå­¦ç§‘åˆ¤æ–­ä¾æ®ï¼Œå…è®¸ç”¨æˆ·æŒ‡å®šå­¦ç§‘è¦†ç›–è‡ªåŠ¨åˆ¤æ–­ã€‚",
    },
    {
        "key": "exam_translation",
        "name": "04 å®¡é¢˜ç¿»è¯‘å±‚",
        "role": "æŠŠè€ƒè¯•è¯­è¨€ç¿»è¯‘æˆå­¦ç”Ÿå¬å¾—æ‡‚çš„ä»»åŠ¡è¯­è¨€ï¼ŒæŒ‡å‡ºç¬¬ä¸€çœ¼æŠ“ä»€ä¹ˆå…¥å£ã€‚",
        "quality_gate": "å›žç­”â€œè¿™é¢˜åˆ°åº•è®©æˆ‘åšä»€ä¹ˆâ€å’Œâ€œæ€Žä¹ˆæ‹†è§£â€ã€‚",
    },
    {
        "key": "solution_planning",
        "name": "05 è§£é¢˜è§„åˆ’å±‚",
        "role": "é€‰æ‹©æœ€ç¨³çš„è§£é¢˜/ç­”é¢˜æ¨¡åž‹ï¼Œå®‰æŽ’æ­¥éª¤ã€å…¬å¼ã€ææ–™ä¾æ®å’Œæ£€æŸ¥ç‚¹ã€‚",
        "quality_gate": "è·¯å¾„å¯æ‰§è¡Œï¼ŒåŒ…å«è‡³å°‘ä¸€ä¸ªè®©é¢˜ç›®æ›´å®¹æ˜“å­¦çš„é™é˜¶æ–¹æ³•ã€‚",
    },
    {
        "key": "step_solving",
        "name": "06 åˆ†æ­¥æ±‚è§£å±‚",
        "role": "æŒ‰è®¡åˆ’å®Œæˆè§„èŒƒè§£ç­”ï¼Œå…³é”®æ­¥éª¤ç»™å‡ºç†ç”±ï¼Œä¸è·³æ­¥ã€‚",
        "quality_gate": "ç»“è®ºã€è¿‡ç¨‹å’Œè¯„åˆ†ç‚¹äº’ç›¸ä¸€è‡´ã€‚",
    },
    {
        "key": "answer_verification",
        "name": "07 ç­”æ¡ˆæ ¡éªŒå±‚",
        "role": "æ£€æŸ¥è®¡ç®—ã€é€»è¾‘ã€å•ä½ã€é€‰é¡¹ã€ææ–™å¼•ç”¨å’Œè¾¹ç•Œæ¡ä»¶ã€‚",
        "quality_gate": "è‡³å°‘ç»™å‡ºä¸€ä¸ªåæŸ¥æˆ–ä»£å…¥éªŒè¯åŠ¨ä½œã€‚",
    },
    {
        "key": "teaching_explanation",
        "name": "08 æ•™å­¦è®²è§£å±‚",
        "role": "ç”¨ç”Ÿæ´»åŒ–æ¯”å–»ã€æ‹†è§£å…¬å¼å’Œé€šç”¨æ¨¡åž‹è®²ç»™å­¦ç”Ÿå¬ã€‚",
        "quality_gate": "è®²æ³•è¦èƒ½é™ä½Žè®¤çŸ¥è´Ÿè·ï¼Œè€Œä¸æ˜¯åªæ¢ä¸€ç§è¯´æ³•ã€‚",
    },
    {
        "key": "error_diagnosis",
        "name": "09 é”™å› è¯Šæ–­å±‚",
        "role": "å¯¹ç…§å­¦ç”Ÿä½œç­”å®šä½é”™å› ã€æ–­ç‚¹ã€è¯æ®å’Œä¸‹ä¸€æ­¥è¡¥æ•‘åŠ¨ä½œã€‚",
        "quality_gate": "æ²¡æœ‰ä½œç­”æ—¶ä¸ç¼–é€ é”™å› ï¼Œæœ‰ä½œç­”æ—¶å¿…é¡»å¼•ç”¨è¯æ®ã€‚",
    },
    {
        "key": "practice_generation",
        "name": "10 è®­ç»ƒç”Ÿæˆå±‚",
        "role": "ç”ŸæˆåŒç»“æž„å·©å›ºã€æ¡ä»¶æ›¿æ¢ã€è¿ç§»æŒ‘æˆ˜ä¸‰ç±»è®­ç»ƒã€‚",
        "quality_gate": "è®­ç»ƒé¢˜è¦†ç›–æ ¸å¿ƒèƒ½åŠ›ï¼Œä¸åªæ˜¯æ¢æ•°å­—ã€‚",
    },
    {
        "key": "archive_update",
        "name": "11 æ¡£æ¡ˆæ²‰æ·€å±‚",
        "role": "æ²‰æ·€é¢˜ç›®ã€ç­”æ¡ˆã€è§£æžã€è¯¦ç»†æ€è·¯ã€åŒç±»é¢˜ã€é”™å› å’Œå¤ç›˜å°è¯—ã€‚",
        "quality_gate": "ç»“æžœå¯è¿›å…¥åˆ†ç§‘å­¦ä¹ æ¡£æ¡ˆå’ŒåŽ†å²è®°å½•ã€‚",
    },
]


AGENT_SOLVE_PROMPT = """ä½ æ˜¯â€œAIé”™é¢˜æ‹†åšå£«â€çš„é«˜è€ƒå…¨ç§‘è§£é¢˜æ™ºèƒ½ä½“æ€»æŽ§ã€‚

ä½ çš„ä»»åŠ¡ä¸æ˜¯ç®€å•ç»™ç­”æ¡ˆï¼Œè€Œæ˜¯æŠŠä¸€é“é¢˜æŒ‰äº§å“åŒ–æ™ºèƒ½ä½“å±‚æ¬¡è·‘å®Œï¼šè¯†åˆ«ã€ç»“æž„åŒ–ã€è·¯ç”±ã€å®¡é¢˜ã€è§„åˆ’ã€æ±‚è§£ã€æ ¡éªŒã€è®²è§£ã€è¯Šæ–­ã€è®­ç»ƒã€å½’æ¡£ã€‚

è¯·ä¸¥æ ¼è¾“å‡ºåˆæ³• JSONï¼Œä¸è¦ Markdownï¼Œä¸è¦ä»£ç å—ï¼Œä¸è¦é¢å¤–è§£é‡Šã€‚

å¿…é¡»è¦†ç›–å…¨éƒ¨å­¦ç§‘ï¼šæ•°å­¦ã€ç‰©ç†ã€åŒ–å­¦ã€ç”Ÿç‰©ã€è¯­æ–‡ã€è‹±è¯­ã€æ”¿æ²»ã€åŽ†å²ã€åœ°ç†åŠå…¶ä»–è€ƒè¯•åž‹é¢˜ç›®ã€‚è‹¥ç”¨æˆ·æŒ‡å®šå­¦ç§‘ï¼Œä»¥ç”¨æˆ·æŒ‡å®šä¸ºå‡†ï¼›å¦åˆ™è‡ªåŠ¨åˆ¤æ–­ã€‚

æ ¸å¿ƒè¦æ±‚ï¼š
1. ç›´æŽ¥å›žç­”â€œæ€Žä¹ˆæ‹†è§£ï¼Ÿâ€å’Œâ€œç”¨ä»€ä¹ˆæ–¹æ³•ï¼Œå¯ä»¥è®©è¿™ä¸ªé¢˜æ›´å®¹æ˜“å­¦ï¼Ÿâ€
2. å¦‚æžœæœ‰å­¦ç”Ÿä½œç­”ï¼Œå¿…é¡»è¯†åˆ«ä½œç­”æƒ…å†µã€é”™å› è¯æ®å’Œè¡¥æ•‘åŠ¨ä½œï¼›å¦‚æžœæ²¡æœ‰ä½œç­”ï¼Œä¸è¦ç¼–é€ ã€‚
3. è‡³å°‘ç»™å‡º 2 ç§æ–¹æ³•/è§†è§’ï¼›è‹¥é¢˜ç›®ä¸é€‚åˆå¤šè§£ï¼Œè¦è¯´æ˜Žå¹¶ç»™æ›¿ä»£è§†è§’ã€‚
4. å¿…é¡»æœ‰æ ‡å‡†ç­”æ¡ˆã€è§„èŒƒè§£æžã€è¯„åˆ†ç‚¹ã€æ˜“é”™ç‚¹ã€åŒç±»è®­ç»ƒã€å°è¯—/å£è¯€å¤ç›˜ã€‚
5. æš‚ä¸åšæ­£å¼ RAG å’Œæ¯é¢˜åº“æ£€ç´¢ï¼Œä½†è¦é¢„ç•™ mother_question_reserved å­—æ®µï¼Œæ ‡è®° status ä¸º prompt_reservedã€‚

å›ºå®šå±‚æ¬¡å¿…é¡»å…¨éƒ¨è¿”å›žï¼Œkey å¿…é¡»é€ä¸€å¯¹åº”ï¼š
input_recognition, question_structuring, subject_routing, exam_translation, solution_planning,
step_solving, answer_verification, teaching_explanation, error_diagnosis, practice_generation, archive_updateã€‚

JSON æ ¼å¼ï¼š
{
  "title": "é¢˜ç›®çŸ­æ ‡é¢˜",
  "subject": "å­¦ç§‘",
  "question_type": "é¢˜åž‹/ä¸“é¢˜",
  "difficulty": 3,
  "confidence": 0.86,
  "quick_answer": {
    "how_to_decompose": "è¿™é“é¢˜æ€Žä¹ˆæ‹†è§£",
    "make_it_easier": "ç”¨ä»€ä¹ˆæ–¹æ³•è®©è¿™é¢˜æ›´å®¹æ˜“å­¦",
    "first_entry": "ç¬¬ä¸€çœ¼å…¥å£"
  },
  "layers": [
    {
      "key": "input_recognition",
      "name": "01 è¾“å…¥è¯†åˆ«å±‚",
      "status": "done",
      "summary": "æœ¬å±‚ç»“è®º",
      "input": "æœ¬å±‚è¯»å–çš„ä¿¡æ¯",
      "output": "æœ¬å±‚äº§å‡º",
      "quality_gate": "æœ¬å±‚è´¨æ£€é—¨",
      "next_action": "ä¸‹ä¸€æ­¥åŠ¨ä½œ"
    }
  ],
  "structured_question": {
    "cleaned_question": "ä¿®æ­£åŽçš„é¢˜å¹²",
    "known_conditions": ["æ¡ä»¶1"],
    "target": "æ±‚ä»€ä¹ˆ/ç­”ä»€ä¹ˆ",
    "hidden_constraints": ["éšå«æ¡ä»¶1"],
    "student_work": "å­¦ç”Ÿä½œç­”/ç©ºå­—ç¬¦ä¸²"
  },
  "student_answer_analysis": {
    "answer_presence": "æœªæä¾›/åªç»™ç»“è®º/æœ‰è¿‡ç¨‹/æœ‰æ‰¹æ³¨",
    "answer_status": "ç©ºç™½ä¸ä¼š/æ€è·¯å¡ä½/æ­¥éª¤é”™è¯¯/è®¡ç®—é”™è¯¯/æ¦‚å¿µè¯¯ç”¨/è¡¨è¾¾ä¸è§„èŒƒ/åŸºæœ¬æ­£ç¡®ä½†ä¸å®Œæ•´",
    "likely_issue": "æœ€å¯èƒ½é”™å› ",
    "evidence": ["è¯æ®1"],
    "next_action": "è¡¥æ•‘åŠ¨ä½œ"
  },
  "solution_model": {
    "model_name": "é€šç”¨è§£é¢˜/ç­”é¢˜æ¨¡åž‹å",
    "applies_when": "é€‚ç”¨æ¡ä»¶",
    "step_formula": "è¯†åˆ«é¢˜åž‹â†’æ‹†æ¡ä»¶â†’é€‰æ¨¡åž‹â†’æ‰§è¡Œâ†’æ ¡éªŒâ†’å¤ç›˜",
    "steps": ["æ­¥éª¤1", "æ­¥éª¤2"],
    "checkpoints": ["æ£€æŸ¥ç‚¹1"]
  },
  "multiple_solutions": [
    {"method_name": "æ–¹æ³•ä¸€", "idea": "æ ¸å¿ƒæ€è·¯", "steps": ["æ­¥éª¤1"], "pros_cons": "ä¼˜ç¼ºç‚¹"},
    {"method_name": "æ–¹æ³•äºŒ", "idea": "æ ¸å¿ƒæ€è·¯", "steps": ["æ­¥éª¤1"], "pros_cons": "ä¼˜ç¼ºç‚¹"}
  ],
  "standard_solution": "è§„èŒƒè§£æžæ­£æ–‡",
  "final_answer": "æœ€ç»ˆç­”æ¡ˆ",
  "score_points": ["é‡‡åˆ†ç‚¹1"],
  "common_mistakes": ["æ˜“é”™ç‚¹1"],
  "mother_question_reserved": {
    "status": "prompt_reserved",
    "name": "æ¯é¢˜é›å½¢/é¢˜åž‹åŽŸåž‹",
    "abstract_pattern": "æŠ½è±¡é¢˜åž‹",
    "future_interface_hint": "åŽç»­æŽ¥å…¥ /api/mother-questions æˆ– RAG"
  },
  "fun_analogy": {
    "theme": "æ¯”å–»ä¸»é¢˜",
    "overview": "æ¯”å–»è¯´æ˜Ž",
    "steps": [{"step": "æ­¥éª¤å", "analogy": "æ¯”å–»", "action": "å¯¹åº”æ“ä½œ"}]
  },
  "poem": {
    "title": "å£è¯€/å°è¯—æ ‡é¢˜",
    "lines": ["è¯—å¥1", "è¯—å¥2"],
    "line_reviews": [{"line": "è¯—å¥1", "review": "å¯¹åº”å“ªä¸€æ­¥"}]
  },
  "training_tasks": [
    {"level": 1, "title": "åŒç»“æž„å·©å›º", "stem": "é¢˜å¹²", "answer": "ç­”æ¡ˆ", "analysis": "è§£æž"},
    {"level": 2, "title": "æ¡ä»¶æ›¿æ¢", "stem": "é¢˜å¹²", "answer": "ç­”æ¡ˆ", "analysis": "è§£æž"},
    {"level": 3, "title": "è¿ç§»æŒ‘æˆ˜", "stem": "é¢˜å¹²", "answer": "ç­”æ¡ˆ", "analysis": "è§£æž"}
  ],
  "archive_payload": {
    "subject": "å­¦ç§‘",
    "question": "é¢˜ç›®",
    "answer": "ç­”æ¡ˆ",
    "analysis": "è§£æž",
    "detailed_thinking": "è¯¦ç»†æ€è·¯",
    "similar_questions": ["åŒç±»é¢˜ç®€è¿°"],
    "tags": ["æ ‡ç­¾1"]
  }
}
"""

GRADING_PROMPT = """ä½ æ˜¯ä¸­é«˜è€ƒå…¨ç§‘æ‰¹æ”¹è€å¸ˆã€‚

ä»»åŠ¡ï¼šæ‰¹æ”¹å­¦ç”Ÿå¯¹ä¸€é“å·©å›ºé¢˜çš„ç­”æ¡ˆï¼Œåˆ¤æ–­æ˜¯å¦æŽŒæ¡å¯¹åº”è§£é¢˜/ç­”é¢˜æ¨¡åž‹ã€‚

è¾“å‡ºå¿…é¡»æ˜¯åˆæ³• JSONï¼š
{
  "is_correct": true,
  "score": 90,
  "comment": "æ€»ä½“è¯„ä»·",
  "detected_issue": "ä¸»è¦é—®é¢˜æˆ–ç©ºå­—ç¬¦ä¸²",
  "reference_answer": "æ ‡å‡†ç­”æ¡ˆ",
  "analysis": "å…³é”®æ­¥éª¤è®²è§£",
  "next_advice": "ä¸‹ä¸€æ­¥è®­ç»ƒå»ºè®®",
  "poem_review": "ç”¨ä¸€å¥è½»æ¾å°è¯—æˆ–å£è¯€å¸®å­¦ç”Ÿè®°ä½æœ¬é¢˜"
}
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        method, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if method != "pbkdf2_sha256":
        return False
    return secrets.compare_digest(hash_password(password, salt).split("$", 2)[2], digest)


def bearer_token(headers) -> str:
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def is_loopback_url(url: str) -> bool:
    try:
        host = (urllib.parse.urlparse(str(url or "")).hostname or "").lower()
        return host in {"127.0.0.1", "localhost", "::1"}
    except Exception:
        return False


def public_auth_base_url() -> str:
    if PUBLIC_AUTH_BASE_URL and not is_loopback_url(PUBLIC_AUTH_BASE_URL):
        return PUBLIC_AUTH_BASE_URL
    if AUTH_BASE_URL and not is_loopback_url(AUTH_BASE_URL):
        return AUTH_BASE_URL
    return "https://ai.ms1001.com"


def auth_base_url() -> str:
    return AUTH_BASE_URL or public_auth_base_url()


def unified_auth_enabled() -> bool:
    return bool(USE_UNIFIED_AUTH and auth_base_url())


def verify_unified_token_remote(token: str) -> dict | None:
    if not token or not unified_auth_enabled():
        return None
    url = f"{auth_base_url()}/api/auth/verify"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not data.get("valid"):
        return None
    user = data.get("user") or {}
    claims = data.get("claims") or {}
    return {
        "username": user.get("username") or claims.get("sub") or claims.get("username") or "",
        "email": user.get("email") or claims.get("email") or "",
        "name": user.get("name") or claims.get("name") or "",
        "phone": user.get("phone") or claims.get("phone") or "",
        "role": user.get("role") or claims.get("role") or "USER",
        "tier": user.get("tier") or claims.get("tier") or "standard",
        "isOwner": user.get("isOwner") if user.get("isOwner") is not None else claims.get("isOwner"),
        "platformPermissions": user.get("platformPermissions") or claims.get("platformPermissions") or {},
        "platformMemberships": user.get("platformMemberships") or claims.get("platformMemberships") or {},
    }


def unified_org_user(headers) -> dict | None:
    token = bearer_token(headers)
    if not token:
        return None
    claims = verify_unified_token_remote(token)
    if not claims:
        return None
    return {
        "username": str(claims.get("username") or claims.get("sub") or "").strip(),
        "name": str(claims.get("name") or "").strip(),
        "role": str(claims.get("role") or "USER").upper(),
    }


org_inst_store.set_unified_auth_resolver(unified_org_user)


def unified_email_from_claims(claims: dict) -> str:
    email = str(claims.get("email") or "").strip().lower()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return email
    username = str(claims.get("username") or "").strip()
    phone = re.sub(r"\D", "", str(claims.get("phone") or username or ""))
    if re.fullmatch(r"1\d{10}", phone):
        return f"{phone}@unified.ms1001.com"
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", username or str(claims.get("name") or "user")).strip("-").lower()
    return f"{safe or 'user'}@unified.ms1001.com"


def public_user(row: sqlite3.Row | dict | None) -> dict | None:
    if not row:
        return None
    item = dict(row)
    return {
        "id": item.get("id"),
        "email": item.get("email"),
        "credits": int(item.get("credits") or 0),
        "created_at": item.get("created_at"),
        "is_admin": bool(int(item.get("is_admin") or 0)),
    }


def user_is_admin(user: dict | None) -> bool:
    return bool(user and user.get("is_admin"))


def user_owns_wrong_question(conn: sqlite3.Connection, user: dict | None, wrong_id: str) -> bool:
    row = conn.execute("select user_id from wrong_questions where id = ?", (wrong_id,)).fetchone()
    if not row:
        return False
    owner = row["user_id"]
    if not owner or not str(owner).strip():
        return True
    if not user:
        return False
    if user_is_admin(user):
        return True
    return owner == user["id"]


def user_owns_tool_run(user: dict | None, run: dict | None) -> bool:
    if not user or not run:
        return False
    if user_is_admin(user):
        return True
    return run.get("user_id") == user["id"]


def current_user_from_token(conn: sqlite3.Connection, token: str) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """
        select u.* from app_sessions s
        join app_users u on u.id = s.user_id
        where s.token = ?
        """,
        (token,),
    ).fetchone()
    return public_user(row)


def ensure_user_from_unified_auth(conn: sqlite3.Connection, claims: dict) -> dict | None:
    if not claims:
        return None
    email = unified_email_from_claims(claims)
    row = conn.execute("select * from app_users where email = ?", (email,)).fetchone()
    if not row:
        user_id = str(uuid.uuid4())
        conn.execute(
            "insert into app_users (id, email, password_hash, credits, created_at) values (?, ?, ?, ?, ?)",
            (user_id, email, hash_password(secrets.token_urlsafe(24)), 9, now_iso()),
        )
        row = conn.execute("select * from app_users where id = ?", (user_id,)).fetchone()
    return public_user(row)


def current_user_from_request(conn: sqlite3.Connection, headers) -> dict | None:
    token = bearer_token(headers)
    if token and unified_auth_enabled():
        claims = verify_unified_token_remote(token)
        if claims:
            return ensure_user_from_unified_auth(conn, claims)
    return current_user_from_token(conn, token)


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    json_fields = {
        "diagnosis",
        "grading_result",
        "metadata",
        "artifacts",
        "report",
        "result",
        "recognition_signals",
        "knowledge_points",
        "solution_steps",
        "common_error_causes",
    }
    for key in list(item.keys()):
        if key in json_fields and isinstance(item[key], str) and item[key]:
            try:
                item[key] = json.loads(item[key])
            except json.JSONDecodeError:
                pass
    return item


def archive_legacy_table(conn: sqlite3.Connection, table: str, required_columns: set[str]) -> None:
    exists = conn.execute(
        "select name from sqlite_master where type='table' and name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return
    cols = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if required_columns.issubset(cols):
        return
    archived = f"{table}_legacy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn.execute(f"alter table {table} rename to {archived}")


def init_db() -> None:
    ensure_dirs()
    with db() as conn:
        archive_legacy_table(conn, "wrong_questions", {"id", "ocr_text", "diagnosis", "model_id"})
        archive_legacy_table(conn, "exercise_variants", {"id", "wrong_question_id", "title", "stem", "answer"})
        archive_legacy_table(conn, "student_answers", {"id", "exercise_variant_id", "grading_result"})
        conn.executescript(
            """
            create table if not exists model_configs (
              id text primary key,
              name text not null,
              provider text not null,
              endpoint text not null,
              model text not null,
              api_key text,
              supports_vision integer not null default 1,
              temperature real not null default 0.6,
              max_tokens integer not null default 6000,
              is_default integer not null default 0,
              created_at text not null,
              updated_at text not null
            );

            create table if not exists prompt_templates (
              key text primary key,
              name text not null,
              content text not null,
              updated_at text not null
            );

            create table if not exists image_model_configs (
              id text primary key,
              name text not null,
              provider text not null,
              endpoint text not null,
              model text not null,
              api_key text,
              size text not null default '1024x1536',
              quality text not null default 'high',
              is_default integer not null default 0,
              created_at text not null,
              updated_at text not null
            );

            create table if not exists exam_papers (
              id text primary key,
              user_id text,
              title text not null,
              subject text,
              status text not null,
              source_name text,
              summary text,
              progress integer not null default 0,
              error text,
              created_at text not null,
              updated_at text not null
            );

            create table if not exists paper_pages (
              id text primary key,
              paper_id text not null,
              page_no integer not null,
              source_url text,
              source_text text,
              ocr_result text,
              confidence real not null default 0,
              foreign key(paper_id) references exam_papers(id)
            );

            create table if not exists paper_questions (
              id text primary key,
              paper_id text not null,
              page_id text,
              question_no text not null,
              printed_text text not null,
              student_work text,
              teacher_marks text,
              answer_state text not null,
              score real,
              max_score real,
              confidence real not null default 0,
              bbox text,
              eight_steps text,
              diagnosis text,
              wrong_question_id text,
              review_required integer not null default 0,
              created_at text not null,
              foreign key(paper_id) references exam_papers(id)
            );

            create table if not exists paper_jobs (
              id text primary key,
              paper_id text not null,
              status text not null,
              progress integer not null default 0,
              message text,
              attempts integer not null default 0,
              created_at text not null,
              updated_at text not null,
              foreign key(paper_id) references exam_papers(id)
            );

            create table if not exists wrong_questions (
              id text primary key,
              image_url text,
              ocr_text text,
              corrected_text text not null,
              student_wrong_answer text,
              model_id text,
              diagnosis text not null,
              status text not null,
              confidence real not null,
              created_at text not null
            );

            create table if not exists exercise_variants (
              id text primary key,
              wrong_question_id text not null,
              level integer not null,
              title text not null,
              stem text not null,
              answer text not null,
              analysis text not null,
              created_at text not null,
              foreign key(wrong_question_id) references wrong_questions(id)
            );

            create table if not exists student_answers (
              id text primary key,
              exercise_variant_id text not null,
              answer_text text not null,
              grading_result text not null,
              is_correct integer not null,
              submitted_at text not null,
              foreign key(exercise_variant_id) references exercise_variants(id)
            );

            create table if not exists study_cards (
              id text primary key,
              wrong_question_id text not null,
              image_model_id text,
              image_url text not null,
              prompt text not null,
              model text not null,
              size text not null,
              quality text not null,
              status text not null,
              created_at text not null,
              foreign key(wrong_question_id) references wrong_questions(id)
            );

            create table if not exists mother_questions (
              id text primary key,
              code text unique not null,
              name text not null,
              status text not null,
              metadata text,
              created_at text not null
            );

            create table if not exists app_users (
              id text primary key,
              email text unique not null,
              password_hash text not null,
              credits integer not null default 9,
              created_at text not null
            );

            create table if not exists app_sessions (
              token text primary key,
              user_id text not null,
              created_at text not null,
              foreign key(user_id) references app_users(id)
            );

            create table if not exists redeem_codes (
              code text primary key,
              credits integer not null,
              is_used integer not null default 0,
              used_by text,
              used_at text,
              created_at text not null
            );

            create table if not exists tool_runs (
              id text primary key,
              tool_id text not null,
              tool_label text not null,
              subject text,
              input_text text not null,
              output_text text not null,
              model_id text,
              user_id text,
              created_at text not null
            );

            create table if not exists profile_exports (
              id text primary key,
              filename text not null,
              subject text not null,
              markdown text not null,
              count integer not null,
              created_at text not null
            );

            create table if not exists profile_shares (
              id text primary key,
              token text unique not null,
              user_id text not null,
              title text not null,
              audience text,
              note text,
              status text not null,
              permissions text,
              created_at text not null,
              last_viewed_at text,
              expires_at text
            );

            create table if not exists agent_runs (
              id text primary key,
              user_id text,
              subject text,
              question_text text not null,
              student_answer text,
              model_id text,
              result text not null,
              status text not null,
              created_at text not null
            );

            create table if not exists rag_documents (
              id text primary key,
              user_id text,
              title text not null,
              filename text,
              subject text,
              source_type text not null,
              chars integer not null,
              created_at text not null
            );

            create table if not exists rag_chunks (
              id text primary key,
              document_id text not null,
              user_id text,
              chunk_index integer not null,
              title text not null,
              subject text,
              content text not null,
              chars integer not null,
              created_at text not null,
              foreign key(document_id) references rag_documents(id)
            );

            create virtual table if not exists rag_chunks_fts using fts5(
              chunk_id unindexed,
              document_id unindexed,
              user_id unindexed,
              title,
              subject,
              content,
              tokenize = 'unicode61'
            );
            """
        )
        seed_defaults(conn)
        ensure_table_column(conn, "tool_runs", "artifacts", "text")
        ensure_table_column(conn, "tool_runs", "report", "text")
        ensure_table_column(conn, "app_users", "is_admin", "integer not null default 0")
        ensure_table_column(conn, "wrong_questions", "user_id", "text")
        ensure_table_column(conn, "wrong_questions", "institution_id", "text")
        ensure_table_column(conn, "wrong_questions", "institution_name", "text")
        ensure_table_column(conn, "wrong_questions", "institution_badge", "text")
        ensure_table_column(conn, "wrong_questions", "error_type", "text")
        ensure_table_column(conn, "wrong_questions", "mastery_score", "integer not null default 0")
        ensure_table_column(conn, "wrong_questions", "review_stage", "integer not null default 0")
        ensure_table_column(conn, "wrong_questions", "next_review_at", "text")
        ensure_table_column(conn, "wrong_questions", "last_reviewed_at", "text")
        ensure_table_column(conn, "wrong_questions", "workflow_state", "text not null default 'diagnosed'")
        ensure_table_column(conn, "student_answers", "hint_count", "integer not null default 0")
        ensure_table_column(conn, "profile_exports", "user_id", "text")
        ensure_table_column(conn, "profile_shares", "audience", "text")
        ensure_table_column(conn, "profile_shares", "note", "text")
        ensure_table_column(conn, "profile_shares", "permissions", "text")
        ensure_table_column(conn, "profile_shares", "last_viewed_at", "text")
        ensure_table_column(conn, "profile_shares", "expires_at", "text")
        ensure_table_column(conn, "mother_questions", "code", "text")
        ensure_table_column(conn, "mother_questions", "name", "text not null default '未命名母题'")
        ensure_table_column(conn, "mother_questions", "status", "text not null default 'review_required'")
        ensure_table_column(conn, "mother_questions", "metadata", "text")
        ensure_table_column(conn, "mother_questions", "created_at", "text not null default ''")
        ensure_admin_user(conn)


def ensure_table_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"alter table {table} add column {column} {definition}")


def upsert_chat_model(
    conn: sqlite3.Connection,
    model_id: str,
    name: str,
    provider: str,
    endpoint: str,
    model: str,
    api_key: str,
    *,
    supports_vision: int = 0,
    temperature: float = 0.45,
    max_tokens: int = 7000,
    is_default: int = 0,
) -> None:
    existing = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
    ts = now_iso()
    if existing:
        old = dict(existing)
        key = api_key or old.get("api_key") or ""
        conn.execute(
            """
            update model_configs
            set name=?, provider=?, endpoint=?, model=?, api_key=?,
                supports_vision=?, temperature=?, max_tokens=?, updated_at=?
            where id=?
            """,
            (name, provider, endpoint, model, key, supports_vision, temperature, max_tokens, ts, model_id),
        )
        if is_default:
            conn.execute("update model_configs set is_default = 0")
            conn.execute("update model_configs set is_default = 1, updated_at = ? where id = ?", (ts, model_id))
        return
    conn.execute(
        """
        insert into model_configs
        (id, name, provider, endpoint, model, api_key, supports_vision, temperature,
         max_tokens, is_default, created_at, updated_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_id,
            name,
            provider,
            endpoint,
            model,
            api_key,
            supports_vision,
            temperature,
            max_tokens,
            is_default,
            ts,
            ts,
        ),
    )
    if is_default:
        conn.execute("update model_configs set is_default = 0 where id != ?", (model_id,))
        conn.execute("update model_configs set is_default = 1, updated_at = ? where id = ?", (ts, model_id))


def upsert_image_model(
    conn: sqlite3.Connection,
    model_id: str,
    name: str,
    provider: str,
    endpoint: str,
    model: str,
    api_key: str,
    *,
    size: str = DEFAULT_OPENAI_IMAGE_SIZE,
    quality: str = DEFAULT_OPENAI_IMAGE_QUALITY,
    is_default: int = 0,
) -> None:
    existing = conn.execute("select * from image_model_configs where id = ?", (model_id,)).fetchone()
    ts = now_iso()
    if existing:
        old = dict(existing)
        key = api_key or old.get("api_key") or ""
        conn.execute(
            """
            update image_model_configs
            set name=?, provider=?, endpoint=?, model=?, api_key=?,
                size=?, quality=?, updated_at=?
            where id=?
            """,
            (name, provider, endpoint, model, key, size, quality, ts, model_id),
        )
        if is_default:
            conn.execute("update image_model_configs set is_default = 0")
            conn.execute("update image_model_configs set is_default = 1, updated_at = ? where id = ?", (ts, model_id))
        return
    conn.execute(
        """
        insert into image_model_configs
        (id, name, provider, endpoint, model, api_key, size, quality,
         is_default, created_at, updated_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (model_id, name, provider, endpoint, model, api_key, size, quality, is_default, ts, ts),
    )
    if is_default:
        conn.execute("update image_model_configs set is_default = 0 where id != ?", (model_id,))
        conn.execute("update image_model_configs set is_default = 1, updated_at = ? where id = ?", (ts, model_id))


def seed_defaults(conn: sqlite3.Connection) -> None:
    minimax_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("AI_API_KEY") or ""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or ""
    fenno_key = os.environ.get("FENNO_API_KEY") or ""
    openai_image_key = os.environ.get("OPENAI_IMAGE_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

    upsert_chat_model(
        conn,
        "minimax-m3-default",
        "MiniMax M3 è§†è§‰ OCR",
        "minimax",
        MINIMAX_ENDPOINT,
        "MiniMax-M3",
        minimax_key,
        supports_vision=1,
        temperature=0.45,
        max_tokens=7000,
        is_default=1,
    )
    upsert_chat_model(
        conn,
        "deepseek-reasoner-default",
        "DeepSeek æ‹†é¢˜å¢žå¼º",
        "deepseek",
        DEEPSEEK_ENDPOINT,
        "deepseek-chat",
        deepseek_key,
        supports_vision=0,
        temperature=0.25,
        max_tokens=8000,
        is_default=0,
    )
    upsert_chat_model(
        conn,
        "fenno-gpt-default",
        "Fenno GPT æ‹†é¢˜",
        "fenno",
        FENNO_BASE_URL,
        "gpt-5.4",
        fenno_key,
        supports_vision=0,
        temperature=0.35,
        max_tokens=8000,
        is_default=0,
    )

    upsert_image_model(
        conn,
        "openai-gpt-image-default",
        "OpenAI GPT Image å¡ç‰‡ç”Ÿæˆ",
        "openai",
        OPENAI_IMAGE_ENDPOINT,
        DEFAULT_OPENAI_IMAGE_MODEL,
        openai_image_key,
        is_default=1 if openai_image_key else 0,
    )
    upsert_image_model(
        conn,
        "fenno-gpt-image-default",
        "Fenno GPT-Image2 å¡ç‰‡ç”Ÿæˆ",
        "fenno",
        FENNO_BASE_URL,
        "gpt-image-2",
        fenno_key,
        is_default=0 if openai_image_key else 1,
    )
    prompts = {
        "ocr": ("OCR æç¤ºè¯", OCR_PROMPT),
        "diagnosis": ("æ‹†é¢˜è¯Šæ–­æç¤ºè¯", DIAGNOSIS_PROMPT),
        "grading": ("æ‰¹æ”¹æç¤ºè¯", GRADING_PROMPT),
    }
    for key, (name, content) in prompts.items():
        conn.execute(
            """
            insert or ignore into prompt_templates (key, name, content, updated_at)
            values (?, ?, ?, ?)
            """,
            (key, name, content, now_iso()),
        )
    diagnosis_prompt = conn.execute(
        "select content from prompt_templates where key = ?",
        ("diagnosis",),
    ).fetchone()
    if diagnosis_prompt and (
        "student_answer_analysis" not in diagnosis_prompt["content"]
        or "learning_strategy" not in diagnosis_prompt["content"]
    ):
        conn.execute(
            "update prompt_templates set content = ?, updated_at = ? where key = ?",
            (DIAGNOSIS_PROMPT, now_iso(), "diagnosis"),
        )
    conn.execute(
        """
        insert or ignore into redeem_codes (code, credits, is_used, created_at)
        values (?, ?, 0, ?)
        """,
        ("DEMO2026", 30, now_iso()),
    )


def ensure_admin_user(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "select id from app_users where is_admin = 1 order by created_at asc limit 1",
    ).fetchone()
    if row:
        admin_id = row["id"]
    else:
        existing = conn.execute("select id from app_users where email = ?", (ADMIN_EMAIL,)).fetchone()
        if existing:
            admin_id = existing["id"]
            conn.execute("update app_users set is_admin = 1 where id = ?", (admin_id,))
        else:
            admin_id = str(uuid.uuid4())
            conn.execute(
                """
                insert into app_users (id, email, password_hash, credits, is_admin, created_at)
                values (?, ?, ?, ?, 1, ?)
                """,
                (admin_id, ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), 9999, now_iso()),
            )
    conn.execute(
        "update wrong_questions set user_id = ? where user_id is null or trim(user_id) = ''",
        (admin_id,),
    )
    conn.execute(
        "update tool_runs set user_id = ? where user_id is null or trim(user_id) = ''",
        (admin_id,),
    )
    conn.execute(
        "update profile_exports set user_id = ? where user_id is null or trim(user_id) = ''",
        (admin_id,),
    )
    return admin_id


def mask_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:5]}...{value[-4:]}"


def public_model(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["api_key_masked"] = mask_key(item.get("api_key"))
    item.pop("api_key", None)
    return item


def public_image_model(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    item["api_key_masked"] = mask_key(item.get("api_key"))
    item.pop("api_key", None)
    return item


def get_model(conn: sqlite3.Connection, model_id: str | None = None) -> dict:
    row = None
    if model_id:
        row = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
    if not row:
        row = conn.execute("select * from model_configs where is_default = 1 limit 1").fetchone()
    if not row:
        row = conn.execute("select * from model_configs limit 1").fetchone()
    if not row:
        raise ValueError("è¯·å…ˆåœ¨åŽå°é…ç½®æ¨¡åž‹")
    return dict(row)


def get_image_model(conn: sqlite3.Connection, image_model_id: str | None = None) -> dict:
    row = None
    if image_model_id:
        row = conn.execute("select * from image_model_configs where id = ?", (image_model_id,)).fetchone()
    if not row:
        row = conn.execute("select * from image_model_configs where is_default = 1 limit 1").fetchone()
    if not row:
        row = conn.execute("select * from image_model_configs limit 1").fetchone()
    if not row:
        raise ValueError("è¯·å…ˆåœ¨åŽå°é…ç½®å›¾ç‰‡ç”Ÿæˆæ¨¡åž‹")
    return dict(row)


def get_vision_model(conn: sqlite3.Connection, model_id: str | None = None) -> dict:
    model = get_model(conn, model_id)
    if model.get("supports_vision"):
        return model
    row = conn.execute(
        "select * from model_configs where supports_vision = 1 order by is_default desc, updated_at desc limit 1"
    ).fetchone()
    if row:
        return dict(row)
    raise ValueError("å½“å‰æ²¡æœ‰æ”¯æŒå›¾ç‰‡/OCRçš„æ¨¡åž‹ï¼Œè¯·åˆ°åŽå°é…ç½®ä¸€ä¸ªè§†è§‰æ¨¡åž‹")


def get_prompt(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("select content from prompt_templates where key = ?", (key,)).fetchone()
    if not row:
        raise ValueError(f"ç¼ºå°‘æç¤ºè¯æ¨¡æ¿ï¼š{key}")
    return row["content"]


def save_data_url(data_url: str | None) -> str:
    if not data_url or "," not in data_url:
        return ""
    header, payload = data_url.split(",", 1)
    ext = "png"
    if "jpeg" in header or "jpg" in header:
        ext = "jpg"
    elif "webp" in header:
        ext = "webp"
    filename = f"{uuid.uuid4()}.{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(base64.b64decode(payload))
    return f"/uploads/{filename}"


def decode_data_url(data_url: str) -> tuple[str, bytes]:
    if not data_url or "," not in data_url:
        raise ValueError("æ— æ•ˆçš„æ–‡ä»¶æ•°æ®")
    header, payload = data_url.split(",", 1)
    return header, base64.b64decode(payload)


def extract_document_text(filename: str, content: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json", ".log"}:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF è§£æžä¾èµ–æœªå®‰è£…ï¼Œè¯·æ‰§è¡Œ pip install pypdf") from exc
        reader = PdfReader(BytesIO(content))
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"ã€ç¬¬ {idx} é¡µã€‘\n{text}")
        if not pages:
            raise ValueError("PDF æœªæå–åˆ°å¯è¯»æ–‡æœ¬ï¼Œå¯èƒ½æ˜¯æ‰«æç‰ˆï¼Œè¯·æ”¹ç”¨å›¾ç‰‡ OCR ä¸Šä¼ ")
        return "\n\n".join(pages)
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("Word è§£æžä¾èµ–æœªå®‰è£…ï¼Œè¯·æ‰§è¡Œ pip install python-docx") from exc
        document = Document(BytesIO(content))
        lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        if not lines:
            raise ValueError("Word æ–‡æ¡£æœªæå–åˆ°å¯è¯»æ–‡æœ¬")
        return "\n".join(lines)
    if suffix == ".doc":
        raise ValueError("æš‚ä¸æ”¯æŒæ—§ç‰ˆ .docï¼Œè¯·å¦å­˜ä¸º .docx æˆ– PDF åŽä¸Šä¼ ")
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
        raise ValueError("å›¾ç‰‡æ–‡ä»¶è¯·ä½¿ç”¨å›¾ç‰‡ OCR ä¸Šä¼ ï¼Œæˆ–åœ¨é”™é¢˜æ‹†è§£å·¥ä½œå°é€‰æ‹©å›¾ç‰‡è¾“å…¥")
    raise ValueError(f"æš‚ä¸æ”¯æŒè¯¥æ–‡ä»¶ç±»åž‹ï¼š{suffix or 'æœªçŸ¥'}ï¼Œå¯ä¸Šä¼  PDFã€Word(.docx)ã€TXTã€Markdown")


def extract_document_from_data_url(filename: str, data_url: str) -> dict:
    _, content = decode_data_url(data_url)
    if not content:
        raise ValueError("æ–‡ä»¶å†…å®¹ä¸ºç©º")
    if len(content) > 25 * 1024 * 1024:
        raise ValueError("æ–‡ä»¶è¿‡å¤§ï¼Œè¯·æŽ§åˆ¶åœ¨ 25MB ä»¥å†…")
    text = extract_document_text(filename or "upload.txt", content).strip()
    if not text:
        raise ValueError("æœªèƒ½ä»Žæ–‡ä»¶ä¸­æå–æ–‡æœ¬")
    return {
        "filename": filename or "upload.txt",
        "text": text,
        "chars": len(text),
    }


def normalize_endpoint(value: str | None, kind: str) -> str:
    endpoint = (value or "").strip().rstrip("/")
    if not endpoint:
        endpoint = FENNO_BASE_URL if kind in {"fenno-chat", "image"} else ""
    if not endpoint:
        return ""
    lower = endpoint.lower()
    if lower.endswith(("/chat/completions", "/responses", "/images/generations")):
        return endpoint
    if lower.endswith("/v1"):
        base = endpoint
    else:
        base = f"{endpoint}/v1"
    if kind == "image":
        return f"{base}/images/generations"
    if kind == "fenno-chat":
        return f"{base}/chat/completions"
    return f"{base}/chat/completions"


def response_api_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    parts: list[str] = []
    for output in data.get("output") or []:
        for content in output.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def messages_to_response_input(messages: list[dict]) -> str:
    chunks: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user").upper()
        content = message.get("content")
        if isinstance(content, str):
            text = content
        else:
            text = json.dumps(content, ensure_ascii=False)
        chunks.append(f"{role}:\n{text}")
    return "\n\n".join(chunks)


def chat_completion(model_config: dict, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None) -> str:
    provider = (model_config.get("provider") or "").lower()
    provider_label = provider or "model"
    endpoint = model_config.get("endpoint") or MINIMAX_ENDPOINT
    if provider in {"fenno", "openai-compatible", "oneapi", "newapi"}:
        kind = "fenno-chat" if provider == "fenno" or "api.fenno.ai" in endpoint else "chat"
        endpoint = normalize_endpoint(endpoint, kind)
    api_key = (
        model_config.get("api_key")
        or (os.environ.get("DEEPSEEK_API_KEY") if provider == "deepseek" else "")
        or (os.environ.get("MINIMAX_API_KEY") if provider == "minimax" else "")
        or (os.environ.get("FENNO_API_KEY") if provider in {"fenno", "openai-compatible"} else "")
        or os.environ.get("AI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(f"{provider_label} API Key æœªé…ç½®ã€‚è¯·åˆ°åŽå°æ¨¡åž‹è®¾ç½®ä¸­ä¿å­˜ API Keyã€‚")
    use_responses_api = endpoint.lower().endswith("/responses")
    if use_responses_api:
        payload = {
            "model": model_config["model"],
            "input": messages_to_response_input(messages),
            "temperature": float(model_config.get("temperature", 0.45) if temperature is None else temperature),
            "max_output_tokens": int(max_tokens or model_config.get("max_tokens") or 6000),
        }
    else:
        payload = {
            "model": model_config["model"],
            "messages": messages,
            "temperature": float(model_config.get("temperature", 0.45) if temperature is None else temperature),
        }
        if provider == "minimax":
            payload["max_completion_tokens"] = int(max_tokens or model_config.get("max_tokens") or 6000)
            payload["thinking"] = {"type": "disabled"}
        else:
            payload["max_tokens"] = int(max_tokens or model_config.get("max_tokens") or 6000)
        if provider == "deepseek":
            payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Connection": "close",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{provider_label} è°ƒç”¨å¤±è´¥ï¼šHTTP {exc.code} {detail[:600]}") from exc
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise RuntimeError(f"{provider_label} ç½‘ç»œé”™è¯¯ï¼Œå·²è‡ªåŠ¨é‡è¿ž3æ¬¡ä»å¤±è´¥ï¼š{last_error}") from exc
    if use_responses_api:
        text = response_api_text(data)
        if not text:
            raise RuntimeError(f"{provider_label} è¿”å›žæ ¼å¼å¼‚å¸¸ï¼š{json.dumps(data, ensure_ascii=False)[:600]}")
        return text
    if "choices" not in data or not data["choices"]:
        raise RuntimeError(f"{provider_label} è¿”å›žæ ¼å¼å¼‚å¸¸ï¼š{json.dumps(data, ensure_ascii=False)[:600]}")
    return data["choices"][0]["message"].get("content", "")


def minimax_chat(model_config: dict, messages: list[dict], max_tokens: int | None = None, temperature: float | None = None) -> str:
    return chat_completion(model_config, messages, max_tokens=max_tokens, temperature=temperature)


def strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_json(text: str) -> dict:
    clean = strip_thinking(text)
    clean = re.sub(r"^```(?:json)?", "", clean.strip(), flags=re.IGNORECASE).strip()
    clean = re.sub(r"```$", "", clean.strip()).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start >= 0 and end > start:
            return json.loads(clean[start : end + 1])
        raise


PAPER_OCR_PROMPT = """你是全卷分析 OCR 与阅卷助手。只根据试卷页面识别，不编造。
识别印刷题干、题号、分值、选项、学生手写笔迹、演算过程、红叉/勾/圈画、教师批语和得分。
把页面切分为独立题目；跨页题要标记 continuation=true。无法确认的字符使用 [?]。
判断每题状态：correct、wrong、partial、blank、review_required。低置信度必须使用 review_required。
严格输出 JSON：
{"page_text":"", "page_confidence":0.0, "questions":[{
 "question_no":"1", "printed_text":"", "student_work":"", "teacher_marks":"",
 "answer_state":"review_required", "score":null, "max_score":null,
 "confidence":0.0, "bbox":[0,0,1,1], "continuation":false
}]}
"""


def run_ocr(image_data_url: str, model_id: str | None = None) -> dict:
    if not image_data_url:
        raise ValueError("è¯·å…ˆä¸Šä¼ é¢˜ç›®å›¾ç‰‡")
    with db() as conn:
        model = get_vision_model(conn, model_id)
        prompt = get_prompt(conn, "ocr")
    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": image_data_url,
                "detail": "high",
                "max_long_side_pixel": 1600,
            },
        },
    ]
    raw = minimax_chat(model, [{"role": "user", "content": content}], max_tokens=2500, temperature=0.1)
    result = extract_json(raw)
    result.setdefault("ocr_text", "")
    result.setdefault("confidence", 0.85)
    return result


def diagnose_with_llm(
    question_text: str,
    wrong_answer: str = "",
    image_text: str = "",
    model_id: str | None = None,
    subject: str = "è‡ªåŠ¨è¯†åˆ«",
) -> dict:
    with db() as conn:
        model = get_model(conn, model_id)
        prompt = get_prompt(conn, "diagnosis")
    user_text = f"""ç”¨æˆ·é€‰æ‹©çš„å­¦ç§‘/åœºæ™¯ï¼š
{subject or "è‡ªåŠ¨è¯†åˆ«"}

é¢˜ç›® OCR æ–‡æœ¬ï¼š
{image_text or "(æ— )"}

ç”¨æˆ·ä¿®æ­£åŽçš„é¢˜å¹²ï¼š
{question_text}

å­¦ç”Ÿä½œç­”/é”™è§£/æ‰¹æ³¨/å¡ç‚¹ï¼š
{wrong_answer or "(æœªæä¾›)"}

è¯·æŒ‰æç¤ºè¯å›ºå®š JSON ç»“æž„è¾“å‡ºã€‚"""
    raw = minimax_chat(
        model,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_text},
        ],
        max_tokens=int(model.get("max_tokens") or 7000),
        temperature=float(model.get("temperature") or 0.45),
    )
    result = extract_json(raw)
    result.setdefault("subject", subject or "è‡ªåŠ¨è¯†åˆ«")
    result.setdefault("confidence", 0.75)
    result.setdefault("core_pattern", "å¾…å½’çº³é¢˜åž‹")
    result.setdefault("practice_variants", [])
    result.setdefault("knowledge_points", [])
    result.setdefault(
        "student_answer_analysis",
        {
            "answer_presence": "æœªæä¾›" if not wrong_answer else "å·²æä¾›",
            "extracted_work": wrong_answer,
            "answer_status": "å¾…æ¨¡åž‹è¿›ä¸€æ­¥åˆ¤æ–­" if wrong_answer else "æœªæä¾›ä½œç­”",
            "likely_issue": "" if not wrong_answer else "å·²è®°å½•å­¦ç”Ÿä½œç­”/å¡ç‚¹ï¼Œéœ€ç»“åˆæ‹†é¢˜ç»“æžœåˆ¤æ–­",
            "evidence": [],
            "next_action": "å…ˆè¡¥å……å­¦ç”Ÿä½œç­”æˆ–é”™è§£è¿‡ç¨‹" if not wrong_answer else "å¯¹ç…§æ¨¡åž‹æ­¥éª¤å®šä½æ–­ç‚¹",
        },
    )
    result.setdefault(
        "learning_strategy",
        {
            "decomposition_answer": "å…ˆè¯†åˆ«é¢˜åž‹å’Œé¢˜ç›®ç›®æ ‡ï¼Œå†æ‹†æ¡ä»¶ã€é€‰æ¨¡åž‹ã€æ‰§è¡Œè®¡ç®—æˆ–ä½œç­”ï¼Œæœ€åŽç”¨å°é¢˜éªŒè¯ã€‚",
            "make_it_easier": "å…ˆæŠŠé¢˜ç›®é™é˜¶æˆä¸€ä¸ªæ›´å°çš„åŽŸåž‹é¢˜ï¼Œå†ä»ŽåŽŸåž‹é¢˜è¿ç§»å›žåŽŸé¢˜ã€‚",
            "entry_point": result.get("core_pattern") or result.get("topic") or "é¢˜åž‹å…¥å£",
            "cognitive_ladder": ["çœ‹æ‡‚é¢˜ç›®ç›®æ ‡", "æ‰¾åˆ°å¯å¥—ç”¨çš„æ¨¡åž‹", "å®Œæˆä¸€æ­¥ä¸€éªŒç®—"],
            "micro_drills": ["ç”¨ä¸€å¥è¯è¯´å‡ºé¢˜ç›®ç±»åž‹", "å†™å‡ºç¬¬ä¸€æ­¥æ‹†è§£å…¬å¼æˆ–ç­”é¢˜è§’åº¦"],
            "teacher_hint": "è¿™é“é¢˜ç¬¬ä¸€çœ¼æœ€åƒå“ªä¸€ç±»ä½ å·²ç»åšè¿‡çš„é¢˜ï¼Ÿ",
        },
    )
    return result


def grade_with_llm(variant: dict, answer_text: str, diagnosis: dict | None, model_id: str | None = None) -> dict:
    with db() as conn:
        model = get_model(conn, model_id)
        prompt = get_prompt(conn, "grading")
    user_text = f"""åŽŸé¢˜è¯Šæ–­æ‘˜è¦ï¼š
{json.dumps(diagnosis or {}, ensure_ascii=False)}

å˜å¼é¢˜ï¼š
{variant["stem"]}

å‚è€ƒç­”æ¡ˆï¼š
{variant["answer"]}

å‚è€ƒè§£æžï¼š
{variant["analysis"]}

å­¦ç”Ÿç­”æ¡ˆï¼š
{answer_text}

è¯·æŒ‰ JSON æ ¼å¼æ‰¹æ”¹ã€‚"""
    raw = minimax_chat(
        model,
        [{"role": "system", "content": prompt}, {"role": "user", "content": user_text}],
        max_tokens=2200,
        temperature=0.25,
    )
    result = extract_json(raw)
    result["is_correct"] = bool(result.get("is_correct"))
    result["score"] = int(result.get("score", 0))
    return result


def save_variants(conn: sqlite3.Connection, wrong_id: str, diagnosis: dict) -> list[dict]:
    existing = conn.execute(
        "select * from exercise_variants where wrong_question_id = ? order by level",
        (wrong_id,),
    ).fetchall()
    if existing:
        return [row_to_dict(row) for row in existing]
    variants = diagnosis.get("practice_variants") or []
    saved: list[dict] = []
    for idx, item in enumerate(variants[:3], start=1):
        variant_id = str(uuid.uuid4())
        level = int(item.get("level") or idx)
        title = item.get("title") or ("åŒç»“æž„å·©å›º" if level == 1 else "æ¡ä»¶æ›¿æ¢" if level == 2 else "è¿ç§»æŒ‘æˆ˜")
        conn.execute(
            """
            insert into exercise_variants
            (id, wrong_question_id, level, title, stem, answer, analysis, created_at)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                variant_id,
                wrong_id,
                level,
                title,
                item.get("stem", ""),
                item.get("answer", ""),
                item.get("analysis", ""),
                now_iso(),
            ),
        )
        saved.append(
            {
                "id": variant_id,
                "wrong_question_id": wrong_id,
                "level": level,
                "title": title,
                "stem": item.get("stem", ""),
                "answer": item.get("answer", ""),
                "analysis": item.get("analysis", ""),
                "created_at": now_iso(),
            }
        )
    return saved


def compact_text(value: object, limit: int = 720) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def build_study_card_prompt(item: dict, style: str = "") -> str:
    diagnosis = item.get("diagnosis") or {}
    student = diagnosis.get("student_answer_analysis") or {}
    strategy = diagnosis.get("learning_strategy") or {}
    answer = diagnosis.get("standard_answer") or {}
    decomposition = diagnosis.get("decomposition") or {}
    poem = diagnosis.get("poem") or {}
    variants = item.get("variants") or []
    first_variant = variants[0] if variants else {}
    solution_models = diagnosis.get("solution_models") or []
    first_model = solution_models[0] if solution_models else {}

    traps: list[str] = []
    for model in solution_models:
        traps.extend(model.get("common_mistakes") or [])
    if student.get("likely_issue"):
        traps.insert(0, student.get("likely_issue"))

    step_lines = []
    for idx, step in enumerate((decomposition.get("step_formulas") or [])[:5], start=1):
        step_lines.append(
            f"{idx}. {compact_text(step.get('name'), 30)}ï¼š{compact_text(step.get('formula') or step.get('operation'), 120)}"
        )

    self_checks = [
        "æˆ‘æ˜¯å¦å…ˆè¯†åˆ«é¢˜åž‹å…¥å£ï¼Ÿ",
        "æˆ‘æ˜¯å¦å†™æ¸…å…³é”®å…¬å¼/é‡‡åˆ†ç‚¹ï¼Ÿ",
        "æˆ‘æ˜¯å¦åŒºåˆ†äº†æ˜“æ··æ¦‚å¿µå’Œæœ€ç»ˆç›®æ ‡ï¼Ÿ",
    ]

    payload = {
        "æ ‡é¢˜": f"{diagnosis.get('subject') or 'å…¨ç§‘é¢˜ç›®'}ï½œé”™é¢˜æŒ‡å¯¼å­¦ä¹ è®­ç»ƒå¡ç‰‡",
        "ä¸»é¢˜": diagnosis.get("topic") or diagnosis.get("core_pattern") or "é¢˜ç›®æ‹†è§£è®­ç»ƒ",
        "é”™å› æ ‡ç­¾": (diagnosis.get("knowledge_points") or [])[:3] + traps[:3],
        "é¢˜ç›®": compact_text(diagnosis.get("cleaned_question") or item.get("corrected_text"), 520),
        "ä¸ºä»€ä¹ˆå®¹æ˜“é”™": compact_text(student.get("likely_issue") or "å…¥å£ã€å…¬å¼ã€æ¡ä»¶æˆ–è¡¨è¾¾å®¹æ˜“æ··åœ¨ä¸€èµ·ï¼Œéœ€è¦å…ˆæ‹†é¢˜å†ä½œç­”ã€‚", 260),
        "çº é”™æ€è·¯": step_lines or [compact_text(strategy.get("decomposition_answer"), 260)],
        "è§„èŒƒè§£ç­”": compact_text(answer.get("concise_solution") or answer.get("final_answer"), 620),
        "å…³é”®æé†’": compact_text(strategy.get("make_it_easier") or first_model.get("applies_when"), 220),
        "å˜å¼è®­ç»ƒ": compact_text(first_variant.get("stem") or "æŠŠæ¡ä»¶æ›¿æ¢æˆåŒç»“æž„æ–°é¢˜ï¼Œå…ˆè¯´å…¥å£ï¼Œå†å†™å…³é”®æ­¥éª¤ã€‚", 280),
        "è‡ªæˆ‘å¤ç›˜": self_checks,
        "æ€»ç»“å°è¯—": compact_text("ï¼›".join(poem.get("lines") or []), 180),
    }

    return f"""è¯·ç”Ÿæˆä¸€å¼ ç«–ç‰ˆä¸­æ–‡æ•™è¾…å­¦ä¹ å¡ç‰‡ï¼Œæ¯”ä¾‹ 2:3ï¼Œé€‚åˆæ‰‹æœºä¿å­˜å’Œæ‰“å°ã€‚

è§†è§‰é£Žæ ¼ï¼š
- å‚è€ƒä¸­å›½æ•™è¾…äº§å“çš„æ¸…çˆ½è“ç™½åº•è‰²ï¼Œè¾…ä»¥å°‘é‡æ©™é‡‘æé†’è‰²ï¼›çº¿æ¡å¹²å‡€ï¼Œå±‚çº§æ¸…æ¥šã€‚
- ä¸è¦åšè¥é”€æµ·æŠ¥ï¼Œä¸è¦çœŸå®žæœºæž„ logoï¼Œä¸è¦äºŒç»´ç ï¼Œä¸è¦æ°´å°ã€‚
- ç‰ˆå¼å¿…é¡»åƒä¸€å¼ å®Œæ•´çš„â€œé”™é¢˜æŒ‡å¯¼å­¦ä¹ è®­ç»ƒå¡ç‰‡â€ï¼ŒåŒ…å«ç¼–å· 01 åˆ° 07 çš„ä¸ƒå—å†…å®¹ã€‚
- å°½é‡ä¿æŒä¸­æ–‡æ–‡å­—æ¸…æ™°ï¼Œå…¬å¼ç”¨å¯è¯»çš„æ•°å­¦æŽ’ç‰ˆï¼›å†…å®¹è¿‡é•¿æ—¶å¯ä»¥åŽ‹ç¼©æ‘˜è¦ï¼Œä½†ä¸è¦æ”¹é¢˜æ„ã€‚
- æ¯ä¸ªåŒºå—ç”¨åœ†è§’ 8px ä»¥å†…çš„æ¸…æ™°è¾¹æ¡†æˆ–åˆ†éš”çº¿ï¼Œé¿å…æ–‡å­—é‡å ã€‚

ä¸ƒå—å›ºå®šç»“æž„ï¼š
01 é¢˜ç›®
02 è¿™é“é¢˜ä¸ºä»€ä¹ˆå®¹æ˜“é”™ï¼Ÿ
03 çº é”™æ€è·¯
04 è§„èŒƒè§£ç­”
05 å…³é”®æé†’
06 å˜å¼è®­ç»ƒ
07 è‡ªæˆ‘å¤ç›˜

å¡ç‰‡æ•°æ®ï¼š
{json.dumps(payload, ensure_ascii=False, indent=2)}

é¢å¤–é£Žæ ¼è¦æ±‚ï¼š
{style or "åšæˆä¸“ä¸šã€æ¼‚äº®ã€å¯ä¿¡çš„é«˜è€ƒ/ä¸­è€ƒé”™é¢˜è®­ç»ƒå¡ã€‚"}"""


def call_image_generation(model_config: dict, prompt: str) -> bytes:
    provider = (model_config.get("provider") or "openai").lower()
    compatible_providers = {"openai", "fenno", "openai-compatible", "oneapi", "newapi"}
    if provider not in compatible_providers:
        raise RuntimeError("å½“å‰å›¾ç‰‡ç”Ÿæˆæ”¯æŒ OpenAI å…¼å®¹ Images APIã€‚è¯·æŠŠä¸­è½¬ç«™ provider å¡«ä¸º openaiã€fenno æˆ– openai-compatibleã€‚")
    provider_label = model_config.get("provider") or "openai"
    api_key = (
        model_config.get("api_key")
        or (os.environ.get("FENNO_API_KEY") if provider == "fenno" else "")
        or os.environ.get("OPENAI_IMAGE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(f"{provider_label} å›¾ç‰‡ API Key æœªé…ç½®ï¼Œè¯·åœ¨åŽå°å›¾ç‰‡æ¨¡åž‹é…ç½®ä¸­ä¿å­˜ Keyï¼Œæˆ–åœ¨æœåŠ¡å™¨çŽ¯å¢ƒå˜é‡ä¸­è®¾ç½® FENNO_API_KEY / OPENAI_API_KEYã€‚")

    payload = {
        "model": model_config.get("model") or DEFAULT_OPENAI_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": model_config.get("size") or DEFAULT_OPENAI_IMAGE_SIZE,
    }
    quality = model_config.get("quality") or DEFAULT_OPENAI_IMAGE_QUALITY
    if quality:
        payload["quality"] = quality

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoint = normalize_endpoint(model_config.get("endpoint") or OPENAI_IMAGE_ENDPOINT, "image")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Connection": "close",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{provider_label} å›¾ç‰‡ç”Ÿæˆå¤±è´¥ï¼šHTTP {exc.code} {detail[:800]}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"{provider_label} å›¾ç‰‡ç”Ÿæˆç½‘ç»œé”™è¯¯ï¼š{exc}") from exc

    items = data.get("data") or []
    if not items:
        raise RuntimeError(f"{provider_label} å›¾ç‰‡è¿”å›žä¸ºç©ºï¼š{json.dumps(data, ensure_ascii=False)[:600]}")
    first = items[0]
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"])
    if first.get("url"):
        with urllib.request.urlopen(first["url"], timeout=180) as resp:
            return resp.read()
    raise RuntimeError(f"{provider_label} å›¾ç‰‡è¿”å›žæ ¼å¼å¼‚å¸¸ï¼š{json.dumps(data, ensure_ascii=False)[:600]}")


def generate_study_card(wrong_id: str, image_model_id: str | None = None, style: str = "") -> dict:
    with db() as conn:
        item = get_wrong_question(conn, wrong_id)
        if not item:
            raise ValueError("wrong question not found")
        image_model = get_image_model(conn, image_model_id)

    prompt = build_study_card_prompt(item, style)
    image_bytes = call_image_generation(image_model, prompt)
    card_id = str(uuid.uuid4())
    filename = f"{card_id}.png"
    (CARD_DIR / filename).write_bytes(image_bytes)
    image_url = f"/cards/{filename}"

    with db() as conn:
        conn.execute(
            """
            insert into study_cards
            (id, wrong_question_id, image_model_id, image_url, prompt, model,
             size, quality, status, created_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                wrong_id,
                image_model.get("id"),
                image_url,
                prompt,
                image_model.get("model") or DEFAULT_OPENAI_IMAGE_MODEL,
                image_model.get("size") or DEFAULT_OPENAI_IMAGE_SIZE,
                image_model.get("quality") or DEFAULT_OPENAI_IMAGE_QUALITY,
                "ready",
                now_iso(),
            ),
        )
        row = conn.execute("select * from study_cards where id = ?", (card_id,)).fetchone()
        return row_to_dict(row)


def get_wrong_question(conn: sqlite3.Connection, wrong_id: str) -> dict | None:
    row = conn.execute("select * from wrong_questions where id = ?", (wrong_id,)).fetchone()
    item = row_to_dict(row)
    if not item:
        return None
    variants = conn.execute(
        "select * from exercise_variants where wrong_question_id = ? order by level",
        (wrong_id,),
    ).fetchall()
    item["variants"] = []
    for row in variants:
        variant = row_to_dict(row)
        answer_rows = conn.execute(
            """
            select * from student_answers
            where exercise_variant_id = ?
            order by submitted_at desc
            """,
            (variant["id"],),
        ).fetchall()
        variant["answers"] = [row_to_dict(answer_row) for answer_row in answer_rows]
        item["variants"].append(variant)
    card_rows = conn.execute(
        """
        select * from study_cards
        where wrong_question_id = ?
        order by created_at desc
        """,
        (wrong_id,),
    ).fetchall()
    item["study_cards"] = [row_to_dict(card_row) for card_row in card_rows]
    return item


def clean_subject_name(value: object) -> str:
    subject = str(value or "").strip()
    if not subject or re.fullmatch(r"\?+", subject):
        return "æœªè¯†åˆ«å­¦ç§‘"
    return subject


def profile_items(conn: sqlite3.Connection, user: dict | None) -> dict:
    if not user:
        return {"subjects": [], "items": []}
    wq_where, wq_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    rows = conn.execute(
        f"select id from wrong_questions{wq_where} order by created_at desc",
        wq_params,
    ).fetchall()
    items = []
    subjects: dict[str, int] = {}
    for row in rows:
        item = get_wrong_question(conn, row["id"])
        if not item:
            continue
        diagnosis = item.get("diagnosis") or {}
        subject = clean_subject_name(diagnosis.get("subject"))
        item["subject"] = subject
        subjects[subject] = subjects.get(subject, 0) + 1
        items.append(item)
    return {
        "subjects": [{"name": name, "count": count} for name, count in sorted(subjects.items())],
        "items": items,
    }


def md_escape(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).replace("\r\n", "\n").strip()


def append_list(lines: list[str], title: str, values: list) -> None:
    if not values:
        return
    lines.append(f"### {title}")
    for value in values:
        lines.append(f"- {md_escape(value)}")
    lines.append("")


def build_profile_markdown(conn: sqlite3.Connection, data: dict, user: dict | None) -> dict:
    selections: dict = data.get("selections") or {}
    subject_filter = data.get("subject") or "å…¨éƒ¨å­¦ç§‘"
    if not selections:
        raise ValueError("è¯·è‡³å°‘é€‰æ‹©ä¸€é“é¢˜ç›®")
    if not user:
        raise ValueError("è¯·å…ˆç™»å½•åŽå†å¯¼å‡ºæ¡£æ¡ˆ")

    lines = [
        f"# ä¸ªäººå­¦ä¹ æ¡£æ¡ˆ - {subject_filter}",
        "",
        f"> å¯¼å‡ºæ—¶é—´ï¼š{now_iso()}",
        "> å†…å®¹æ¥æºï¼šOCR é¢˜ç›®ã€AI æ‹†é¢˜ç»“æžœã€å·©å›ºé¢˜ä¸Žæ‰¹æ”¹è®°å½•ã€‚",
        "",
    ]
    exported_count = 0

    for wrong_id, options in selections.items():
        if not options or not any(options.values()):
            continue
        if not user_owns_wrong_question(conn, user, wrong_id):
            continue
        item = get_wrong_question(conn, wrong_id)
        if not item:
            continue
        diagnosis = item.get("diagnosis") or {}
        subject = clean_subject_name(diagnosis.get("subject"))
        if subject_filter != "å…¨éƒ¨å­¦ç§‘" and subject != subject_filter:
            continue

        exported_count += 1
        title = diagnosis.get("core_pattern") or diagnosis.get("topic") or "é¢˜ç›®æ¡£æ¡ˆ"
        lines.extend([f"## {exported_count}. {title}", "", f"- å­¦ç§‘ï¼š{subject}", f"- çŠ¶æ€ï¼š{item.get('status')}", ""])

        if options.get("question"):
            lines.extend(["### é¢˜ç›®", md_escape(item.get("corrected_text")), ""])
        if options.get("ocr") and item.get("ocr_text"):
            lines.extend(["### OCR åŽŸæ–‡", md_escape(item.get("ocr_text")), ""])
        if options.get("student"):
            analysis = diagnosis.get("student_answer_analysis") or {}
            lines.extend(["### ä½œç­”æƒ…å†µ", f"- ä½œç­”å­˜åœ¨ï¼š{md_escape(analysis.get('answer_presence') or ('å·²æä¾›' if item.get('student_wrong_answer') else 'æœªæä¾›'))}"])
            if item.get("student_wrong_answer"):
                lines.append(f"- åŽŸå§‹ä½œç­”/å¡ç‚¹ï¼š{md_escape(item.get('student_wrong_answer'))}")
            if analysis.get("extracted_work"):
                lines.append(f"- ç»“æž„åŒ–ä½œç­”ï¼š{md_escape(analysis.get('extracted_work'))}")
            if analysis.get("answer_status"):
                lines.append(f"- çŠ¶æ€åˆ¤æ–­ï¼š{md_escape(analysis.get('answer_status'))}")
            if analysis.get("likely_issue"):
                lines.append(f"- ä¸»è¦é—®é¢˜ï¼š{md_escape(analysis.get('likely_issue'))}")
            if analysis.get("next_action"):
                lines.append(f"- ä¸‹ä¸€æ­¥ï¼š{md_escape(analysis.get('next_action'))}")
            lines.append("")
        if options.get("answer"):
            answer = diagnosis.get("standard_answer") or {}
            lines.extend(["### ç­”æ¡ˆ", md_escape(answer.get("final_answer") or "æœªè¿”å›žæœ€ç»ˆç­”æ¡ˆ"), ""])
        if options.get("analysis"):
            answer = diagnosis.get("standard_answer") or {}
            lines.extend(["### è§£æž", md_escape(answer.get("concise_solution") or "æœªè¿”å›žæ ‡å‡†è§£æž"), ""])
            decomposition = diagnosis.get("decomposition") or {}
            if decomposition.get("total_formula"):
                lines.extend(["### æ€»æ‹†è§£å…¬å¼", md_escape(decomposition.get("total_formula")), ""])
        if options.get("strategy"):
            strategy = diagnosis.get("learning_strategy") or {}
            lines.extend(["### å­¦ä¹ æ–¹æ³•"])
            if strategy.get("decomposition_answer"):
                lines.append(f"- æ€Žä¹ˆæ‹†è§£ï¼š{md_escape(strategy.get('decomposition_answer'))}")
            if strategy.get("make_it_easier"):
                lines.append(f"- æ€Žä¹ˆæ›´å®¹æ˜“å­¦ï¼š{md_escape(strategy.get('make_it_easier'))}")
            if strategy.get("entry_point"):
                lines.append(f"- å…¥å£ï¼š{md_escape(strategy.get('entry_point'))}")
            if strategy.get("teacher_hint"):
                lines.append(f"- è€å¸ˆå¼•å¯¼ï¼š{md_escape(strategy.get('teacher_hint'))}")
            for step in strategy.get("cognitive_ladder", []) or []:
                lines.append(f"- è®¤çŸ¥å°é˜¶ï¼š{md_escape(step)}")
            for drill in strategy.get("micro_drills", []) or []:
                lines.append(f"- å¾®ç»ƒä¹ ï¼š{md_escape(drill)}")
            lines.append("")
        if options.get("thinking"):
            decomposition = diagnosis.get("decomposition") or {}
            lines.append("### è¯¦ç»†æ€è·¯")
            for step in decomposition.get("step_formulas", []) or []:
                lines.append(f"- **{md_escape(step.get('name'))}**ï¼š{md_escape(step.get('formula'))}")
                if step.get("operation"):
                    lines.append(f"  - æ“ä½œï¼š{md_escape(step.get('operation'))}")
                if step.get("student_trap"):
                    lines.append(f"  - æ˜“é”™ç‚¹ï¼š{md_escape(step.get('student_trap'))}")
            for model in diagnosis.get("solution_models", []) or []:
                lines.append(f"- **æ¨¡åž‹ï¼š{md_escape(model.get('model_name'))}**")
                for step in model.get("steps", []) or []:
                    lines.append(f"  - {md_escape(step)}")
            lines.append("")
        if options.get("multi"):
            lines.append("### ä¸€é¢˜å¤šè§£/å¤šè§†è§’")
            for method in diagnosis.get("multiple_solutions", []) or []:
                lines.append(f"- **{md_escape(method.get('method_name'))}**ï¼š{md_escape(method.get('idea'))}")
                for step in method.get("steps", []) or []:
                    lines.append(f"  - {md_escape(step)}")
                if method.get("pros_cons"):
                    lines.append(f"  - ä¼˜ç¼ºç‚¹ï¼š{md_escape(method.get('pros_cons'))}")
            lines.append("")
        if options.get("poem"):
            poem = diagnosis.get("poem") or {}
            lines.extend([f"### {md_escape(poem.get('title') or 'å¤ç›˜å°è¯—')}"])
            for line in poem.get("lines", []) or []:
                lines.append(f"> {md_escape(line)}")
            for review in poem.get("line_reviews", []) or []:
                lines.append(f"- {md_escape(review.get('line'))}ï¼š{md_escape(review.get('review'))}")
            lines.append("")
        if options.get("similar"):
            lines.append("### åŒç±»é¢˜/å·©å›ºé¢˜")
            for variant in item.get("variants", []) or []:
                lines.append(f"#### ç¬¬ {variant.get('level')} é¢˜ï¼š{md_escape(variant.get('title'))}")
                lines.append(md_escape(variant.get("stem")))
                lines.append("")
                lines.append(f"- ç­”æ¡ˆï¼š{md_escape(variant.get('answer'))}")
                lines.append(f"- è§£æžï¼š{md_escape(variant.get('analysis'))}")
                if variant.get("answers"):
                    latest = variant["answers"][0]
                    grading = latest.get("grading_result") or {}
                    lines.append(f"- æœ€è¿‘ä½œç­”ï¼š{md_escape(latest.get('answer_text'))}")
                    lines.append(f"- æ‰¹æ”¹ï¼š{md_escape(grading.get('comment'))}")
                lines.append("")
        lines.append("---")
        lines.append("")

    if exported_count == 0:
        raise ValueError("æ²¡æœ‰ç¬¦åˆæ¡ä»¶çš„å¯¼å‡ºå†…å®¹")
    filename_subject = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", subject_filter)
    return {
        "filename": f"{filename_subject}_ä¸ªäººå­¦ä¹ æ¡£æ¡ˆ.md",
        "markdown": "\n".join(lines),
        "count": exported_count,
    }


def update_pass_status(conn: sqlite3.Connection, wrong_id: str) -> None:
    wrong = conn.execute(
        "select review_stage from wrong_questions where id = ?", (wrong_id,)
    ).fetchone()
    variants = conn.execute(
        "select id, level from exercise_variants where wrong_question_id = ?", (wrong_id,)
    ).fetchall()
    if len(variants) < 3:
        return
    results = []
    for variant in variants:
        row = conn.execute(
            """
            select is_correct, hint_count from student_answers
            where exercise_variant_id = ?
            order by submitted_at desc limit 1
            """,
            (variant["id"],),
        ).fetchone()
        results.append({
            "level": variant["level"],
            "is_correct": bool(row and row["is_correct"]),
            "hint_count": int(row["hint_count"] or 0) if row else 0,
        })
    state = transition(results, int(wrong["review_stage"] or 0) if wrong else 0)
    public_status = "passed" if state["state"] == "mastered" else state["state"]
    conn.execute(
        """
        update wrong_questions
        set status = ?, workflow_state = ?, mastery_score = ?, review_stage = ?,
            next_review_at = ?, last_reviewed_at = ?
        where id = ?
        """,
        (
            public_status, state["state"], state["mastery_score"], state["review_stage"],
            state["next_review_at"], state["last_reviewed_at"], wrong_id,
        ),
    )


def build_report(conn: sqlite3.Connection, user: dict | None) -> dict:
    empty = {
        "total_wrong_questions": 0,
        "passed_questions": 0,
        "pass_rate": 0,
        "weak_mothers": [],
        "error_causes": [],
    }
    if not user:
        return empty
    wq_where, wq_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    total = conn.execute(f"select count(*) as n from wrong_questions{wq_where}", wq_params).fetchone()["n"]
    passed = conn.execute(
        f"select count(*) as n from wrong_questions{wq_where}{' and' if wq_where else ' where'} status = 'passed'",
        wq_params,
    ).fetchone()["n"]
    pattern_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    for row in conn.execute(f"select diagnosis from wrong_questions{wq_where}", wq_params).fetchall():
        diagnosis = json.loads(row["diagnosis"])
        pattern = diagnosis.get("core_pattern") or diagnosis.get("topic") or "æœªå½’ç±»"
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        answer_status = (diagnosis.get("student_answer_analysis") or {}).get("answer_status") or ""
        if answer_status and answer_status not in {"æœªæä¾›ä½œç­”", "å¾…æ¨¡åž‹è¿›ä¸€æ­¥åˆ¤æ–­", "ç©ºç™½ä¸ä¼š"}:
            issue_counts[answer_status] = issue_counts.get(answer_status, 0) + 1
        for model in diagnosis.get("solution_models", []):
            for mistake in model.get("common_mistakes", []):
                issue_counts[mistake] = issue_counts.get(mistake, 0) + 1
    return {
        "total_wrong_questions": total,
        "passed_questions": passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "weak_mothers": sorted(
            [{"name": name, "count": count} for name, count in pattern_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:5],
        "error_causes": sorted(
            [{"label": label, "count": count} for label, count in issue_counts.items()],
            key=lambda item: item["count"],
            reverse=True,
        )[:5],
    }


def structured_tool_schema(delivery: str) -> str:
    schemas = {
        "docx": """
{
  "title": "æ–‡æ¡£æ ‡é¢˜",
  "summary": "200å­—ä»¥å†…æ‘˜è¦",
  "document_markdown": "å®Œæ•´ Markdown æ­£æ–‡",
  "sections": [
    {
      "title": "ç« èŠ‚æ ‡é¢˜",
      "content": "ç« èŠ‚æ­£æ–‡ï¼Œå¯å«åˆ—è¡¨",
      "questions": [
        {"stem": "é¢˜å¹²", "answer": "ç­”æ¡ˆ", "analysis": "è§£æž"}
      ]
    }
  ]
}""",
        "pptx": """
{
  "title": "è¯¾ä»¶æ ‡é¢˜",
  "summary": "è®²è¯„æ‘˜è¦",
  "slides": [
    {
      "title": "é¡µæ ‡é¢˜",
      "bullets": ["è¦ç‚¹1", "è¦ç‚¹2"],
      "speaker_notes": "è®²è¯„å¤‡æ³¨"
    }
  ],
  "document_markdown": "å®Œæ•´è®²è¯„æçº² Markdown"
}""",
        "report": """
{
  "title": "å·é¢å­¦æƒ…åˆ†æžæŠ¥å‘Š",
  "summary": "æ€»ä½“ç»“è®º",
  "score_overview": {"total_score": "100", "estimated_score": "78", "pass_rate": "78%"},
  "module_analysis": [{"module": "æ¨¡å—å", "score_rate": "65%", "issue": "é—®é¢˜", "action": "æ”¹è¿›åŠ¨ä½œ"}],
  "question_type_analysis": [{"type": "é¢˜åž‹", "loss_points": "å¤±åˆ†ç‚¹", "action": "è®­ç»ƒå»ºè®®"}],
  "weak_knowledge_points": ["è–„å¼±ç‚¹1", "è–„å¼±ç‚¹2"],
  "error_causes": [{"cause": "åŽŸå› ", "evidence": "ä¾æ®", "fix": "ä¿®æ­£æ–¹æ¡ˆ"}],
  "layered_suggestions": {"A": "ä¼˜ç­‰ç”Ÿå»ºè®®", "B": "ä¸­ç­‰ç”Ÿå»ºè®®", "C": "å¾…æå‡å»ºè®®"},
  "action_plan_7d": [{"day": "ç¬¬1å¤©", "tasks": ["ä»»åŠ¡1", "ä»»åŠ¡2"]}],
  "document_markdown": "å®Œæ•´æŠ¥å‘Š Markdownï¼Œå«è¡¨æ ¼ä¸Žåˆ†èŠ‚"
}""",
        "image": """
{
  "title": "é…å›¾æ ‡é¢˜",
  "summary": "é…å›¾è¯´æ˜Ž",
  "image_prompt": "ç”¨äºŽç”Ÿæˆæ•™å­¦é…å›¾çš„è¯¦ç»†ä¸­æ–‡æç¤ºè¯ï¼Œæè¿°å¸ƒå±€ã€å…ƒç´ ã€æ ‡æ³¨ã€é¢œè‰²ã€é£Žæ ¼",
  "caption": "å›¾æ³¨"
}""",
        "map": """
{
  "title": "çŸ¥è¯†å›¾è°±æ ‡é¢˜",
  "summary": "å›¾è°±è¯´æ˜Ž",
  "nodes": [{"label": "æ¦‚å¿µ", "detail": "è§£é‡Š"}],
  "edges": [{"from": "æ¦‚å¿µA", "to": "æ¦‚å¿µB", "label": "å…³ç³»"}],
  "image_prompt": "å¯é€‰ï¼Œç”Ÿæˆå¯è§†åŒ–å›¾è°±é…å›¾çš„æç¤ºè¯",
  "document_markdown": "æ–‡å­—ç‰ˆå›¾è°±è¯´æ˜Ž"
}""",
    }
    return schemas.get(delivery, schemas["docx"])


def structured_to_markdown(data: dict, delivery: str) -> str:
    if data.get("document_markdown"):
        parts = [f"# {data.get('title') or 'ç”Ÿæˆç»“æžœ'}", "", data.get("summary") or "", "", data["document_markdown"]]
        return "\n".join(part for part in parts if part is not None)
    lines = [f"# {data.get('title') or 'ç”Ÿæˆç»“æžœ'}", ""]
    if data.get("summary"):
        lines.extend([str(data["summary"]), ""])
    if delivery == "report":
        overview = data.get("score_overview") or {}
        if overview:
            lines.append("## æˆç»©æ¦‚è§ˆ")
            for key, value in overview.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
        for section_key, title in [
            ("module_analysis", "æ¨¡å—è¯Šæ–­"),
            ("question_type_analysis", "é¢˜åž‹è¯Šæ–­"),
            ("weak_knowledge_points", "è–„å¼±çŸ¥è¯†ç‚¹"),
            ("error_causes", "å¤±åˆ†å½’å› "),
            ("action_plan_7d", "7æ—¥è¡ŒåŠ¨"),
        ]:
            block = data.get(section_key)
            if not block:
                continue
            lines.append(f"## {title}")
            if isinstance(block, list):
                for item in block:
                    lines.append(f"- {json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else item}")
            elif isinstance(block, dict):
                for key, value in block.items():
                    lines.append(f"- {key}: {value}")
            lines.append("")
    if delivery == "pptx":
        lines.append("## è¯¾ä»¶é¡µ")
        for idx, slide in enumerate(data.get("slides") or [], start=1):
            lines.append(f"### ç¬¬{idx}é¡µ {slide.get('title') or ''}")
            for bullet in slide.get("bullets") or []:
                lines.append(f"- {bullet}")
            if slide.get("speaker_notes"):
                lines.append(f"> å¤‡æ³¨ï¼š{slide['speaker_notes']}")
            lines.append("")
    if delivery == "map":
        lines.append("## çŸ¥è¯†èŠ‚ç‚¹")
        for node in data.get("nodes") or []:
            lines.append(f"- **{node.get('label') or ''}**ï¼š{node.get('detail') or ''}")
        lines.append("")
    if data.get("caption"):
        lines.append(f"å›¾æ³¨ï¼š{data['caption']}")
    return "\n".join(lines).strip()


def build_tool_artifacts(conn: sqlite3.Connection, tool: dict, run_id: str, data: dict) -> tuple[list[dict], dict]:
    delivery = tool.get("delivery") or "docx"
    title = data.get("title") or tool.get("label") or "ç”Ÿæˆç»“æžœ"
    safe = export_utils.safe_filename(title, run_id[:8])
    prefix = f"{run_id}_{safe}"
    artifacts: list[dict] = []
    report: dict = {}

    body = data.get("document_markdown") or structured_to_markdown(data, delivery)
    sections = data.get("sections") or []

    if delivery in {"docx", "report"}:
        docx_path = EXPORT_DIR / f"{prefix}.docx"
        if delivery == "report":
            report = {
                "title": title,
                "summary": data.get("summary") or "",
                "score_overview": data.get("score_overview") or {},
                "module_analysis": data.get("module_analysis") or [],
                "question_type_analysis": data.get("question_type_analysis") or [],
                "weak_knowledge_points": data.get("weak_knowledge_points") or [],
                "error_causes": data.get("error_causes") or [],
                "layered_suggestions": data.get("layered_suggestions") or {},
                "action_plan_7d": data.get("action_plan_7d") or [],
            }
            report_sections = []
            if report["score_overview"]:
                report_sections.append({"title": "æˆç»©æ¦‚è§ˆ", "content": "\n".join(f"- {k}: {v}" for k, v in report["score_overview"].items())})
            if report["module_analysis"]:
                report_sections.append({"title": "æ¨¡å—è¯Šæ–­", "content": "\n".join(json.dumps(item, ensure_ascii=False) for item in report["module_analysis"])})
            if report["question_type_analysis"]:
                report_sections.append({"title": "é¢˜åž‹è¯Šæ–­", "content": "\n".join(json.dumps(item, ensure_ascii=False) for item in report["question_type_analysis"])})
            if report["weak_knowledge_points"]:
                report_sections.append({"title": "è–„å¼±çŸ¥è¯†ç‚¹", "content": "\n".join(f"- {x}" for x in report["weak_knowledge_points"])})
            if report["error_causes"]:
                report_sections.append({"title": "å¤±åˆ†å½’å› ", "content": "\n".join(json.dumps(item, ensure_ascii=False) for item in report["error_causes"])})
            if report["layered_suggestions"]:
                report_sections.append({"title": "åˆ†å±‚å»ºè®®", "content": "\n".join(f"- {k}: {v}" for k, v in report["layered_suggestions"].items())})
            if report["action_plan_7d"]:
                report_sections.append({"title": "7æ—¥è¡ŒåŠ¨æ–¹æ¡ˆ", "content": "\n".join(json.dumps(item, ensure_ascii=False) for item in report["action_plan_7d"])})
            if body:
                report_sections.append({"title": "å®Œæ•´æŠ¥å‘Š", "content": body})
            export_utils.write_docx(docx_path, title, body, report_sections)
        else:
            export_utils.write_docx(docx_path, title, body, sections or None)
        artifacts.append(export_utils.artifact_record(docx_path.name, f"/exports/{docx_path.name}", "docx", "ä¸‹è½½ Word"))

    if delivery == "pptx":
        pptx_path = EXPORT_DIR / f"{prefix}.pptx"
        slides = data.get("slides") or []
        if not slides and body:
            slides = [{"title": "è®²è¯„æçº²", "bullets": [line[2:] for line in body.splitlines() if line.strip().startswith("- ")][:8]}]
        export_utils.write_pptx(pptx_path, title, slides)
        artifacts.append(export_utils.artifact_record(pptx_path.name, f"/exports/{pptx_path.name}", "pptx", "ä¸‹è½½ PowerPoint"))

    if delivery in {"docx", "pptx", "report", "map"}:
        md_path = EXPORT_DIR / f"{prefix}.md"
        export_utils.write_markdown(md_path, title, body)
        artifacts.append(export_utils.artifact_record(md_path.name, f"/exports/{md_path.name}", "markdown", "ä¸‹è½½ Markdown"))

    if delivery == "map":
        html_path = EXPORT_DIR / f"{prefix}.html"
        export_utils.write_knowledge_map_html(html_path, title, data.get("nodes") or [], data.get("edges") or [])
        artifacts.append(export_utils.artifact_record(html_path.name, f"/exports/{html_path.name}", "html", "æ‰“å¼€çŸ¥è¯†å›¾è°±"))

    if delivery == "image":
        md_path = EXPORT_DIR / f"{prefix}.md"
        export_utils.write_markdown(md_path, title, body or data.get("summary") or data.get("caption") or "")
        artifacts.append(export_utils.artifact_record(md_path.name, f"/exports/{md_path.name}", "markdown", "ä¸‹è½½è¯´æ˜Ž Markdown"))

    image_prompt = (data.get("image_prompt") or "").strip()
    if delivery in {"image", "map"} and image_prompt:
        image_model = get_image_model(conn)
        image_bytes = call_image_generation(image_model, image_prompt)
        image_path = EXPORT_DIR / f"{prefix}.png"
        image_path.write_bytes(image_bytes)
        artifacts.append(export_utils.artifact_record(image_path.name, f"/exports/{image_path.name}", "image", "ä¸‹è½½é…å›¾ PNG"))

    return artifacts, report


def portal_tool_prompt(tool: dict, subject: str, user_input: str) -> list[dict]:
    delivery = tool.get("delivery") or "docx"
    if delivery == "diagnose":
        delivery = "docx"
    mode_guides = {
        "document": "æ•´ç†é¢˜å·/è¯•å·ä¸ºè§„èŒƒæ–‡æ¡£ç»“æž„ï¼Œä¿®æ­£ OCR æ¢è¡Œï¼Œä¿ç•™é¢˜å·ã€é€‰é¡¹ã€ç­”æ¡ˆåŒºã€è§£æžåŒºã€‚",
        "analysis": "åŸºäºŽå®Œæ•´è¯•å·æˆ–ä½œç­”ææ–™ï¼Œè¾“å‡ºç¬¦åˆæ•™ç ”è§„èŒƒçš„å·é¢å­¦æƒ…è¯Šæ–­ï¼šæˆç»©æ¦‚è§ˆã€æ¨¡å—/é¢˜åž‹è¯Šæ–­ã€å¤±åˆ†å½’å› ã€åˆ†å±‚å»ºè®®ã€7æ—¥è¡ŒåŠ¨ã€‚",
        "variant": "ç”ŸæˆåŒç»“æž„ã€æ¡ä»¶æ›¿æ¢ã€è¿ç§»æŒ‘æˆ˜ä¸‰ç±»å˜å¼é¢˜ï¼Œæ¯é¢˜å¸¦ç­”æ¡ˆä¸Žè§£æžã€‚",
        "question": "å›´ç»•çŸ¥è¯†ç‚¹æ‰¹é‡å‘½é¢˜ï¼ŒæŒ‰åŸºç¡€/æé«˜/åŽ‹è½´åˆ†å±‚ï¼Œæ¯é¢˜å¸¦ç­”æ¡ˆã€è§£æžå’Œæ˜“é”™æé†’ã€‚",
        "wrong": "å¯¹é”™é¢˜åšå½’å› ã€æ‹†é¢˜ã€åŒç±»é¢˜è¿ç§»å’Œå¤ç›˜å»ºè®®ã€‚",
        "image": "æ ¹æ®æ•™å­¦éœ€æ±‚ç”Ÿæˆå¯ç›´æŽ¥ç”¨äºŽè¯¾å ‚çš„é…å›¾ï¼Œå¹¶ç»™å‡ºè¯¦ç»† image_promptã€‚",
        "ppt": "ç”Ÿæˆå¯ç›´æŽ¥æŽˆè¯¾çš„è®²è¯„è¯¾ä»¶ï¼Œè‡³å°‘ 8 é¡µï¼Œå«å…¸åž‹é¢˜ã€äº’åŠ¨æé—®ã€è¯¾åŽç»ƒä¹ ä¸Žè®²è¯„å¤‡æ³¨ã€‚",
        "review": "è¾“å‡ºå®¡é¢˜è®­ç»ƒæ–¹æ¡ˆï¼šå…³é”®è¯ã€éšå«æ¡ä»¶ã€è®¾é—®ç±»åž‹ã€é™·é˜±ã€ç¬¬ä¸€æ­¥åŠ¨ä½œä¸Žç»ƒä¹ é¢˜ã€‚",
        "decompose": "æŠŠå¤§é¢˜æ‹†æˆé‡‡åˆ†ç‚¹ã€å…¬å¼/ææ–™ä¾æ®ã€æ­¥éª¤ã€æ˜“é”™ç‚¹å’Œç­”é¢˜æ¨¡æ¿ã€‚",
        "english": "ç”Ÿæˆè¯æ±‡ç»ƒä¹ å·ï¼šè¯ä¹‰ã€æ‹¼å†™ã€è¯­å¢ƒå¡«ç©ºã€ç¿»è¯‘å’Œç­”æ¡ˆã€‚",
        "coverage": "æ£€æµ‹è€ƒç‚¹è¦†ç›–ï¼šå·²è¦†ç›–ã€é—æ¼ã€é‡å¤ã€éš¾åº¦æ¯”ä¾‹å’Œè¡¥é¢˜å»ºè®®ã€‚",
        "plan": "ç”Ÿæˆå†²åˆºè®¡åˆ’ï¼šç›®æ ‡ã€æ¯æ—¥ä»»åŠ¡ã€é”™é¢˜å¤ç›˜ã€è¾“å‡ºç‰©å’ŒéªŒæ”¶æ ‡å‡†ã€‚",
        "notes": "æ•´ç†è¯¾å ‚ç¬”è®°ï¼šæ¦‚å¿µã€ä¾‹é¢˜ã€æ–¹æ³•ã€æ˜“é”™ç‚¹å’Œè¯¾åŽä»»åŠ¡ã€‚",
        "preview": "ç”Ÿæˆé¢„ä¹ å•ï¼šé¢„ä¹ ç›®æ ‡ã€å…³é”®è¯ã€é—®é¢˜é“¾ã€ä»»åŠ¡å’Œæ£€æŸ¥ã€‚",
        "loss": "åˆ†æžå¤±åˆ†åŽŸå› ï¼šçŸ¥è¯†ã€å®¡é¢˜ã€è¡¨è¾¾ã€è®¡ç®—ã€æ—¶é—´å’Œå¿ƒç†å› ç´ ï¼Œå¹¶ç»™ä¿®æ­£åŠ¨ä½œã€‚",
        "sense": "è¾“å‡ºé¢˜æ„Ÿè®­ç»ƒï¼šåˆ¤åž‹ã€å…¥å£ã€å¸¸ç”¨æ¨¡åž‹å’Œæœ€å°éªŒè¯é¢˜ã€‚",
        "map": "æž„å»ºçŸ¥è¯†ç‚¹å›¾è°±ï¼šèŠ‚ç‚¹ã€å…³ç³»é“¾ã€ä¾‹é¢˜å…¥å£ï¼Œå¹¶ç»™å‡ºå¯è§†åŒ– image_promptã€‚",
        "multi": "ç»™å‡ºå¤šç§è§£æ³•/è§†è§’ï¼Œæ¯”è¾ƒé€‚ç”¨åœºæ™¯ã€ä¼˜ç¼ºç‚¹å’Œè¿ç§»å»ºè®®ã€‚",
        "explain": "ç²¾è®²çŸ¥è¯†ç‚¹ï¼šå®šä¹‰ã€æ¯”å–»ã€ä¾‹é¢˜ã€è¯¯åŒºå’Œå°ç»ƒä¹ ã€‚",
        "writing": "ä¼˜åŒ–ä½œæ–‡/è¡¨è¾¾ï¼šæ”¹è¯ã€å¥å¼å‡çº§ã€æ®µè½å»ºè®®å’Œè¯„åˆ†ç†ç”±ã€‚",
        "score": "æ‹†è§£ç›®æ ‡åˆ†ï¼šåˆ†æ•°å·®è·ã€é¢˜åž‹æ”¶ç›Šã€æ¯æ—¥ç»ƒä¹ å’Œå¤ç›˜èŠ‚ç‚¹ã€‚",
    }
    guide = mode_guides.get(tool.get("mode"), "ç”Ÿæˆå¯ç›´æŽ¥ç”¨äºŽæ•™å­¦æˆ–å­¦ä¹ çš„ç»“æž„åŒ–ç»“æžœã€‚")
    schema = structured_tool_schema(delivery)
    system = f"""ä½ æ˜¯ AIé”™é¢˜æ‹†åšå£« çš„ä¸“ä¸šæ•™ç ”å¼•æ“Žã€‚å½“å‰å·¥å…·ï¼š{tool['label']}ã€‚

è¦æ±‚ï¼š
1. è¾“å‡ºå¿…é¡»æ˜¯åˆæ³• JSONï¼Œä¸è¦ Markdownï¼Œä¸è¦ä»£ç å—ï¼Œä¸è¦é¢å¤–è§£é‡Šã€‚
2. å†…å®¹å¿…é¡»ç¬¦åˆ K12 / ä¸­è€ƒ / é«˜è€ƒ / æœ¬ç¡•åšè§£é¢˜è¾…å¯¼è§„èŒƒï¼Œå¯ç›´æŽ¥äº¤ä»˜æ•™å¸ˆã€å­¦ç”Ÿæˆ–å®¶é•¿ä½¿ç”¨ã€‚
3. ç»“æž„å®Œæ•´ã€ç»“è®ºå…ˆè¡Œã€å»ºè®®å¯æ‰§è¡Œï¼›ç¦æ­¢ç©ºæ³›å¥—è¯ã€‚
4. è‹¥ææ–™ä¸è¶³ï¼Œå¯åˆç†è¡¥å…¨å¹¶å†™å…¥ summaryã€‚

å·¥å…·ä»»åŠ¡ï¼š{guide}

JSON æ ¼å¼ï¼š
{schema}"""
    user = f"""å­¦ç§‘/åœºæ™¯ï¼š{subject or 'è‡ªåŠ¨è¯†åˆ«'}

ç”¨æˆ·ææ–™ï¼š
{user_input}

è¯·ä¸¥æ ¼æŒ‰ JSON æ ¼å¼è¾“å‡ºã€‚"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_portal_tool(conn: sqlite3.Connection, data: dict, user: dict | None) -> dict:
    tool_id = data.get("tool_id") or "knowledge-explain"
    tool = get_portal_tool(tool_id)
    if not tool:
        raise ValueError("å·¥å…·ä¸å­˜åœ¨")
    if tool.get("delivery") == "diagnose":
        raise ValueError("è¯¥å·¥å…·è¯·ä½¿ç”¨é”™é¢˜æ‹†è§£å·¥ä½œå°")
    input_text = (data.get("input_text") or "").strip()
    if not input_text:
        raise ValueError("è¯·å…ˆè¾“å…¥è¦å¤„ç†çš„é¢˜ç›®ã€è¯•å·ã€çŸ¥è¯†ç‚¹æˆ–å­¦ä¹ ææ–™")
    subject = data.get("subject") or "è‡ªåŠ¨è¯†åˆ«"
    model = get_model(conn, data.get("model_id"))
    raw = minimax_chat(
        model,
        portal_tool_prompt(tool, subject, input_text),
        max_tokens=int(model.get("max_tokens") or 7000),
        temperature=float(model.get("temperature") or 0.35),
    )
    structured = extract_json(raw)
    delivery = tool.get("delivery") or "docx"
    output = structured_to_markdown(structured, delivery)
    run_id = str(uuid.uuid4())
    artifacts, report = build_tool_artifacts(conn, tool, run_id, structured)
    if not artifacts:
        raise RuntimeError("æœªèƒ½ç”Ÿæˆå¯ä¸‹è½½æ–‡ä»¶ï¼Œè¯·æ£€æŸ¥æ¨¡åž‹è¿”å›žå†…å®¹")
    user_id = user.get("id") if user else None
    created_at = now_iso()
    conn.execute(
        """
        insert into tool_runs
        (id, tool_id, tool_label, subject, input_text, output_text, model_id, user_id, artifacts, report, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            tool["id"],
            tool["label"],
            subject,
            input_text,
            output,
            model.get("id"),
            user_id,
            json.dumps(artifacts, ensure_ascii=False),
            json.dumps(report, ensure_ascii=False) if report else "",
            created_at,
        ),
    )
    if user_id:
        conn.execute("update app_users set credits = max(credits - 1, 0) where id = ?", (user_id,))
    return {
        "id": run_id,
        "tool_id": tool["id"],
        "tool_label": tool["label"],
        "subject": subject,
        "input_text": input_text,
        "output_text": output,
        "artifacts": artifacts,
        "report": report,
        "model_id": model.get("id"),
        "created_at": created_at,
    }


def rag_user_filter(user: dict | None) -> tuple[str, list]:
    if user and user_is_admin(user):
        return "", []
    if user:
        return " where (user_id = ? or user_id is null or trim(user_id) = '')", [user["id"]]
    return " where (user_id is null or trim(user_id) = '')", []


def chunk_text_for_rag(text: str, max_chars: int = 900, overlap: int = 140) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if not clean:
        return []
    blocks = [part.strip() for part in re.split(r"\n\s*\n", clean) if part.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(block):
                chunks.append(block[start:start + max_chars].strip())
                start += max_chars - overlap
            continue
        if current and len(current) + len(block) + 2 > max_chars:
            chunks.append(current.strip())
            current = current[-overlap:] if overlap and len(current) > overlap else ""
        current = f"{current}\n\n{block}".strip() if current else block
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def fallback_rag_score(query: str, content: str, subject: str = "") -> float:
    q = re.sub(r"\s+", "", query or "").lower()
    c = (content or "").lower()
    if not q or not c:
        return 0.0
    score = 0.0
    for token in re.findall(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}", query or ""):
        if token.lower() in c:
            score += min(4.0, len(token) / 2)
    for i in range(max(0, len(q) - 1)):
        if q[i:i + 2] in c:
            score += 0.08
    if subject and subject != "è‡ªåŠ¨è¯†åˆ«" and subject in content:
        score += 1.5
    return score


def public_rag_document(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "filename": item.get("filename"),
        "subject": clean_subject_name(item.get("subject")),
        "source_type": item.get("source_type"),
        "chars": int(item.get("chars") or 0),
        "created_at": item.get("created_at"),
    }


def create_rag_document(conn: sqlite3.Connection, data: dict, user: dict | None) -> dict:
    filename = data.get("filename") or "paste.txt"
    subject = clean_subject_name(data.get("subject") or "è‡ªåŠ¨è¯†åˆ«")
    title = (data.get("title") or Path(filename).stem or "çŸ¥è¯†èµ„æ–™").strip()[:120]
    text = (data.get("text") or "").strip()
    source_type = "paste"
    if data.get("file_data_url"):
        extracted = extract_document_from_data_url(filename, data.get("file_data_url") or "")
        text = (extracted.get("text") or "").strip()
        filename = extracted.get("filename") or filename
        title = (data.get("title") or Path(filename).stem or title).strip()[:120]
        source_type = "file"
    if len(text) < 20:
        raise ValueError("èµ„æ–™å†…å®¹å¤ªçŸ­ï¼Œæ— æ³•å…¥åº“æ£€ç´¢")
    doc_id = str(uuid.uuid4())
    user_id = user["id"] if user else None
    created_at = now_iso()
    chunks = chunk_text_for_rag(text)
    if not chunks:
        raise ValueError("æœªèƒ½åˆ‡åˆ†å‡ºæœ‰æ•ˆçŸ¥è¯†ç‰‡æ®µ")
    conn.execute(
        """
        insert into rag_documents (id, user_id, title, filename, subject, source_type, chars, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (doc_id, user_id, title, filename, subject, source_type, len(text), created_at),
    )
    saved_chunks = []
    for index, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        conn.execute(
            """
            insert into rag_chunks (id, document_id, user_id, chunk_index, title, subject, content, chars, created_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chunk_id, doc_id, user_id, index, title, subject, chunk, len(chunk), created_at),
        )
        try:
            conn.execute(
                "insert into rag_chunks_fts (chunk_id, document_id, user_id, title, subject, content) values (?, ?, ?, ?, ?, ?)",
                (chunk_id, doc_id, user_id or "", title, subject, chunk),
            )
        except sqlite3.OperationalError:
            pass
        saved_chunks.append({"id": chunk_id, "index": index, "chars": len(chunk)})
    return {
        "id": doc_id,
        "title": title,
        "filename": filename,
        "subject": subject,
        "source_type": source_type,
        "chars": len(text),
        "chunk_count": len(saved_chunks),
        "created_at": created_at,
    }


def search_rag(conn: sqlite3.Connection, query: str, subject: str = "", user: dict | None = None, limit: int = 5) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(int(limit or 5), 12))
    subject = clean_subject_name(subject or "è‡ªåŠ¨è¯†åˆ«")
    user_clause, params = rag_user_filter(user)
    base_where = user_clause.replace(" where ", "") if user_clause else "1=1"
    subject_sql = ""
    subject_params: list = []
    if subject and subject != "è‡ªåŠ¨è¯†åˆ«":
        subject_sql = " and (subject = ? or subject = 'è‡ªåŠ¨è¯†åˆ«' or subject is null or trim(subject) = '')"
        subject_params.append(subject)
    candidates: list[dict] = []
    try:
        fts_query = " OR ".join(re.findall(r"[0-9A-Za-z_]+|[\u4e00-\u9fff]{2,}", query)) or query
        rows = conn.execute(
            f"""
            select c.*, bm25(rag_chunks_fts) as rank
            from rag_chunks_fts
            join rag_chunks c on c.id = rag_chunks_fts.chunk_id
            where rag_chunks_fts match ? and {base_where}{subject_sql}
            order by rank limit ?
            """,
            [fts_query, *params, *subject_params, limit * 3],
        ).fetchall()
        for row in rows:
            item = row_to_dict(row)
            item["score"] = round(100 / (1 + abs(float(row["rank"] or 0))), 2)
            candidates.append(item)
    except sqlite3.OperationalError:
        candidates = []
    if len(candidates) < limit:
        rows = conn.execute(
            f"select * from rag_chunks where {base_where}{subject_sql} order by created_at desc limit 200",
            [*params, *subject_params],
        ).fetchall()
        seen = {item.get("id") for item in candidates}
        fallback = []
        for row in rows:
            item = row_to_dict(row)
            if item.get("id") in seen:
                continue
            score = fallback_rag_score(query, f"{item.get('title')}\n{item.get('subject')}\n{item.get('content')}", subject)
            if score > 0:
                item["score"] = round(score, 2)
                fallback.append(item)
        fallback.sort(key=lambda item: item.get("score", 0), reverse=True)
        candidates.extend(fallback[:limit * 2])
    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    results = []
    for item in candidates[:limit]:
        results.append({
            "id": item.get("id"),
            "document_id": item.get("document_id"),
            "chunk_index": item.get("chunk_index"),
            "title": item.get("title"),
            "subject": clean_subject_name(item.get("subject")),
            "content": item.get("content"),
            "score": item.get("score", 0),
            "created_at": item.get("created_at"),
        })
    return results


def build_rag_context_for_prompt(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"ã€èµ„æ–™{index}ï½œ{chunk.get('title') or 'çŸ¥è¯†ç‰‡æ®µ'}ï½œ{chunk.get('subject') or 'æœªæ ‡æ³¨'}ï½œç›¸å…³åº¦{chunk.get('score', 0)}ã€‘\n{compact_text(chunk.get('content'), 900)}"
        )
    return "\n\n".join(blocks)


def generate_rag_quiz_from_hits(topic: str, hits: list[dict], count: int = 5) -> dict:
    topic = compact_text(topic or "综合复习", 80)
    questions = []
    for index, hit in enumerate(hits[:count], start=1):
        title = hit.get("title") or "知识资料"
        content = compact_text(hit.get("content"), 180)
        short = index % 2 == 0
        questions.append({
            "type": "short" if short else "single",
            "question": f"根据资料《{title}》，请判断或说明：{topic} 中最容易出错的关键点是什么？",
            "options": [] if short else [
                compact_text(content, 48),
                "只背题干，不需要理解条件",
                "不需要引用资料证据",
                "可以忽略错因复盘",
            ],
            "answer": content,
            "analysis": "答案应紧扣资料证据，并能说出这个知识点对应的错因、题型入口和训练动作。",
            "source": title,
        })
    if not questions:
        questions.append({
            "type": "short",
            "question": f"围绕“{topic}”，请先上传教材、错题总结或课堂笔记，再生成基于证据的自测题。",
            "options": [],
            "answer": "当前 RAG 未命中资料。",
            "analysis": "系统需要先有资料片段，才能可靠出题。",
            "source": "RAG 知识库",
        })
    return {"topic": topic, "questions": questions, "citations": hits, "ai_ready": False}


def generate_rag_study_os(topic: str, hits: list[dict]) -> dict:
    topic = compact_text(topic or "综合自学", 80)
    plan = []
    cards = []
    hints = []
    review = []
    for index, hit in enumerate(hits[:6], start=1):
        title = hit.get("title") or f"{topic}资料{index}"
        content = compact_text(hit.get("content"), 220)
        plan.append({
            "title": f"第{index}步：吃透《{title}》",
            "goal": f"先复述资料，再标出题型入口、易错条件和标准动作：{content}",
            "evidence": title,
        })
        cards.append({
            "front": title,
            "back": content,
            "source": title,
        })
        hints.append({
            "question": f"《{title}》对应的错题突破入口是什么？",
            "try_first": "先遮住解析，用 2 句话写出自己的判断。",
            "hint": "从题型、条件、目标、常见错因四个角度找。",
            "answer": content,
        })
        review.append({
            "mistake": f"把《{title}》当成孤立知识点背诵",
            "fix": "订正时写清：我错在哪里、正确入口是什么、下一道同类题先看什么。",
        })
    if not hits:
        plan.append({
            "title": "先建设错题资料库",
            "goal": "上传错题总结、教材、讲义或评分标准，系统会切片进入 RAG，再生成自学方案。",
            "evidence": "暂无 RAG 命中",
        })
    return {
        "topic": topic,
        "plan": plan,
        "flashcards": cards,
        "hints": hints,
        "review": review,
        "citations": hits,
        "ai_ready": False,
    }


def normalize_agent_result(result: dict, question_text: str, subject: str, student_answer: str) -> dict:
    if not isinstance(result, dict):
        result = {}
    subject_name = result.get("subject") or subject or "è‡ªåŠ¨è¯†åˆ«"
    structured = result.get("structured_question") or {}
    quick = result.get("quick_answer") or {}
    result.setdefault("title", compact_text(structured.get("target") or result.get("question_type") or question_text, 42))
    result.setdefault("subject", subject_name)
    result.setdefault("question_type", result.get("question_type") or "å¾…å½’çº³é¢˜åž‹")
    result.setdefault("difficulty", 3)
    result.setdefault("confidence", 0.72)
    result["quick_answer"] = {
        "how_to_decompose": quick.get("how_to_decompose") or "å…ˆè¯†åˆ«å­¦ç§‘ä¸Žé¢˜åž‹ï¼Œå†æ‹†å·²çŸ¥æ¡ä»¶ã€è®¾é—®ç›®æ ‡ã€å¯ç”¨æ¨¡åž‹ã€æ‰§è¡Œæ­¥éª¤å’Œæ ¡éªŒåŠ¨ä½œã€‚",
        "make_it_easier": quick.get("make_it_easier") or "å…ˆåšä¸€ä¸ªæ›´å°çš„åŽŸåž‹é¢˜ï¼ŒæŠŠæ ¸å¿ƒæ­¥éª¤ç»ƒç†Ÿï¼Œå†è¿ç§»å›žåŽŸé¢˜ã€‚",
        "first_entry": quick.get("first_entry") or result.get("question_type") or "é¢˜åž‹å…¥å£",
    }
    structured.setdefault("cleaned_question", question_text)
    structured.setdefault("known_conditions", [])
    structured.setdefault("target", result.get("title") or "é¢˜ç›®ç›®æ ‡")
    structured.setdefault("hidden_constraints", [])
    structured.setdefault("student_work", student_answer or "")
    result["structured_question"] = structured
    answer_analysis = result.get("student_answer_analysis") or {}
    answer_analysis.setdefault("answer_presence", "å·²æä¾›" if student_answer else "æœªæä¾›")
    answer_analysis.setdefault("answer_status", "å¾…æ¨¡åž‹è¿›ä¸€æ­¥åˆ¤æ–­" if student_answer else "æœªæä¾›ä½œç­”")
    answer_analysis.setdefault("likely_issue", "æ ¹æ®å­¦ç”Ÿä½œç­”å®šä½é”™å› " if student_answer else "æœªæä¾›ä½œç­”ï¼Œæš‚ä¸åˆ¤æ–­é”™å› ")
    answer_analysis.setdefault("evidence", [])
    answer_analysis.setdefault("next_action", "å¯¹ç…§åˆ†å±‚æ­¥éª¤å¤ç›˜" if student_answer else "å¯è¡¥å……å­¦ç”Ÿä½œç­”åŽå†è¯Šæ–­")
    result["student_answer_analysis"] = answer_analysis
    result.setdefault("solution_model", {
        "model_name": "è¯†åˆ«é¢˜åž‹-æ‹†æ¡ä»¶-é€‰æ¨¡åž‹-æ‰§è¡Œ-æ ¡éªŒ-å¤ç›˜æ¨¡åž‹",
        "applies_when": "é€‚ç”¨äºŽé«˜è€ƒå…¨ç§‘é¢˜ç›®çš„é€šç”¨æ‹†è§£",
        "step_formula": "è¯†åˆ«é¢˜åž‹â†’æ‹†æ¡ä»¶â†’é€‰æ¨¡åž‹â†’æ‰§è¡Œâ†’æ ¡éªŒâ†’å¤ç›˜",
        "steps": ["è¯†åˆ«å…¥å£", "æ‹†åˆ†æ¡ä»¶", "é€‰æ‹©æ¨¡åž‹", "è§„èŒƒä½œç­”", "åå‘æ ¡éªŒ"],
        "checkpoints": ["ç­”æ¡ˆæ˜¯å¦å›žç­”è®¾é—®", "æ­¥éª¤æ˜¯å¦æœ‰ä¾æ®"],
    })
    result.setdefault("multiple_solutions", [])
    result.setdefault("standard_solution", "æ¨¡åž‹æœªè¿”å›žæ ‡å‡†è§£æžï¼Œè¯·é‡æ–°ç”Ÿæˆæˆ–è¡¥å……é¢˜å¹²ã€‚")
    result.setdefault("final_answer", "æ¨¡åž‹æœªè¿”å›žæœ€ç»ˆç­”æ¡ˆã€‚")
    result.setdefault("score_points", [])
    result.setdefault("common_mistakes", [])
    result.setdefault("training_tasks", [])
    result.setdefault("mother_question_reserved", {
        "status": "prompt_reserved",
        "name": result.get("question_type") or "é¢˜åž‹åŽŸåž‹å¾…æ²‰æ·€",
        "abstract_pattern": "åŽç»­æŽ¥å…¥æ¯é¢˜åº“åŽæ²‰æ·€",
        "future_interface_hint": "åŽç»­æŽ¥å…¥ /api/mother-questions æˆ– RAG",
    })
    result.setdefault("fun_analogy", {"theme": "æ‹†é¢˜è·¯çº¿å›¾", "overview": "æŠŠé¢˜ç›®å½“æˆä¸€æ¡ä»»åŠ¡æµæ°´çº¿é€å±‚æ‹†å¼€ã€‚", "steps": []})
    result.setdefault("poem", {"title": "è§£é¢˜å¤ç›˜è¯€", "lines": [], "line_reviews": []})
    result.setdefault("archive_payload", {
        "subject": subject_name,
        "question": question_text,
        "answer": result.get("final_answer"),
        "analysis": result.get("standard_solution"),
        "detailed_thinking": result.get("quick_answer", {}).get("how_to_decompose"),
        "similar_questions": [task.get("stem") for task in result.get("training_tasks", []) if isinstance(task, dict) and task.get("stem")],
        "tags": [result.get("question_type") or "é¢˜åž‹å¾…å½’çº³"],
    })

    existing_layers = {}
    for layer in result.get("layers") or []:
        if isinstance(layer, dict) and layer.get("key"):
            existing_layers[layer["key"]] = layer
    normalized_layers = []
    for template in AGENT_LAYERS:
        layer = existing_layers.get(template["key"], {})
        normalized_layers.append({
            "key": template["key"],
            "name": layer.get("name") or template["name"],
            "status": layer.get("status") or "done",
            "summary": layer.get("summary") or template["role"],
            "input": layer.get("input") or compact_text(question_text, 120),
            "output": layer.get("output") or layer.get("summary") or template["role"],
            "quality_gate": layer.get("quality_gate") or template["quality_gate"],
            "next_action": layer.get("next_action") or "è¿›å…¥ä¸‹ä¸€å±‚å¤„ç†",
        })
    result["layers"] = normalized_layers
    return result


def agent_prompt_messages(subject: str, question_text: str, student_answer: str, rag_context: str = "") -> list[dict]:
    layer_spec = "\n".join(f"- {layer['key']}: {layer['name']}ï½œ{layer['role']}ï½œè´¨æ£€ï¼š{layer['quality_gate']}" for layer in AGENT_LAYERS)
    user = f"""å­¦ç§‘ï¼š{subject or 'è‡ªåŠ¨è¯†åˆ«'}

é¢˜ç›®ï¼š
{question_text}

å­¦ç”Ÿä½œç­”/æ‰¹æ³¨/å¡ç‚¹ï¼š
{student_answer or 'æœªæä¾›'}

RAG æ£€ç´¢èµ„æ–™ï¼š
{rag_context or 'æœªå¯ç”¨æˆ–æœªæ£€ç´¢åˆ°ç›¸å…³èµ„æ–™ã€‚'}

è¦æ±‚ï¼šå¦‚æžœ RAG æ£€ç´¢èµ„æ–™ä¸ä¸ºç©ºï¼Œè¯·ä¼˜å…ˆæŠŠèµ„æ–™ä½œä¸ºä¾æ®ï¼Œä½†å¿…é¡»è‡ªè¡Œæ ¡éªŒèµ„æ–™æ˜¯å¦é€‚ç”¨äºŽæœ¬é¢˜ï¼›è‹¥èµ„æ–™ä¸Žé¢˜ç›®å†²çªï¼Œè¦è¯´æ˜Žâ€œèµ„æ–™ä¸é€‚ç”¨/éœ€è°¨æ…Žâ€ã€‚è¾“å‡º JSON ä¸­å¿…é¡»å†™å…¥ rag_context å­—æ®µï¼ŒåŒ…å« usedã€evidence_countã€citationsã€how_usedã€‚

æ™ºèƒ½ä½“å±‚æ¬¡æ¸…å•ï¼š
{layer_spec}

è¯·ä¸¥æ ¼æŒ‰ AGENT_SOLVE_PROMPT çš„ JSON æ ¼å¼è¾“å‡ºã€‚"""
    return [{"role": "system", "content": AGENT_SOLVE_PROMPT}, {"role": "user", "content": user}]


def solve_with_agent(conn: sqlite3.Connection, data: dict, user: dict | None) -> dict:
    question_text = (data.get("question_text") or "").strip()
    if not question_text:
        raise ValueError("è¯·å…ˆè¾“å…¥é¢˜ç›®å†…å®¹")
    subject = (data.get("subject") or "è‡ªåŠ¨è¯†åˆ«").strip()
    student_answer = (data.get("student_answer") or data.get("student_wrong_answer") or "").strip()
    model = get_model(conn, data.get("model_id"))
    use_rag = data.get("use_rag", True) is not False
    rag_hits = search_rag(conn, "\n".join([subject, question_text, student_answer]), subject, user, int(data.get("rag_limit") or 5)) if use_rag else []
    rag_context = build_rag_context_for_prompt(rag_hits)
    raw = minimax_chat(
        model,
        agent_prompt_messages(subject, question_text, student_answer, rag_context),
        max_tokens=int(model.get("max_tokens") or 8000),
        temperature=float(model.get("temperature") or 0.28),
    )
    structured = normalize_agent_result(extract_json(raw), question_text, subject, student_answer)
    structured["rag_context"] = {
        "used": bool(rag_hits),
        "evidence_count": len(rag_hits),
        "citations": [
            {
                "chunk_id": item.get("id"),
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "subject": item.get("subject"),
                "score": item.get("score"),
                "excerpt": compact_text(item.get("content"), 180),
            }
            for item in rag_hits
        ],
        "how_used": structured.get("rag_context", {}).get("how_used") if isinstance(structured.get("rag_context"), dict) else "å·²ä½œä¸ºè§£é¢˜ä¾æ®æ³¨å…¥æç¤ºè¯" if rag_hits else "æœªæ£€ç´¢åˆ°å¯ç”¨èµ„æ–™",
    }
    run_id = str(uuid.uuid4())
    created_at = now_iso()
    user_id = user["id"] if user else None
    conn.execute(
        """
        insert into agent_runs
        (id, user_id, subject, question_text, student_answer, model_id, result, status, created_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            user_id,
            clean_subject_name(structured.get("subject") or subject),
            question_text,
            student_answer,
            model.get("id"),
            json.dumps(structured, ensure_ascii=False),
            "completed",
            created_at,
        ),
    )
    return {
        "id": run_id,
        "user_id": user_id,
        "subject": clean_subject_name(structured.get("subject") or subject),
        "question_text": question_text,
        "student_answer": student_answer,
        "model_id": model.get("id"),
        "result": structured,
        "status": "completed",
        "created_at": created_at,
    }


def user_owns_agent_run(user: dict | None, run: dict | None) -> bool:
    if not run:
        return False
    if not run.get("user_id"):
        return True
    if not user:
        return False
    if user_is_admin(user):
        return True
    return run.get("user_id") == user.get("id")


def history_item(item_id: str, item_type: str, label: str, title: str, summary: str, created_at: str, **extra) -> dict:
    row = {
        "id": item_id,
        "type": item_type,
        "label": label,
        "title": title or label,
        "summary": compact_text(summary, 220),
        "created_at": created_at or "",
    }
    row.update(extra)
    return row


def build_generation_history(conn: sqlite3.Connection, user: dict | None) -> dict:
    if not user:
        return {"items": [], "counts": {}, "total": 0}

    wq_where, wq_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    join_where, join_params = ("", []) if user_is_admin(user) else (" where w.user_id = ?", [user["id"]])
    tool_where, tool_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    export_where, export_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    agent_where, agent_params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])

    items: list[dict] = []
    for row in conn.execute(
        f"select * from wrong_questions{wq_where} order by created_at desc",
        wq_params,
    ).fetchall():
        item = row_to_dict(row)
        diagnosis = item.get("diagnosis") or {}
        items.append(history_item(
            f"diagnosis:{item['id']}", "diagnosis", "AIæ‹†é¢˜",
            diagnosis.get("core_pattern") or diagnosis.get("topic") or "é¢˜ç›®æ‹†è§£",
            item.get("corrected_text") or "", item.get("created_at"),
            wrong_question_id=item["id"], subject=clean_subject_name(diagnosis.get("subject")), status=item.get("status"),
            institution_id=item.get("institution_id"), institution_name=item.get("institution_name"), institution_badge=item.get("institution_badge"),
        ))
    for row in conn.execute(f"""
        select v.*, w.diagnosis from exercise_variants v
        join wrong_questions w on w.id = v.wrong_question_id
        {join_where}
        order by v.created_at desc
    """, join_params).fetchall():
        variant = row_to_dict(row)
        diagnosis = variant.get("diagnosis") or {}
        items.append(history_item(
            f"variant:{variant['id']}", "variant", "åŒç±»å˜å¼",
            f"ç¬¬ {variant.get('level')} é¢˜ï¼š{variant.get('title')}", variant.get("stem") or "", variant.get("created_at"),
            wrong_question_id=variant.get("wrong_question_id"), subject=clean_subject_name(diagnosis.get("subject")),
        ))
    for row in conn.execute(f"""
        select a.*, v.title, v.wrong_question_id, w.diagnosis
        from student_answers a
        join exercise_variants v on v.id = a.exercise_variant_id
        join wrong_questions w on w.id = v.wrong_question_id
        {join_where}
        order by a.submitted_at desc
    """, join_params).fetchall():
        answer = row_to_dict(row)
        grading = answer.get("grading_result") or {}
        diagnosis = answer.get("diagnosis") or {}
        items.append(history_item(
            f"grading:{answer['id']}", "grading", "AIæ‰¹æ”¹", answer.get("title") or "å˜å¼æ‰¹æ”¹",
            grading.get("comment") or grading.get("detected_issue") or answer.get("answer_text") or "", answer.get("submitted_at"),
            wrong_question_id=answer.get("wrong_question_id"), subject=clean_subject_name(diagnosis.get("subject")),
            score=grading.get("score"), is_correct=bool(answer.get("is_correct")),
        ))
    for row in conn.execute(f"""
        select c.*, w.diagnosis from study_cards c
        join wrong_questions w on w.id = c.wrong_question_id
        {join_where}
        order by c.created_at desc
    """, join_params).fetchall():
        card = row_to_dict(row)
        diagnosis = card.get("diagnosis") or {}
        items.append(history_item(
            f"card:{card['id']}", "card", "å­¦ä¹ å¡ç‰‡",
            diagnosis.get("core_pattern") or diagnosis.get("topic") or "é”™é¢˜è®­ç»ƒå¡",
            f"{card.get('model')} Â· {card.get('size')} Â· {card.get('quality')}", card.get("created_at"),
            wrong_question_id=card.get("wrong_question_id"), subject=clean_subject_name(diagnosis.get("subject")), image_url=card.get("image_url"),
        ))
    for row in conn.execute(
        f"select * from tool_runs{tool_where} order by created_at desc",
        tool_params,
    ).fetchall():
        run = row_to_dict(row)
        items.append(history_item(
            f"tool:{run['id']}", "tool", run.get("tool_label") or "AIå·¥å…·", run.get("tool_label") or "å·¥å…·ç”Ÿæˆ",
            run.get("output_text") or run.get("input_text") or "", run.get("created_at"),
            tool_run_id=run.get("id"), tool_id=run.get("tool_id"), subject=clean_subject_name(run.get("subject")),
        ))
    for row in conn.execute(
        f"select * from agent_runs{agent_where} order by created_at desc",
        agent_params,
    ).fetchall():
        run = row_to_dict(row)
        result = run.get("result") or {}
        quick = result.get("quick_answer") or {}
        items.append(history_item(
            f"agent:{run['id']}", "agent", "è§£é¢˜æ™ºèƒ½ä½“", result.get("title") or result.get("question_type") or "åˆ†å±‚è§£é¢˜",
            quick.get("how_to_decompose") or result.get("standard_solution") or run.get("question_text") or "",
            run.get("created_at"),
            agent_run_id=run.get("id"), subject=clean_subject_name(result.get("subject") or run.get("subject")),
            status=run.get("status"),
        ))
    for row in conn.execute(
        f"select * from profile_exports{export_where} order by created_at desc",
        export_params,
    ).fetchall():
        export = row_to_dict(row)
        items.append(history_item(
            f"profile_export:{export['id']}", "profile_export", "æ¡£æ¡ˆå¯¼å‡º", export.get("filename") or "ä¸ªäººå­¦ä¹ æ¡£æ¡ˆ",
            f"{export.get('subject')} Â· {export.get('count')} é“é¢˜", export.get("created_at"),
            export_id=export.get("id"), subject=clean_subject_name(export.get("subject")),
        ))
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return {"items": items, "counts": counts, "total": len(items)}


def institution_context_for_app_user(user: dict | None) -> dict:
    if not user:
        return {}
    store = org_inst_store.load_store()
    email = str(user.get("email") or "").strip()
    member = org_inst_store.find_member_by_username(store, email)
    if not member:
        return {}
    inst = org_inst_store.get_institution_by_id(store, member.get("institution_id"))
    return {
        "institution_id": member.get("institution_id") or "",
        "institution_name": member.get("institution_name") or (inst or {}).get("name") or "",
        "institution_badge": member.get("institution_badge") or (inst or {}).get("name") or "",
    }


def masked_email(value: str | None) -> str:
    email = (value or "").strip()
    if "@" not in email:
        return "å­¦ä¹ è€…"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        shown = name[:1] + "*"
    else:
        shown = name[:2] + "***" + name[-1:]
    return f"{shown}@{domain}"


def public_profile_share(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    try:
        permissions = json.loads(item.get("permissions") or "{}")
    except json.JSONDecodeError:
        permissions = {}
    return {
        "id": item.get("id"),
        "token": item.get("token"),
        "title": item.get("title"),
        "audience": item.get("audience") or "å®¶æ•™/å®¶é•¿/æ•™åŠ¡",
        "note": item.get("note") or "",
        "status": item.get("status"),
        "permissions": permissions,
        "created_at": item.get("created_at"),
        "last_viewed_at": item.get("last_viewed_at"),
        "expires_at": item.get("expires_at"),
    }


def create_profile_share(conn: sqlite3.Connection, data: dict, user: dict | None) -> dict:
    if not user:
        raise PermissionError("è¯·å…ˆç™»å½•åŽå†åˆ›å»ºå…±äº«é“¾æŽ¥")
    title = (data.get("title") or "å­¦ä¹ çŠ¶æ€å…±äº«").strip()[:80]
    audience = (data.get("audience") or "å®¶æ•™/å®¶é•¿/æ•™åŠ¡").strip()[:80]
    note = (data.get("note") or "").strip()[:300]
    permissions = data.get("permissions") or {
        "report": True,
        "profile": True,
        "history": True,
        "questions": True,
        "auth_required": False,
    }
    share_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)
    conn.execute(
        """
        insert into profile_shares
        (id, token, user_id, title, audience, note, status, permissions, created_at, expires_at)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            share_id,
            token,
            user["id"],
            title,
            audience,
            note,
            "active",
            json.dumps(permissions, ensure_ascii=False),
            now_iso(),
            (data.get("expires_at") or "").strip(),
        ),
    )
    row = conn.execute("select * from profile_shares where id = ?", (share_id,)).fetchone()
    return public_profile_share(row)


def list_profile_shares(conn: sqlite3.Connection, user: dict | None) -> list[dict]:
    if not user:
        return []
    where, params = ("", []) if user_is_admin(user) else (" where user_id = ?", [user["id"]])
    rows = conn.execute(f"select * from profile_shares{where} order by created_at desc", params).fetchall()
    return [public_profile_share(row) for row in rows]


def revoke_profile_share(conn: sqlite3.Connection, share_id: str, user: dict | None) -> dict:
    if not user:
        raise PermissionError("unauthorized")
    row = conn.execute("select * from profile_shares where id = ?", (share_id,)).fetchone()
    if not row:
        raise ValueError("å…±äº«é“¾æŽ¥ä¸å­˜åœ¨")
    item = dict(row)
    if not user_is_admin(user) and item.get("user_id") != user.get("id"):
        raise PermissionError("æ— æƒæ“ä½œè¯¥å…±äº«é“¾æŽ¥")
    conn.execute("update profile_shares set status = ? where id = ?", ("revoked", share_id))
    row = conn.execute("select * from profile_shares where id = ?", (share_id,)).fetchone()
    return public_profile_share(row)


def build_public_share_payload(conn: sqlite3.Connection, token: str, viewer: dict | None = None) -> dict:
    row = conn.execute("select * from profile_shares where token = ?", (token,)).fetchone()
    if not row:
        raise ValueError("å…±äº«é“¾æŽ¥ä¸å­˜åœ¨")
    share = public_profile_share(row)
    if share.get("status") != "active":
        raise PermissionError("å…±äº«é“¾æŽ¥å·²å…³é—­")
    expires_at = (share.get("expires_at") or "").strip()
    if expires_at and expires_at < now_iso():
        raise PermissionError("å…±äº«é“¾æŽ¥å·²è¿‡æœŸ")
    owner = conn.execute("select * from app_users where id = ?", (dict(row).get("user_id"),)).fetchone()
    if not owner:
        raise ValueError("å…±äº«ç”¨æˆ·ä¸å­˜åœ¨")
    user = public_user(owner)
    conn.execute("update profile_shares set last_viewed_at = ? where token = ?", (now_iso(), token))
    permissions = share.get("permissions") or {}
    if permissions.get("auth_required") and not viewer:
        raise PermissionError("该共享链接需要统一账号登录后查看")
    report = build_report(conn, user) if permissions.get("report", True) else {}
    profile = profile_items(conn, user) if permissions.get("profile", True) else {"subjects": [], "items": []}
    history = build_generation_history(conn, user) if permissions.get("history", True) else {"items": [], "counts": {}, "total": 0}
    items = profile.get("items") or []
    recent_items = sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)[:12]
    subject_cards = []
    for subject in profile.get("subjects") or []:
        subject_items = [item for item in items if clean_subject_name((item.get("diagnosis") or {}).get("subject")) == subject.get("name")]
        passed = len([item for item in subject_items if item.get("status") == "passed"])
        subject_cards.append({
            "name": subject.get("name"),
            "count": subject.get("count"),
            "passed": passed,
            "pass_rate": round(passed / len(subject_items) * 100, 1) if subject_items else 0,
        })
    return {
        "share": share,
        "student": {
            "display_name": masked_email(user.get("email")),
            "created_at": user.get("created_at"),
        },
        "summary": {
            "total_wrong_questions": report.get("total_wrong_questions", len(items)),
            "passed_questions": report.get("passed_questions", 0),
            "pass_rate": report.get("pass_rate", 0),
            "history_total": history.get("total", 0),
            "subject_count": len(profile.get("subjects") or []),
        },
        "report": report,
        "subjects": subject_cards,
        "recent_questions": [
            {
                "id": item.get("id"),
                "subject": clean_subject_name((item.get("diagnosis") or {}).get("subject")),
                "title": (item.get("diagnosis") or {}).get("core_pattern") or (item.get("diagnosis") or {}).get("topic") or "é¢˜ç›®æ¡£æ¡ˆ",
                "question": compact_text(item.get("corrected_text"), 180),
                "status": item.get("status"),
                "created_at": item.get("created_at"),
                "variants": len(item.get("variants") or []),
            }
            for item in recent_items
        ],
        "history": (history.get("items") or [])[:16],
        "generated_at": now_iso(),
    }


def build_admin_overview(conn: sqlite3.Connection) -> dict:
    chat_rows = conn.execute("select * from model_configs order by is_default desc, updated_at desc").fetchall()
    image_rows = conn.execute("select * from image_model_configs order by is_default desc, updated_at desc").fetchall()
    chat_models = [public_model(row) for row in chat_rows]
    image_models = [public_image_model(row) for row in image_rows]
    default_chat = next((item for item in chat_models if item.get("is_default")), chat_models[0] if chat_models else None)
    default_image = next((item for item in image_models if item.get("is_default")), image_models[0] if image_models else None)
    return {
        "chat_models": chat_models,
        "image_models": image_models,
        "default_chat_model_id": default_chat.get("id") if default_chat else "",
        "default_image_model_id": default_image.get("id") if default_image else "",
    }


def test_model_connection(conn: sqlite3.Connection, model_id: str) -> dict:
    model = get_model(conn, model_id)
    try:
        sample = minimax_chat(
            model,
            [{"role": "user", "content": "è¯·åªå›žå¤ OKã€‚"}],
            max_tokens=16,
            temperature=0,
        )
        return {
            "ok": True,
            "model_id": model_id,
            "message": "è¿žæŽ¥æˆåŠŸ",
            "sample": compact_text(sample, 80),
        }
    except Exception as exc:
        return {
            "ok": False,
            "model_id": model_id,
            "message": str(exc),
        }


def update_model_api_key(conn: sqlite3.Connection, model_id: str, api_key: str) -> dict:
    row = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
    if not row:
        raise ValueError("æ¨¡åž‹ä¸å­˜åœ¨")
    if not api_key.strip():
        raise ValueError("API Key ä¸èƒ½ä¸ºç©º")
    conn.execute(
        "update model_configs set api_key = ?, updated_at = ? where id = ?",
        (api_key.strip(), now_iso(), model_id),
    )
    updated = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
    return public_model(updated)


def update_image_model_api_key(conn: sqlite3.Connection, model_id: str, api_key: str) -> dict:
    row = conn.execute("select * from image_model_configs where id = ?", (model_id,)).fetchone()
    if not row:
        raise ValueError("å›¾ç‰‡æ¨¡åž‹ä¸å­˜åœ¨")
    if not api_key.strip():
        raise ValueError("API Key ä¸èƒ½ä¸ºç©º")
    conn.execute(
        "update image_model_configs set api_key = ?, updated_at = ? where id = ?",
        (api_key.strip(), now_iso(), model_id),
    )
    updated = conn.execute("select * from image_model_configs where id = ?", (model_id,)).fetchone()
    return public_image_model(updated)


def public_app_config() -> dict:
    return {
        "use_unified_auth": unified_auth_enabled(),
        "unified_auth_url": public_auth_base_url(),
        "platform_id": UNIFIED_PLATFORM_ID,
        "local_auth_enabled": True,
    }


def run_paper_ocr(image_data_url: str, model_id: str | None = None) -> dict:
    with db() as conn:
        model = get_vision_model(conn, model_id)
    content = [
        {"type": "text", "text": PAPER_OCR_PROMPT},
        {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high", "max_long_side_pixel": 2200}},
    ]
    raw = minimax_chat(model, [{"role": "user", "content": content}], max_tokens=7000, temperature=0.1)
    result = extract_json(raw)
    result.setdefault("questions", [])
    result.setdefault("page_confidence", 0.0)
    return result


def image_url_to_data_url(source_url: str) -> str:
    relative = str(source_url or "").split("?", 1)[0].lstrip("/")
    path = PUBLIC_DIR / relative
    if not path.exists():
        raise ValueError("试卷页面原图不存在")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def build_eight_steps(diagnosis: dict, question: dict) -> list[dict]:
    decomposition = diagnosis.get("decomposition") or {}
    analysis = diagnosis.get("student_answer_analysis") or {}
    strategy = diagnosis.get("learning_strategy") or {}
    standard = diagnosis.get("standard_answer") or {}
    supplied = [
        {"key": "understand", "content": diagnosis.get("problem_goal") or question.get("printed_text")},
        {"key": "conditions", "content": decomposition.get("total_formula") or diagnosis.get("cleaned_question")},
        {"key": "knowledge", "content": "；".join(diagnosis.get("knowledge_points") or [])},
        {"key": "diagnose", "content": analysis.get("likely_issue"), "evidence": analysis.get("evidence") or []},
        {"key": "model", "content": strategy.get("entry_point") or diagnosis.get("core_pattern")},
        {"key": "solve", "content": standard.get("concise_solution") or "\n".join(str(x) for x in decomposition.get("step_formulas") or [])},
        {"key": "verify", "content": standard.get("final_answer") or "代入、单位、边界与逻辑校核"},
        {"key": "transfer", "content": strategy.get("make_it_easier") or "完成同型巩固、轻微变式与综合迁移"},
    ]
    return normalize_eight_steps({"eight_steps": supplied})


def ensure_gaokao_mother_catalog(conn: sqlite3.Connection) -> None:
    """幂等写入高考题型模型；后续教研导入不会被覆盖。"""
    columns = {row["name"] for row in conn.execute("pragma table_info(mother_questions)").fetchall()}
    for item in SEED_MOTHER_QUESTIONS:
        if conn.execute("select 1 from mother_questions where code=? limit 1", (item["code"],)).fetchone():
            continue
        metadata = {key: value for key, value in item.items() if key not in {"code", "name"}}
        values = {
            "id": str(uuid.uuid4()), "code": item["code"], "name": item["name"],
            "topic": item["name"], "difficulty": 3,
            "recognition_signals": json.dumps(item.get("keywords") or [], ensure_ascii=False),
            "knowledge_points": json.dumps(item.get("keywords") or [], ensure_ascii=False),
            "solution_steps": json.dumps([item.get("formula") or ""], ensure_ascii=False),
            "common_error_causes": json.dumps(item.get("reminders") or [], ensure_ascii=False),
            "mnemonic": item.get("formula") or "", "status": "seed_verified",
            "metadata": json.dumps(metadata, ensure_ascii=False), "created_at": now_iso(),
        }
        names = [name for name in values if name in columns]
        conn.execute(
            f"insert into mother_questions ({','.join(names)}) values ({','.join('?' for _ in names)})",
            [values[name] for name in names],
        )


def enrich_gaokao_diagnosis(question: dict, diagnosis: dict, subject: str) -> dict:
    mother = match_mother_question(question.get("printed_text") or "", subject)
    enriched = dict(diagnosis or {})
    enriched["gaokao_card"] = build_gaokao_card(question, enriched, mother)
    enriched["mother_question"] = mother
    return enriched


def fallback_paper_diagnosis(question: dict, error: Exception) -> dict:
    text = question.get("printed_text") or ""
    work = question.get("student_work") or ""
    return {
        "cleaned_question": text,
        "subject": "待确认",
        "topic": "模型结果待复核",
        "difficulty": 1,
        "confidence": 0.5,
        "core_pattern": "待教师复核题型",
        "knowledge_points": [],
        "problem_goal": "根据题干确定问题目标",
        "student_answer_analysis": {
            "answer_presence": "已提供" if work else "未提供",
            "extracted_work": work,
            "answer_status": "待复核",
            "likely_issue": "模型输出格式异常，已保留原题与作答，请人工确认",
            "evidence": [str(question.get("teacher_marks") or "").strip()] if question.get("teacher_marks") else [],
            "next_action": "确认题干、作答与批改痕迹后重新分析",
        },
        "learning_strategy": {
            "decomposition_answer": "先确认题意，再提取条件、选择方法、分步求解并验算",
            "make_it_easier": "先完成同知识点基础题，再回到原题",
            "entry_point": "确认题目条件和设问",
        },
        "decomposition": {"total_formula": "读题→条件→知识点→方法→求解→验算", "step_formulas": []},
        "standard_answer": {"final_answer": "待复核", "concise_solution": "待重新分析"},
        "practice_variants": [],
        "needs_review": True,
        "model_error": str(error),
    }


def paper_owner_clause(user: dict | None) -> tuple[str, list]:
    if user and user_is_admin(user):
        return "", []
    if user:
        return " and user_id = ?", [user["id"]]
    return " and user_id is null", []


def get_paper(conn: sqlite3.Connection, paper_id: str, user: dict | None) -> dict | None:
    owner_sql, params = paper_owner_clause(user)
    row = conn.execute(f"select * from exam_papers where id = ?{owner_sql}", [paper_id, *params]).fetchone()
    if not row:
        return None
    item = row_to_dict(row)
    item["summary"] = item.get("summary") if isinstance(item.get("summary"), dict) else json.loads(item.get("summary") or "{}")
    questions = []
    for qrow in conn.execute("select * from paper_questions where paper_id = ? order by cast(question_no as integer), question_no", (paper_id,)).fetchall():
        q = row_to_dict(qrow)
        q["bbox"] = q.get("bbox") if isinstance(q.get("bbox"), (list, dict)) else json.loads(q.get("bbox") or "null")
        q["eight_steps"] = q.get("eight_steps") if isinstance(q.get("eight_steps"), list) else json.loads(q.get("eight_steps") or "[]")
        q["diagnosis"] = q.get("diagnosis") if isinstance(q.get("diagnosis"), dict) else json.loads(q.get("diagnosis") or "{}")
        questions.append(q)
    item["questions"] = questions
    item["pages"] = [row_to_dict(x) for x in conn.execute("select * from paper_pages where paper_id = ? order by page_no", (paper_id,)).fetchall()]
    return item


def persist_wrong_from_paper(conn: sqlite3.Connection, paper_id: str, question_id: str, user_id: str | None, question: dict, diagnosis: dict) -> str:
    wrong_id = str(uuid.uuid4())
    confidence = float(diagnosis.get("confidence") or question.get("confidence") or 0.7)
    error_type = normalize_error_type((diagnosis.get("student_answer_analysis") or {}).get("likely_issue"))
    model = get_model(conn, None)
    conn.execute(
        """insert into wrong_questions
        (id,image_url,ocr_text,corrected_text,student_wrong_answer,model_id,diagnosis,status,confidence,user_id,error_type,workflow_state,created_at)
        values (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (wrong_id, None, question.get("printed_text"), question.get("printed_text") or "",
         question.get("student_work") or "", model["id"], json.dumps(diagnosis, ensure_ascii=False),
         "review_needed" if question.get("review_required") else "diagnosed", confidence, user_id,
         error_type, "diagnosed", now_iso()),
    )
    save_variants(conn, wrong_id, diagnosis)
    return wrong_id


def process_paper_job(paper_id: str, model_id: str | None = None) -> None:
    try:
        with db() as conn:
            ensure_gaokao_mother_catalog(conn)
            paper = conn.execute("select * from exam_papers where id = ?", (paper_id,)).fetchone()
            pages = conn.execute("select * from paper_pages where paper_id = ? order by page_no", (paper_id,)).fetchall()
            conn.execute("update exam_papers set status='processing',progress=2,updated_at=? where id=?", (now_iso(), paper_id))
            conn.execute("update paper_jobs set status='processing',progress=2,attempts=attempts+1,updated_at=? where paper_id=?", (now_iso(), paper_id))
        extracted = []
        for index, page in enumerate(pages, start=1):
            if page["source_url"]:
                result = run_paper_ocr(image_url_to_data_url(page["source_url"]), model_id)
                questions = result.get("questions") or []
            else:
                result = {"page_text": page["source_text"] or "", "page_confidence": 0.82}
                questions = split_numbered_questions(page["source_text"] or "")
            with db() as conn:
                conn.execute("update paper_pages set ocr_result=?,confidence=? where id=?", (json.dumps(result, ensure_ascii=False), float(result.get("page_confidence") or 0), page["id"]))
            for question in questions:
                question["page_id"] = page["id"]
                extracted.append(question)
            progress = min(45, round(index / max(1, len(pages)) * 45))
            with db() as conn:
                conn.execute("update exam_papers set progress=?,updated_at=? where id=?", (progress, now_iso(), paper_id))
                conn.execute("update paper_jobs set progress=?,updated_at=? where paper_id=?", (progress, now_iso(), paper_id))
        for index, question in enumerate(extracted, start=1):
            state = normalize_answer_state(question.get("answer_state"), question.get("score"), question.get("max_score"))
            confidence = float(question.get("confidence") or 0.55)
            review_required = state == "review_required" or confidence < 0.72
            diagnosis = {}
            steps = []
            wrong_id = None
            if state != "correct":
                try:
                    diagnosis = diagnose_with_llm(question.get("printed_text") or "", question.get("student_work") or question.get("teacher_marks") or "", "", model_id, paper["subject"] or "自动识别")
                except Exception as exc:
                    diagnosis = fallback_paper_diagnosis(question, exc)
                    review_required = True
                diagnosis = enrich_gaokao_diagnosis(question, diagnosis, paper["subject"] or "自动识别")
                steps = build_eight_steps(diagnosis, question)
            qid = str(uuid.uuid4())
            with db() as conn:
                if state != "correct":
                    wrong_id = persist_wrong_from_paper(conn, paper_id, qid, paper["user_id"], {**question, "review_required": review_required}, diagnosis)
                conn.execute(
                    """insert into paper_questions
                    (id,paper_id,page_id,question_no,printed_text,student_work,teacher_marks,answer_state,score,max_score,confidence,bbox,eight_steps,diagnosis,wrong_question_id,review_required,created_at)
                    values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (qid,paper_id,question.get("page_id"),str(question.get("question_no") or index),question.get("printed_text") or "",question.get("student_work") or "",question.get("teacher_marks") or "",state,question.get("score"),question.get("max_score"),confidence,json.dumps(question.get("bbox"),ensure_ascii=False),json.dumps(steps,ensure_ascii=False),json.dumps(diagnosis,ensure_ascii=False),wrong_id,1 if review_required else 0,now_iso()),
                )
                progress = 45 + round(index / max(1, len(extracted)) * 50)
                conn.execute("update exam_papers set progress=?,updated_at=? where id=?", (progress, now_iso(), paper_id))
                conn.execute("update paper_jobs set progress=?,updated_at=? where paper_id=?", (progress, now_iso(), paper_id))
        with db() as conn:
            rows = [row_to_dict(r) for r in conn.execute("select * from paper_questions where paper_id=?", (paper_id,)).fetchall()]
            summary = paper_summary(rows)
            matched = 0
            for row in rows:
                diag = json.loads(row.get("diagnosis") or "{}") if not isinstance(row.get("diagnosis"), dict) else row.get("diagnosis")
                if diag.get("mother_question"):
                    matched += 1
            summary["mother_matched_count"] = matched
            summary["knowledge_card_count"] = sum(1 for row in rows if row.get("answer_state") != "correct")
            conn.execute("update exam_papers set status='completed',summary=?,progress=100,updated_at=? where id=?", (json.dumps(summary,ensure_ascii=False),now_iso(),paper_id))
            conn.execute("update paper_jobs set status='completed',progress=100,message='分析完成',updated_at=? where paper_id=?", (now_iso(),paper_id))
    except Exception as exc:
        with db() as conn:
            conn.execute("update exam_papers set status='failed',error=?,updated_at=? where id=?", (str(exc),now_iso(),paper_id))
            conn.execute("update paper_jobs set status='failed',message=?,updated_at=? where paper_id=?", (str(exc),now_iso(),paper_id))


def build_paper_docx(paper: dict) -> bytes:
    from docx import Document
    doc = Document()
    doc.add_heading(paper.get("title") or "全卷分析报告", 0)
    summary = paper.get("summary") or {}
    doc.add_paragraph(f"题目总数：{summary.get('total_questions',0)}　错题/待复核：{summary.get('wrong_count',0)}　得分率：{summary.get('score_rate','-')}%")
    for q in paper.get("questions") or []:
        doc.add_heading(f"第 {q.get('question_no')} 题｜{q.get('answer_state')}", level=1)
        doc.add_paragraph(q.get("printed_text") or "")
        if q.get("student_work"): doc.add_paragraph("学生作答：" + q["student_work"])
        if q.get("teacher_marks"): doc.add_paragraph("批改痕迹：" + q["teacher_marks"])
        for step in q.get("eight_steps") or []:
            doc.add_heading(f"{step.get('number')}. {step.get('label')}", level=2)
            doc.add_paragraph(step.get("content") or "待复核")
    stream = BytesIO(); doc.save(stream); return stream.getvalue()


def build_paper_pdf(paper: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    stream = BytesIO(); styles = getSampleStyleSheet()
    for style in styles.byName.values(): style.fontName = 'STSong-Light'
    story = [Paragraph(paper.get("title") or "全卷分析报告", styles['Title']), Spacer(1, 12)]
    summary = paper.get("summary") or {}
    story.append(Paragraph(f"题目总数：{summary.get('total_questions',0)}　错题/待复核：{summary.get('wrong_count',0)}　得分率：{summary.get('score_rate','-')}%", styles['BodyText']))
    for q in paper.get("questions") or []:
        story += [Spacer(1, 12), Paragraph(f"第 {q.get('question_no')} 题｜{q.get('answer_state')}", styles['Heading2']), Paragraph((q.get("printed_text") or "").replace('\n','<br/>'), styles['BodyText'])]
        for step in q.get("eight_steps") or []:
            story.append(Paragraph(f"{step.get('number')}. {step.get('label')}：{step.get('content') or '待复核'}", styles['BodyText']))
    SimpleDocTemplate(stream, pagesize=A4).build(story); return stream.getvalue()


class AppHandler(BaseHTTPRequestHandler):
    server_version = "GaokaoMVP/0.2"

    def require_admin(self, conn: sqlite3.Connection) -> bool:
        user = current_user_from_request(conn, self.headers)
        if user_is_admin(user):
            return True
        self.send_json({"error": "éœ€è¦ç®¡ç†å‘˜è´¦å·ç™»å½•åŽè®¿é—®åŽå°é…ç½®ã€‚"}, 403)
        return False

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_json({"ok": True, "service": "gaokao-ai"})
            return
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed.path)
            return
        self.not_found()

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        raw = None
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                raw = body.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if raw is None:
            raise ValueError("请求内容编码无法识别，请使用 UTF-8")
        return json.loads(raw or "{}")

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_api_get(self, path: str, query: dict) -> None:
        try:
            def platform_admin_ok() -> bool:
                with db() as conn:
                    return user_is_admin(current_user_from_request(conn, self.headers))

            org_resp = org_inst_store.handle_org_api("GET", path, self.headers, None, platform_admin_ok)
            if org_resp:
                self.send_json(org_resp[1], org_resp[0])
                return
            if path == "/api/aippt/code":
                uid = (query.get("uid") or [""])[0].strip() or None
                self.send_json(aippt_auth.fetch_grant_code(uid=uid))
                return
            if path == "/api/config":
                self.send_json(public_app_config())
                return
            with db() as conn:
                user = current_user_from_request(conn, self.headers)
                if path == "/api/portal-tools":
                    self.send_json(PORTAL_TOOLS)
                    return
                if path == "/api/agent/layers":
                    self.send_json(AGENT_LAYERS)
                    return
                if path == "/api/me":
                    self.send_json(user if user else {"error": "unauthorized"}, 200 if user else 401)
                    return
                if path == "/api/history":
                    self.send_json(build_generation_history(conn, user))
                    return
                if path == "/api/papers":
                    owner_sql, params = paper_owner_clause(user)
                    rows = conn.execute(f"select * from exam_papers where 1=1{owner_sql} order by created_at desc", params).fetchall()
                    payload = []
                    for row in rows:
                        item = row_to_dict(row); item["summary"] = item.get("summary") if isinstance(item.get("summary"), dict) else json.loads(item.get("summary") or "{}"); payload.append(item)
                    self.send_json(payload)
                    return
                paper_match = re.fullmatch(r"/api/papers/([^/]+)", path)
                if paper_match:
                    item = get_paper(conn, paper_match.group(1), user)
                    self.send_json(item if item else {"error":"not found"}, 200 if item else 404)
                    return
                export_match = re.fullmatch(r"/api/papers/([^/]+)/export/(docx|pdf)", path)
                if export_match:
                    item = get_paper(conn, export_match.group(1), user)
                    if not item:
                        self.send_json({"error":"not found"},404); return
                    fmt = export_match.group(2)
                    if fmt == "docx":
                        self.send_bytes(build_paper_docx(item), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{item['title']}-全卷分析.docx")
                    else:
                        self.send_bytes(build_paper_pdf(item), "application/pdf", f"{item['title']}-全卷分析.pdf")
                    return
                if path == "/api/rag/documents":
                    where, params = rag_user_filter(user)
                    rows = conn.execute(f"select * from rag_documents{where} order by created_at desc", params).fetchall()
                    self.send_json([public_rag_document(row) for row in rows])
                    return
                if path == "/api/rag/search":
                    q = (query.get("q") or [""])[0]
                    subject = (query.get("subject") or ["è‡ªåŠ¨è¯†åˆ«"])[0]
                    limit = int((query.get("limit") or [5])[0])
                    self.send_json(search_rag(conn, q, subject, user, limit))
                    return
                match = re.fullmatch(r"/api/agent/runs/([^/]+)", path)
                if match:
                    row = conn.execute("select * from agent_runs where id = ?", (match.group(1),)).fetchone()
                    item = row_to_dict(row)
                    if user_owns_agent_run(user, item):
                        self.send_json(item)
                        return
                    self.send_json({"error": "not found"}, 404)
                    return
                match = re.fullmatch(r"/api/tool-runs/([^/]+)", path)
                if match:
                    row = conn.execute("select * from tool_runs where id = ?", (match.group(1),)).fetchone()
                    item = row_to_dict(row)
                    if item and user_owns_tool_run(user, item):
                        self.send_json(item)
                        return
                    self.send_json({"error": "not found"}, 404)
                    return
                match = re.fullmatch(r"/api/profile/exports/([^/]+)", path)
                if match:
                    row = conn.execute("select * from profile_exports where id = ?", (match.group(1),)).fetchone()
                    item = row_to_dict(row)
                    if item and user and (user_is_admin(user) or item.get("user_id") == user["id"]):
                        self.send_json(item)
                        return
                    self.send_json({"error": "not found"}, 404)
                    return
                if path == "/api/models":
                    rows = conn.execute("select * from model_configs order by is_default desc, updated_at desc").fetchall()
                    self.send_json([public_model(row) for row in rows])
                    return
                if path == "/api/image-models":
                    rows = conn.execute("select * from image_model_configs order by is_default desc, updated_at desc").fetchall()
                    self.send_json([public_image_model(row) for row in rows])
                    return
                if path == "/api/admin/overview":
                    if not self.require_admin(conn):
                        return
                    self.send_json(build_admin_overview(conn))
                    return
                if path == "/api/admin/models":
                    if not self.require_admin(conn):
                        return
                    rows = conn.execute("select * from model_configs order by is_default desc, updated_at desc").fetchall()
                    self.send_json([public_model(row) for row in rows])
                    return
                if path == "/api/admin/image-models":
                    if not self.require_admin(conn):
                        return
                    rows = conn.execute("select * from image_model_configs order by is_default desc, updated_at desc").fetchall()
                    self.send_json([public_image_model(row) for row in rows])
                    return
                if path == "/api/admin/prompts":
                    if not self.require_admin(conn):
                        return
                    rows = conn.execute("select * from prompt_templates order by key").fetchall()
                    self.send_json([row_to_dict(row) for row in rows])
                    return
                if path == "/api/mother-questions":
                    ensure_gaokao_mother_catalog(conn)
                    rows = conn.execute("select * from mother_questions order by created_at desc").fetchall()
                    self.send_json([row_to_dict(row) for row in rows])
                    return
                if path == "/api/wrong-questions/due":
                    if not user:
                        self.send_json([])
                        return
                    owner_sql, params = ("", []) if user_is_admin(user) else (" and user_id = ?", [user["id"]])
                    rows = conn.execute(
                        f"""
                        select id from wrong_questions
                        where workflow_state = 'review_scheduled'
                          and next_review_at is not null and next_review_at <= ?{owner_sql}
                        order by next_review_at asc
                        """,
                        [now_iso(), *params],
                    ).fetchall()
                    self.send_json([get_wrong_question(conn, row["id"]) for row in rows])
                    return
                if path == "/api/wrong-questions":
                    ids_param = (query.get("ids") or [""])[0]
                    if user and user_is_admin(user):
                        wq_where, wq_params = "", []
                    elif user:
                        wq_where, wq_params = " where user_id = ?", [user["id"]]
                    elif ids_param.strip():
                        id_list = [item.strip() for item in ids_param.split(",") if item.strip()]
                        if not id_list:
                            self.send_json([])
                            return
                        placeholders = ",".join("?" * len(id_list))
                        wq_where = f" where id in ({placeholders}) and (user_id is null or trim(user_id) = '')"
                        wq_params = id_list
                    else:
                        self.send_json([])
                        return
                    rows = conn.execute(
                        f"select * from wrong_questions{wq_where} order by created_at desc",
                        wq_params,
                    ).fetchall()
                    self.send_json([row_to_dict(row) for row in rows])
                    return
                if path == "/api/report":
                    self.send_json(build_report(conn, user))
                    return
                if path == "/api/profile":
                    self.send_json(profile_items(conn, user))
                    return
                if path == "/api/profile/shares":
                    self.send_json(list_profile_shares(conn, user))
                    return
                match = re.fullmatch(r"/api/share/([^/]+)", path)
                if match:
                    payload = build_public_share_payload(conn, match.group(1), user)
                    self.send_json(payload)
                    return
                match = re.fullmatch(r"/api/wrong-questions/([^/]+)", path)
                if match:
                    wrong_id = match.group(1)
                    if not user_owns_wrong_question(conn, user, wrong_id):
                        self.send_json({"error": "not found"}, 404)
                        return
                    item = get_wrong_question(conn, wrong_id)
                    self.send_json(item if item else {"error": "not found"}, 200 if item else 404)
                    return
                match = re.fullmatch(r"/api/wrong-questions/([^/]+)/variants", path)
                if match:
                    wrong_id = match.group(1)
                    if not user_owns_wrong_question(conn, user, wrong_id):
                        self.send_json({"error": "not found"}, 404)
                        return
                    rows = conn.execute(
                        "select * from exercise_variants where wrong_question_id = ? order by level",
                        (wrong_id,),
                    ).fetchall()
                    self.send_json([row_to_dict(row) for row in rows])
                    return
                match = re.fullmatch(r"/api/wrong-questions/([^/]+)/cards", path)
                if match:
                    wrong_id = match.group(1)
                    if not user_owns_wrong_question(conn, user, wrong_id):
                        self.send_json({"error": "not found"}, 404)
                        return
                    rows = conn.execute(
                        """
                        select * from study_cards
                        where wrong_question_id = ?
                        order by created_at desc
                        """,
                        (wrong_id,),
                    ).fetchall()
                    self.send_json([row_to_dict(row) for row in rows])
                    return
        except PermissionError as exc:
            self.send_json({"error": str(exc)}, 401)
            return
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)
            return
        self.not_found()

    def handle_api_post(self, path: str) -> None:
        try:
            def platform_admin_ok() -> bool:
                with db() as conn:
                    return user_is_admin(current_user_from_request(conn, self.headers))

            org_resp = org_inst_store.handle_org_api("POST", path, self.headers, self.read_json, platform_admin_ok)
            if org_resp:
                self.send_json(org_resp[1], org_resp[0])
                return
            if path == "/api/papers":
                data = self.read_json()
                def request_text(value, default=""):
                    if value is None: return default
                    if isinstance(value, str): return value
                    return json.dumps(value, ensure_ascii=False)
                title = request_text(data.get("title") or data.get("source_name"), "未命名试卷").strip()
                pages = data.get("pages") or []
                if data.get("paper_text"):
                    pages = [{"text": data.get("paper_text")}]
                if not pages:
                    self.send_json({"error":"请上传至少一页试卷或提供试卷文本"},400); return
                paper_id, job_id, ts = str(uuid.uuid4()), str(uuid.uuid4()), now_iso()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    conn.execute("insert into exam_papers (id,user_id,title,subject,status,source_name,summary,progress,created_at,updated_at) values (?,?,?,?,?,?,?,?,?,?)",
                                 (paper_id,request_text(user.get("id")) if user else None,title,request_text(data.get("subject"),"自动识别"),"queued",request_text(data.get("source_name"),title),"{}",0,ts,ts))
                    for page_no, page in enumerate(pages, start=1):
                        if not isinstance(page, dict): page = {"text": request_text(page)}
                        source_url = save_data_url(page.get("image_data_url")) if page.get("image_data_url") else None
                        conn.execute("insert into paper_pages (id,paper_id,page_no,source_url,source_text,ocr_result,confidence) values (?,?,?,?,?,?,?)",
                                     (str(uuid.uuid4()),paper_id,page_no,source_url,request_text(page.get("text")),"{}",0))
                    conn.execute("insert into paper_jobs (id,paper_id,status,progress,message,attempts,created_at,updated_at) values (?,?,?,?,?,?,?,?)",
                                 (job_id,paper_id,"queued",0,"等待分析",0,ts,ts))
                threading.Thread(target=process_paper_job,args=(paper_id,data.get("model_id")),daemon=True,name=f"paper-{paper_id[:8]}").start()
                self.send_json({"id":paper_id,"job_id":job_id,"status":"queued","progress":0},202)
                return
            retry_match = re.fullmatch(r"/api/papers/([^/]+)/retry", path)
            if retry_match:
                with db() as conn:
                    user = current_user_from_request(conn,self.headers)
                    paper = get_paper(conn,retry_match.group(1),user)
                    if not paper: self.send_json({"error":"not found"},404); return
                    conn.execute("delete from paper_questions where paper_id=?",(paper["id"],))
                    conn.execute("update exam_papers set status='queued',progress=0,error=null,updated_at=? where id=?",(now_iso(),paper["id"]))
                    conn.execute("update paper_jobs set status='queued',progress=0,message='重新分析',updated_at=? where paper_id=?",(now_iso(),paper["id"]))
                threading.Thread(target=process_paper_job,args=(paper["id"],None),daemon=True).start()
                self.send_json({"id":paper["id"],"status":"queued"},202); return
            if path == "/api/register":
                self.register_user()
                return
            if path == "/api/login":
                self.login_user()
                return
            if path == "/api/redeem":
                self.redeem_code()
                return
            if path == "/api/agent/solve":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = solve_with_agent(conn, data, user)
                self.send_json(result, 201)
                return
            if path == "/api/rag/documents":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = create_rag_document(conn, data, user)
                self.send_json(result, 201)
                return
            if path == "/api/rag/search":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = search_rag(conn, data.get("query") or "", data.get("subject") or "è‡ªåŠ¨è¯†åˆ«", user, int(data.get("limit") or 5))
                self.send_json(result)
                return
            if path == "/api/rag/generate-quiz":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    topic = data.get("topic") or data.get("query") or "错题复习"
                    subject = data.get("subject") or "自动识别"
                    hits = search_rag(conn, str(topic), subject, user, max(6, int(data.get("count") or 5)))
                    result = generate_rag_quiz_from_hits(str(topic), hits, int(data.get("count") or 5))
                self.send_json(result)
                return
            if path == "/api/rag/study-os":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    topic = data.get("topic") or data.get("query") or "错题自学"
                    subject = data.get("subject") or "自动识别"
                    hits = search_rag(conn, str(topic), subject, user, 8)
                    result = generate_rag_study_os(str(topic), hits)
                self.send_json(result)
                return
            if path == "/api/tool-runs":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = run_portal_tool(conn, data, user)
                self.send_json(result, 201)
                return
            match = re.fullmatch(r"/api/admin/models/([^/]+)/test", path)
            if match:
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    result = test_model_connection(conn, match.group(1))
                status = 200 if result.get("ok") else 502
                self.send_json(result, status)
                return
            match = re.fullmatch(r"/api/admin/models/([^/]+)/api-key", path)
            if match:
                data = self.read_json()
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    result = update_model_api_key(conn, match.group(1), data.get("api_key") or "")
                self.send_json(result)
                return
            match = re.fullmatch(r"/api/admin/image-models/([^/]+)/api-key", path)
            if match:
                data = self.read_json()
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    result = update_image_model_api_key(conn, match.group(1), data.get("api_key") or "")
                self.send_json(result)
                return
            if path == "/api/admin/models":
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                self.save_model()
                return
            if path == "/api/admin/default-model":
                data = self.read_json()
                model_id = data.get("id")
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    conn.execute("update model_configs set is_default = 0")
                    conn.execute("update model_configs set is_default = 1, updated_at = ? where id = ?", (now_iso(), model_id))
                self.send_json({"ok": True})
                return
            if path == "/api/admin/image-models":
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                self.save_image_model()
                return
            if path == "/api/admin/default-image-model":
                data = self.read_json()
                model_id = data.get("id")
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    conn.execute("update image_model_configs set is_default = 0")
                    conn.execute("update image_model_configs set is_default = 1, updated_at = ? where id = ?", (now_iso(), model_id))
                self.send_json({"ok": True})
                return
            if path == "/api/admin/prompts":
                data = self.read_json()
                key = data.get("key")
                content = data.get("content", "")
                if key not in {"ocr", "diagnosis", "grading"}:
                    self.send_json({"error": "invalid prompt key"}, 400)
                    return
                with db() as conn:
                    if not self.require_admin(conn):
                        return
                    conn.execute(
                        "update prompt_templates set content = ?, updated_at = ? where key = ?",
                        (content, now_iso(), key),
                    )
                self.send_json({"ok": True})
                return
            if path == "/api/ocr":
                data = self.read_json()
                image_data_url = data.get("image_data_url")
                image_url = save_data_url(image_data_url)
                result = run_ocr(image_data_url, data.get("model_id"))
                result["image_url"] = image_url
                self.send_json(result, 201)
                return
            if path == "/api/extract-document":
                data = self.read_json()
                result = extract_document_from_data_url(
                    data.get("filename") or "upload.txt",
                    data.get("file_data_url") or "",
                )
                self.send_json(result, 201)
                return
            if path == "/api/diagnose":
                self.create_diagnosis()
                return
            match = re.fullmatch(r"/api/wrong-questions/([^/]+)/variants", path)
            if match:
                wrong_id = match.group(1)
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    if not user_owns_wrong_question(conn, user, wrong_id):
                        self.send_json({"error": "wrong question not found"}, 404)
                        return
                    wrong = get_wrong_question(conn, wrong_id)
                    if not wrong:
                        self.send_json({"error": "wrong question not found"}, 404)
                        return
                    variants = save_variants(conn, wrong_id, wrong["diagnosis"])
                    conn.execute("update wrong_questions set status = ? where id = ?", ("training", wrong_id))
                self.send_json(variants, 201)
                return
            match = re.fullmatch(r"/api/wrong-questions/([^/]+)/cards", path)
            if match:
                data = self.read_json()
                card = generate_study_card(
                    match.group(1),
                    data.get("image_model_id"),
                    data.get("style") or "",
                )
                self.send_json(card, 201)
                return
            match = re.fullmatch(r"/api/exercise-variants/([^/]+)/answers", path)
            if match:
                self.grade_answer(match.group(1))
                return
            if path == "/api/mother-questions":
                self.create_reserved_mother()
                return
            if path == "/api/profile/share":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = create_profile_share(conn, data, user)
                self.send_json(result, 201)
                return
            match = re.fullmatch(r"/api/profile/shares/([^/]+)/revoke", path)
            if match:
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = revoke_profile_share(conn, match.group(1), user)
                self.send_json(result)
                return
            if path == "/api/profile/export":
                data = self.read_json()
                with db() as conn:
                    user = current_user_from_request(conn, self.headers)
                    result = build_profile_markdown(conn, data, user)
                    export_id = str(uuid.uuid4())
                    user_id = user["id"] if user else None
                    conn.execute(
                        """
                        insert into profile_exports (id, filename, subject, markdown, count, user_id, created_at)
                        values (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            export_id,
                            result.get("filename") or "ä¸ªäººå­¦ä¹ æ¡£æ¡ˆ.md",
                            data.get("subject") or "å…¨éƒ¨å­¦ç§‘",
                            result.get("markdown") or "",
                            int(result.get("count") or 0),
                            user_id,
                            now_iso(),
                        ),
                    )
                    result["id"] = export_id
                    self.send_json(result, 201)
                return
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)
            return
        self.not_found()

    def register_user(self) -> None:
        data = self.read_json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            self.send_json({"error": "è¯·è¾“å…¥æœ‰æ•ˆé‚®ç®±"}, 400)
            return
        if email == ADMIN_EMAIL:
            self.send_json({"error": "è¯¥é‚®ç®±ä¸ºç³»ç»Ÿç®¡ç†å‘˜è´¦å·ï¼Œè¯·ç›´æŽ¥ç™»å½•"}, 409)
            return
        if len(password) < 6:
            self.send_json({"error": "å¯†ç è‡³å°‘ 6 ä½"}, 400)
            return
        user_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        with db() as conn:
            exists = conn.execute("select id from app_users where email = ?", (email,)).fetchone()
            if exists:
                self.send_json({"error": "é‚®ç®±å·²æ³¨å†Œï¼Œè¯·ç›´æŽ¥ç™»å½•"}, 409)
                return
            conn.execute(
                "insert into app_users (id, email, password_hash, credits, created_at) values (?, ?, ?, ?, ?)",
                (user_id, email, hash_password(password), 9, now_iso()),
            )
            conn.execute(
                "insert into app_sessions (token, user_id, created_at) values (?, ?, ?)",
                (token, user_id, now_iso()),
            )
            row = conn.execute("select * from app_users where id = ?", (user_id,)).fetchone()
        self.send_json({"token": token, **public_user(row)}, 201)

    def login_user(self) -> None:
        data = self.read_json()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        with db() as conn:
            row = conn.execute("select * from app_users where email = ?", (email,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                self.send_json({"error": "é‚®ç®±æˆ–å¯†ç é”™è¯¯"}, 401)
                return
            token = secrets.token_urlsafe(32)
            conn.execute(
                "insert into app_sessions (token, user_id, created_at) values (?, ?, ?)",
                (token, row["id"], now_iso()),
            )
        self.send_json({"token": token, **public_user(row)})

    def redeem_code(self) -> None:
        data = self.read_json()
        code = (data.get("code") or "").strip().upper()
        with db() as conn:
            user = current_user_from_request(conn, self.headers)
            if not user:
                self.send_json({"error": "è¯·å…ˆç™»å½•åŽå†å…‘æ¢ç§¯åˆ†"}, 401)
                return
            row = conn.execute("select * from redeem_codes where code = ?", (code,)).fetchone()
            if not row:
                self.send_json({"error": "å…‘æ¢ç ä¸å­˜åœ¨"}, 404)
                return
            reusable_demo = code == "DEMO2026"
            if row["is_used"] and not reusable_demo:
                self.send_json({"error": "å…‘æ¢ç å·²ä½¿ç”¨"}, 409)
                return
            if not reusable_demo:
                conn.execute(
                    "update redeem_codes set is_used = 1, used_by = ?, used_at = ? where code = ?",
                    (user["id"], now_iso(), code),
                )
            conn.execute("update app_users set credits = credits + ? where id = ?", (int(row["credits"]), user["id"]))
            updated = conn.execute("select * from app_users where id = ?", (user["id"],)).fetchone()
        self.send_json({"ok": True, "added": int(row["credits"]), "credits": int(updated["credits"])})

    def save_model(self) -> None:
        data = self.read_json()
        model_id = data.get("id") or str(uuid.uuid4())
        name = data.get("name") or "MiniMax M3"
        provider = data.get("provider") or "minimax"
        endpoint = data.get("endpoint") or MINIMAX_ENDPOINT
        model = data.get("model") or "MiniMax-M3"
        api_key = data.get("api_key")
        with db() as conn:
            existing = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
            if existing:
                old = dict(existing)
                conn.execute(
                    """
                    update model_configs
                    set name=?, provider=?, endpoint=?, model=?,
                        api_key=?, supports_vision=?, temperature=?, max_tokens=?, updated_at=?
                    where id=?
                    """,
                    (
                        name,
                        provider,
                        endpoint,
                        model,
                        api_key if api_key is not None and api_key != "" else old.get("api_key"),
                        1 if data.get("supports_vision", True) else 0,
                        float(data.get("temperature", old.get("temperature", 0.45))),
                        int(data.get("max_tokens", old.get("max_tokens", 7000))),
                        now_iso(),
                        model_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    insert into model_configs
                    (id, name, provider, endpoint, model, api_key, supports_vision,
                     temperature, max_tokens, is_default, created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        name,
                        provider,
                        endpoint,
                        model,
                        api_key or "",
                        1 if data.get("supports_vision", True) else 0,
                        float(data.get("temperature", 0.45)),
                        int(data.get("max_tokens", 7000)),
                        0,
                        now_iso(),
                        now_iso(),
                    ),
                )
            row = conn.execute("select * from model_configs where id = ?", (model_id,)).fetchone()
        self.send_json(public_model(row), 201)

    def save_image_model(self) -> None:
        data = self.read_json()
        model_id = data.get("id") or str(uuid.uuid4())
        name = data.get("name") or "OpenAI GPT Image å¡ç‰‡ç”Ÿæˆ"
        provider = data.get("provider") or "openai"
        endpoint = data.get("endpoint") or OPENAI_IMAGE_ENDPOINT
        model = data.get("model") or DEFAULT_OPENAI_IMAGE_MODEL
        api_key = data.get("api_key")
        size = data.get("size") or DEFAULT_OPENAI_IMAGE_SIZE
        quality = data.get("quality") or DEFAULT_OPENAI_IMAGE_QUALITY
        with db() as conn:
            existing = conn.execute("select * from image_model_configs where id = ?", (model_id,)).fetchone()
            if existing:
                old = dict(existing)
                conn.execute(
                    """
                    update image_model_configs
                    set name=?, provider=?, endpoint=?, model=?, api_key=?,
                        size=?, quality=?, updated_at=?
                    where id=?
                    """,
                    (
                        name,
                        provider,
                        endpoint,
                        model,
                        api_key if api_key is not None and api_key != "" else old.get("api_key"),
                        size,
                        quality,
                        now_iso(),
                        model_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    insert into image_model_configs
                    (id, name, provider, endpoint, model, api_key, size, quality,
                     is_default, created_at, updated_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        name,
                        provider,
                        endpoint,
                        model,
                        api_key or "",
                        size,
                        quality,
                        0,
                        now_iso(),
                        now_iso(),
                    ),
                )
            row = conn.execute("select * from image_model_configs where id = ?", (model_id,)).fetchone()
        self.send_json(public_image_model(row), 201)

    def create_diagnosis(self) -> None:
        data = self.read_json()
        text = (data.get("question_text") or "").strip()
        if not text:
            self.send_json({"error": "question_text is required"}, 400)
            return
        image_url = save_data_url(data.get("image_data_url"))
        wrong_answer = (data.get("student_wrong_answer") or "").strip()
        ocr_text = (data.get("ocr_text") or "").strip()
        model_id = data.get("model_id")
        subject = data.get("subject") or "è‡ªåŠ¨è¯†åˆ«"
        diagnosis = diagnose_with_llm(text, wrong_answer, ocr_text, model_id, subject)
        answer_analysis = diagnosis.setdefault("student_answer_analysis", {})
        error_type = normalize_error_type(answer_analysis.get("error_type") or answer_analysis.get("likely_issue"))
        answer_analysis["error_type"] = error_type
        for index, variant in enumerate(diagnosis.get("practice_variants") or [], start=1):
            variant["tier"] = practice_tier(index)
        wrong_id = str(uuid.uuid4())
        confidence = float(diagnosis.get("confidence") or 0.75)
        status = "review_needed" if diagnosis.get("needs_review") else "diagnosed"
        with db() as conn:
            user = current_user_from_request(conn, self.headers)
            user_id = user["id"] if user else None
            org_ctx = institution_context_for_app_user(user)
            actual_model = get_model(conn, model_id)
            conn.execute(
                """
                insert into wrong_questions
                (id, image_url, ocr_text, corrected_text, student_wrong_answer, model_id,
                 diagnosis, status, confidence, user_id, institution_id, institution_name,
                 institution_badge, error_type, workflow_state, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wrong_id,
                    image_url,
                    ocr_text,
                    text,
                    wrong_answer,
                    actual_model["id"],
                    json.dumps(diagnosis, ensure_ascii=False),
                    status,
                    confidence,
                    user_id,
                    org_ctx.get("institution_id") or None,
                    org_ctx.get("institution_name") or None,
                    org_ctx.get("institution_badge") or None,
                    error_type,
                    "diagnosed",
                    now_iso(),
                ),
            )
            save_variants(conn, wrong_id, diagnosis)
            reserved = diagnosis.get("mother_question_reserved") or {}
            if reserved.get("name"):
                conn.execute(
                    """
                    insert into mother_questions (id, code, name, status, metadata, created_at)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        f"MQ-{wrong_id[:8]}",
                        reserved.get("name") or "é¢˜åž‹åŽŸåž‹",
                        "auto_from_diagnosis",
                        json.dumps(
                            {
                                "wrong_question_id": wrong_id,
                                "abstract_pattern": reserved.get("abstract_pattern"),
                                "recognition_signals": reserved.get("recognition_signals"),
                                "subject": diagnosis.get("subject"),
                            },
                            ensure_ascii=False,
                        ),
                        now_iso(),
                    ),
                )
            item = get_wrong_question(conn, wrong_id)
        self.send_json(item, 201)

    def grade_answer(self, variant_id: str) -> None:
        data = self.read_json()
        answer_text = (data.get("answer_text") or "").strip()
        model_id = data.get("model_id")
        hint_count = max(0, min(int(data.get("hint_count") or 0), 3))
        with db() as conn:
            variant = row_to_dict(conn.execute("select * from exercise_variants where id = ?", (variant_id,)).fetchone())
            if not variant:
                self.send_json({"error": "variant not found"}, 404)
                return
            wrong = get_wrong_question(conn, variant["wrong_question_id"])
        result = grade_with_llm(variant, answer_text, wrong.get("diagnosis") if wrong else None, model_id)
        answer_id = str(uuid.uuid4())
        with db() as conn:
            conn.execute(
                """
                insert into student_answers
                (id, exercise_variant_id, answer_text, grading_result, is_correct, hint_count, submitted_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer_id,
                    variant_id,
                    answer_text,
                    json.dumps(result, ensure_ascii=False),
                    1 if result["is_correct"] else 0,
                    hint_count,
                    now_iso(),
                ),
            )
            update_pass_status(conn, variant["wrong_question_id"])
        self.send_json({"id": answer_id, **result}, 201)

    def create_reserved_mother(self) -> None:
        data = self.read_json()
        item_id = str(uuid.uuid4())
        with db() as conn:
            conn.execute(
                """
                insert into mother_questions (id, code, name, status, metadata, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    data.get("code") or f"RES-{item_id[:8]}",
                    data.get("name") or "é¢„ç•™æ¯é¢˜",
                    "reserved",
                    json.dumps(data.get("metadata") or {}, ensure_ascii=False),
                    now_iso(),
                ),
            )
            row = conn.execute("select * from mother_questions where id = ?", (item_id,)).fetchone()
        self.send_json(row_to_dict(row), 201)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        if path == "/org":
            path = "/org.html"
        if path == "/org-admin":
            path = "/org-admin.html"
        safe_path = path.lstrip("/").replace("..", "")
        file_path = PUBLIC_DIR / safe_path
        if not file_path.exists() or not file_path.is_file():
            self.not_found()
            return
        content_type = "text/plain; charset=utf-8"
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        elif file_path.suffix in (".png", ".jpg", ".jpeg", ".webp"):
            kind = "jpeg" if file_path.suffix in (".jpg", ".jpeg") else file_path.suffix.lstrip(".")
            content_type = f"image/{kind}"
        elif file_path.suffix == ".docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_path.suffix == ".pptx":
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif file_path.suffix == ".md":
            content_type = "text/markdown; charset=utf-8"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if "exports" in file_path.parts and file_path.suffix in (".docx", ".pptx", ".md", ".png"):
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def not_found(self) -> None:
        self.send_json({"error": "not found"}, 404)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{now_iso()}] {self.address_string()} {fmt % args}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8021"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"AIé”™é¢˜æ‹†åšå£«å·²å¯åŠ¨: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
