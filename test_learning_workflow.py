from datetime import datetime, timezone
import unittest

from learning_workflow import needs_calibration, normalize_error_type, practice_tier, transition


class LearningWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 11, tzinfo=timezone.utc)

    def test_low_confidence_or_short_ocr_requires_calibration(self):
        self.assertTrue(needs_calibration("一道完整的数学题目文本", 0.79))
        self.assertTrue(needs_calibration("太短", 0.99))
        self.assertFalse(needs_calibration("一道完整的数学题目文本", 0.91))

    def test_error_taxonomy_and_practice_tiers_are_normalized(self):
        self.assertEqual(normalize_error_type("审题错误"), "reading_error")
        self.assertEqual(normalize_error_type("unknown"), "knowledge_gap")
        self.assertEqual(practice_tier(1)["label"], "同型巩固")
        self.assertEqual(practice_tier(3)["code"], "far_transfer")

    def test_wrong_answer_returns_to_remediation(self):
        result = transition([
            {"level": 1, "is_correct": True},
            {"level": 2, "is_correct": False},
            {"level": 3, "is_correct": True},
        ], now=self.now)
        self.assertEqual(result["state"], "remediation")
        self.assertIsNone(result["next_review_at"])

    def test_three_tiers_schedule_review_and_hints_reduce_mastery(self):
        result = transition([
            {"level": 1, "is_correct": True, "hint_count": 0},
            {"level": 2, "is_correct": True, "hint_count": 1},
            {"level": 3, "is_correct": True, "hint_count": 0},
        ], now=self.now)
        self.assertEqual(result["state"], "review_scheduled")
        self.assertGreaterEqual(result["mastery_score"], 75)
        self.assertLess(result["mastery_score"], 100)
        self.assertTrue(result["next_review_at"].startswith("2026-07-12"))

    def test_last_review_stage_marks_mastered_and_uses_30_days(self):
        result = transition([
            {"level": 1, "is_correct": True},
            {"level": 2, "is_correct": True},
            {"level": 3, "is_correct": True},
        ], review_stage=4, now=self.now)
        self.assertEqual(result["state"], "mastered")
        self.assertTrue(result["next_review_at"].startswith("2026-08-10"))


if __name__ == "__main__":
    unittest.main()
