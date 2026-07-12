import unittest
from latex_pipeline import convert_bytes, detect_paste_format, text_to_latex

class LatexPipelineTests(unittest.TestCase):
    def test_detects_latex_magic_paste(self): self.assertEqual(detect_paste_format(r"\frac{1}{2}"), "latex")
    def test_wraps_chinese_and_preserves_math(self):
        result=text_to_latex("已知 $x^2=1$，求解。", "测试卷")
        self.assertIn(r"\documentclass[UTF8]{ctexart}", result)
        self.assertIn("$x^2=1$", result)
        self.assertIn("测试卷", result)
    def test_embedded_formula_images_require_review(self):
        import unittest.mock as mock
        with mock.patch("latex_pipeline.convert_with_pandoc", return_value=r"\includegraphics{x.wmf}"):
            result=convert_bytes("卷.docx", b"x", "")
        self.assertTrue(result["requires_formula_review"])
        self.assertEqual(result["embedded_formula_images"], 2)

if __name__ == "__main__": unittest.main()
