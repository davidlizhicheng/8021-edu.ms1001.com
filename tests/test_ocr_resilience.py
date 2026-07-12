import unittest
from unittest.mock import patch
import base64
from io import BytesIO

import server


class OcrResponseResilienceTests(unittest.TestCase):
    def test_accepts_fenced_json_with_trailing_commas(self):
        raw = '''```json
        {"page_text":"第1题", "page_confidence":0.8,
         "questions":[{"question_no":"1","printed_text":"计算 1+1",}],}
        ```'''
        result = server.parse_paper_ocr_response(raw)
        self.assertEqual(result["questions"][0]["printed_text"], "计算 1+1")
        self.assertTrue(result["response_repaired"])

    def test_preserves_plain_ocr_text_as_numbered_questions(self):
        raw = "1. 计算 1+1\n学生答案：3\n2. 计算 2+2"
        result = server.parse_paper_ocr_response(raw)
        self.assertEqual(result["page_text"], raw)
        self.assertEqual([item["question_no"] for item in result["questions"]], ["1", "2"])
        self.assertEqual(result["parse_mode"], "text_fallback")

    def test_recovers_page_text_from_truncated_json(self):
        raw = '{"page_text":"1. 第一题\\n2. 第二题","page_confidence":0.7,"questions":[{"question_no":"1"'
        result = server.parse_paper_ocr_response(raw)
        self.assertIn("第一题", result["page_text"])
        self.assertGreaterEqual(len(result["questions"]), 2)
        self.assertEqual(result["parse_mode"], "truncated_json_fallback")

    def test_normalizes_unsafe_question_fields(self):
        raw = '{"page_text":"题目","page_confidence":4,"questions":[{"question_no":1,"printed_text":"题干","answer_state":"maybe","confidence":-2,"bbox":[-1,2,4,9]}]}'
        result = server.parse_paper_ocr_response(raw)
        question = result["questions"][0]
        self.assertEqual(result["page_confidence"], 1.0)
        self.assertEqual(question["answer_state"], "review_required")
        self.assertEqual(question["confidence"], 0.0)
        self.assertEqual(question["bbox"], [0.0, 1.0, 1.0, 1.0])


class OcrRetryPolicyTests(unittest.TestCase):
    def test_usable_result_only_calls_model_once(self):
        good = {
            "page_text": "1. 这是一个完整题目",
            "page_confidence": 0.76,
            "questions": [{"question_no": "1", "printed_text": "这是一个完整题目", "confidence": 0.7}],
        }
        with patch.object(server, "run_paper_ocr", return_value=good) as mocked:
            result = server.best_of_two_paper_ocr("data:image/jpeg;base64,AA==")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(result["recognition_attempts"], 1)

    def test_unusable_result_retries_only_once(self):
        poor = {"page_text": "", "page_confidence": 0.1, "questions": []}
        better = {
            "page_text": "1. 可用题目",
            "page_confidence": 0.75,
            "questions": [{"question_no": "1", "printed_text": "可用题目正文", "confidence": 0.7}],
        }
        with patch.object(server, "run_paper_ocr", side_effect=[poor, better]) as mocked:
            result = server.best_of_two_paper_ocr("data:image/jpeg;base64,AA==")
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(result["recognition_attempts"], 2)
        self.assertEqual(result["questions"][0]["question_no"], "1")


class OcrImageNormalizationTests(unittest.TestCase):
    def test_downscales_large_page_before_model_upload(self):
        from PIL import Image

        source = Image.new("RGB", (3200, 2400), "white")
        buffer = BytesIO()
        source.save(buffer, format="JPEG", quality=95)
        original = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        normalized, metadata = server.normalize_ocr_image_data_url(original, max_long_side=2200)
        payload = base64.b64decode(normalized.split(",", 1)[1])
        with Image.open(BytesIO(payload)) as output:
            self.assertLessEqual(max(output.size), 2200)
        self.assertTrue(metadata["processed"])
        self.assertLess(len(payload), len(buffer.getvalue()))

    def test_invalid_image_falls_back_to_original(self):
        original = "data:image/jpeg;base64,AA=="
        normalized, metadata = server.normalize_ocr_image_data_url(original)
        self.assertEqual(normalized, original)
        self.assertFalse(metadata["processed"])


if __name__ == "__main__":
    unittest.main()
