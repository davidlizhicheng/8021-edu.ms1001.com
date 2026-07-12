"""Idempotently seed the public RAG library from reviewed local materials."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server
GAOKAO_DIR = ROOT / "data" / "gaokao_2026"

SHENZHEN_PACKS = {
    "深圳初三数学复习模型": """
来源：义务教育数学课程标准（2022年版）能力框架整理，不含第三方试卷全文。
函数：一次函数、反比例函数、二次函数；训练解析式、图象交点、最值与实际情境。
方程与不等式：设元、建模、求解、验根、实际意义；分式方程必须检验增根。
几何：全等、相似、圆、锐角三角函数；训练基本图形识别、辅助线目的和完整推理链。
统计概率：总体样本、抽样、频数、平均数、概率；结论必须回到问题情境。
每题复盘统一记录：题干信号、错误步骤、正确切入点、规范解答、评分点、母题公式、关键提醒、同型训练。
""",
    "深圳初三英语复习模型": """
来源：义务教育英语课程标准（2022年版）能力框架整理，不含第三方试卷全文。
阅读理解：先判主旨/细节/推断/态度题型，再定位原文并识别同义改写，禁止超文本推断。
完形填空：通读主旨、判词性、近句搭配、远句逻辑、全文回读。
语法填空：句子成分、词性、时态语态、非谓语、从句和固定搭配逐层检查。
书面表达：体裁、人称、时态、要点、段落结构、连接词、句式与拼写复核。
适合李娜假期辅导：英语按词汇—语法—阅读—写作四线推进；数学按模型识别和错因复盘推进。
""",
}


def already_seeded(conn, title: str) -> bool:
    return bool(conn.execute("select 1 from rag_documents where title=? limit 1", (title,)).fetchone())


def main() -> None:
    server.init_db()
    created = []
    with server.db() as conn:
        server.ensure_gaokao_mother_catalog(conn)
        for title, text in SHENZHEN_PACKS.items():
            if not already_seeded(conn, title):
                created.append(server.create_rag_document(conn, {"title": title, "filename": f"{title}.txt", "subject": "数学" if "数学" in title else "英语", "text": text}, None))
        if GAOKAO_DIR.exists():
            for path in sorted(GAOKAO_DIR.glob("*.tex")):
                title = path.stem
                if already_seeded(conn, title):
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                created.append(server.create_rag_document(conn, {"title": title, "filename": path.name, "subject": "数学", "text": text}, None))
    print(f"seeded_documents={len(created)}")


if __name__ == "__main__":
    main()
