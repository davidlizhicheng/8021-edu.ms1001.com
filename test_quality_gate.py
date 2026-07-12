import unittest

from server import enrich_gaokao_diagnosis, ocr_quality_score


class QualityGateTests(unittest.TestCase):
    def test_ocr_quality_rewards_confidence_and_usable_questions(self):
        low = {"page_confidence": .4, "questions": [{"printed_text": "1"}]}
        high = {"page_confidence": .9, "questions": [{"printed_text": "一道完整可识别的题目"}]}
        self.assertGreater(ocr_quality_score(high), ocr_quality_score(low))

    def test_diagnosis_gets_scoring_points_and_quality_flags(self):
        result = enrich_gaokao_diagnosis(
            {"printed_text": "已知函数，讨论导数与单调区间", "student_work": "令导数为零"},
            {"student_answer_analysis": {"extracted_work": "令导数为零"}, "standard_answer": {}},
            "数学",
        )
        self.assertTrue(result["quality_gate"]["has_scoring_points"])
        self.assertTrue(result["quality_gate"]["has_mother_evidence"])


if __name__ == "__main__":
    unittest.main()
