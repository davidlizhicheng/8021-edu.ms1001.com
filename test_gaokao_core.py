import unittest

from gaokao_core import build_gaokao_card, match_mother_question


class GaokaoCoreTests(unittest.TestCase):
    def test_matches_derivative_mother_and_exposes_source(self):
        hit = match_mother_question("已知函数f(x)，讨论导数与单调区间并求极值", "数学")
        self.assertEqual(hit["code"], "M-MATH-DERIV-01")
        self.assertTrue(hit["source"])

    def test_card_always_has_speech_defined_eight_steps(self):
        card = build_gaokao_card({"student_work":"令f'(x)=0"}, {"student_answer_analysis":{"likely_issue":"漏判区间"}})
        self.assertEqual(len(card["steps"]), 8)
        self.assertEqual(card["steps"][0]["label"], "作答还原")
        self.assertEqual(card["steps"][-1]["label"], "自我复盘")

    def test_unmatched_question_requires_review(self):
        card = build_gaokao_card({}, {}, match_mother_question("无法判断题型的短文本", ""))
        self.assertEqual(card["evidence_status"], "review_required")


if __name__ == "__main__":
    unittest.main()

