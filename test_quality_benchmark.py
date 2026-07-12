import unittest

from gaokao_core import match_mother_question


SHENZHEN_GRADE9_PAPERS = [
    ("数学", "一次函数图象与反比例函数交点综合题"),
    ("数学", "二次函数图象顶点、交点与实际利润问题"),
    ("数学", "圆与相似三角形的几何证明题"),
    ("数学", "全等三角形判定与辅助线证明"),
    ("数学", "分式方程应用题并检验增根"),
    ("数学", "一元一次不等式组解集与方案选择"),
    ("数学", "抽样调查频数分布与平均数解释"),
    ("数学", "随机事件概率与列表法统计"),
    ("数学", "二次函数与圆的综合压轴题"),
    ("数学", "方程根与函数图象交点关系"),
    ("数学", "相似三角形与动点最值问题"),
    ("数学", "统计图补全与样本估计总体"),
    ("英语", "阅读理解 main idea 与 detail 证据定位"),
    ("英语", "阅读理解 infer 作者 attitude 推断"),
    ("英语", "完形填空 cloze 上下文语境和固定搭配"),
    ("英语", "完形填空 代词指代与段落逻辑"),
    ("英语", "语法填空 时态语态与词形变化"),
    ("英语", "语法填空 非谓语动词和定语从句"),
    ("英语", "书面表达 writing 一封建议信"),
    ("英语", "英语作文 email 校园活动通知"),
    ("英语", "阅读理解 detail 与同义替换"),
    ("英语", "完形填空 cloze 情感线索"),
    ("英语", "语法填空 从句与固定搭配"),
    ("英语", "书面表达 作文 倡议保护环境"),
]


class QualityBenchmarkTests(unittest.TestCase):
    def test_24_grade9_papers_match_a_source_backed_model(self):
        self.assertEqual(len(SHENZHEN_GRADE9_PAPERS), 24)
        matches = [match_mother_question(text, subject) for subject, text in SHENZHEN_GRADE9_PAPERS]
        self.assertTrue(all(matches))
        self.assertTrue(all(item["source"] for item in matches))

    def test_math_and_english_are_both_covered(self):
        codes = {match_mother_question(text, subject)["code"] for subject, text in SHENZHEN_GRADE9_PAPERS}
        self.assertTrue(any(code.startswith("SZ-MATH") for code in codes))
        self.assertTrue(any(code.startswith("SZ-ENG") for code in codes))


if __name__ == "__main__":
    unittest.main()
