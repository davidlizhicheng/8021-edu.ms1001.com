import unittest

from paper_workflow import normalize_answer_state, normalize_eight_steps, paper_summary, split_numbered_questions, wrong_questions


class PaperWorkflowTests(unittest.TestCase):
    def test_segments_numbered_text(self):
        rows = split_numbered_questions("1. 第一题\n计算过程\n2、第二题\n作答")
        self.assertEqual([r["question_no"] for r in rows], ["1", "2"])

    def test_normalizes_grading_and_filters_wrong_items(self):
        rows = [
            {"answer_state": "正确"}, {"answer_state": "部分正确"},
            {"answer_state": "", "score": 0, "max_score": 5},
        ]
        self.assertEqual(normalize_answer_state("部分正确"), "partial")
        self.assertEqual(len(wrong_questions(rows)), 2)

    def test_always_returns_fixed_eight_steps(self):
        steps = normalize_eight_steps({"steps": [{"content": "读题"}]})
        self.assertEqual(len(steps), 8)
        self.assertEqual(steps[0]["label"], "读懂题意")
        self.assertEqual(steps[-1]["key"], "transfer")

    def test_builds_paper_summary(self):
        summary = paper_summary([
            {"answer_state": "correct", "score": 5, "max_score": 5},
            {"answer_state": "partial", "score": 2, "max_score": 5},
            {"answer_state": "wrong", "score": 0, "max_score": 5},
        ])
        self.assertEqual(summary["wrong_count"], 2)
        self.assertEqual(summary["score_rate"], 46.7)


if __name__ == "__main__":
    unittest.main()
