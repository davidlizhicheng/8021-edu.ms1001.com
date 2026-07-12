import json
import unittest

import server


class TextQualityTests(unittest.TestCase):
    def test_repairs_common_utf8_cp1252_mojibake(self):
        self.assertEqual(server.repair_mojibake_text("å¾…å½’çº³é¢˜åž‹"), "待归纳题型")
        self.assertEqual(server.repair_mojibake_text("æœªæä¾›ä½œç­”"), "未提供作答")

    def test_repairs_nested_diagnosis_values(self):
        value = {"a": ["å…ˆè¯†åˆ«é¢˜åž‹", {"b": "æœªæä¾›"}]}
        repaired = server.repair_text_tree(value)
        self.assertEqual(repaired["a"][0], "先识别题型")
        self.assertEqual(repaired["a"][1]["b"], "未提供")

    def test_normalized_diagnosis_has_actionable_core_fields(self):
        diagnosis = server.normalize_diagnosis_payload(
            {"core_pattern": "å¾…å½’çº³é¢˜åž‹", "standard_answer": {}},
            question_text="已知条件，求结论。",
            student_answer="",
        )
        self.assertEqual(diagnosis["core_pattern"], "待归纳题型")
        self.assertTrue(diagnosis["problem_goal"])
        self.assertTrue(diagnosis["decomposition"]["total_formula"])
        self.assertTrue(diagnosis["decomposition"]["step_formulas"])
        self.assertTrue(diagnosis["standard_answer"]["final_answer"])
        self.assertTrue(diagnosis["standard_answer"]["concise_solution"])
        self.assertNotIn("未返回", json.dumps(diagnosis, ensure_ascii=False))
        self.assertEqual(server.text_quality_issues(diagnosis), [])

    def test_quality_gate_reports_bad_visible_text(self):
        issues = server.text_quality_issues({"x": "æ¨¡åž‹æœªè¿”å›ž", "y": "未返回总拆解公式"})
        self.assertIn("mojibake", issues)
        self.assertIn("unhelpful_placeholder", issues)


if __name__ == "__main__":
    unittest.main()
