"""Exercise PDF functions without starting Streamlit or calling an AI model."""
import ast
import base64
import re
import unittest
from pathlib import Path

import pymupdf as fitz


names = {"has_word_boundaries", "is_known_label_text", "text_style_at", "text_width",
         "render_template", "render_filled_template", "build_preview", "normalize_name"}
tree = ast.parse(Path(__file__).with_name("app.py").read_text(encoding="utf-8-sig"))
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
         or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "LABEL_KEYS" for target in node.targets)]
pdf_functions = {"fitz": fitz, "re": re, "base64": base64}
exec(compile(ast.Module(body=nodes, type_ignores=[]), "app_pdf_functions", "exec"), pdf_functions)


class PdfRenderingTests(unittest.TestCase):
    def source(self, rotation=0):
        with fitz.open() as doc:
            page = doc.new_page()
            font = fitz.Font("cjk")
            page.insert_font(fontname="embedded_source", fontbuffer=font.buffer)
            page.insert_text((40, 80), "Employee: Alice Example", fontname="embedded_source", fontsize=11)
            page.set_rotation(rotation)
            return doc.tobytes()

    def template(self, rotation=0):
        fields = [{"replace": True, "original": "Alice Example", "placeholder": "EMPLOYEE_NAME"}]
        output, warnings = pdf_functions["render_template"](self.source(rotation), fields)
        self.assertFalse(warnings)
        return output, fields

    def test_embedded_source_font_produces_searchable_placeholder(self):
        output, fields = self.template()
        with fitz.open(stream=output, filetype="pdf") as doc:
            self.assertTrue(doc[0].search_for("{{EMPLOYEE_NAME}}"))
            self.assertNotIn("Alice Example", doc[0].get_text())
            self.assertNotIn("\ufffd", doc[0].get_text())
        _, targets = pdf_functions["build_preview"](output, fields)
        self.assertEqual(len(targets), 1)

    def test_unicode_replacement_remains_readable(self):
        output, _ = self.template()
        value = "Zoë 李明"
        filled = pdf_functions["render_filled_template"](output, {"EMPLOYEE_NAME": value})
        with fitz.open(stream=filled, filetype="pdf") as doc:
            self.assertTrue(doc[0].search_for(value))
            self.assertNotIn("\ufffd", doc[0].get_text())

    def test_rotated_targets_match_display_coordinates(self):
        for angle in (0, 90, 180, 270):
            with self.subTest(angle=angle):
                output, fields = self.template(angle)
                pages, targets = pdf_functions["build_preview"](output, fields)
                with fitz.open(stream=output, filetype="pdf") as doc:
                    rect = doc[0].search_for("{{EMPLOYEE_NAME}}")[0] * doc[0].rotation_matrix
                    self.assertEqual(targets[0]["rect"], list(rect))
                    self.assertEqual(pages[0]["width"], doc[0].rect.width)
                    self.assertEqual(pages[0]["height"], doc[0].rect.height)

    def test_long_filled_value_expands_click_target(self):
        output, fields = self.template()
        value = "A very long replacement employee name for testing"
        filled = pdf_functions["render_filled_template"](output, {"EMPLOYEE_NAME": value})
        _, original_targets = pdf_functions["build_preview"](output, fields)
        _, targets = pdf_functions["build_preview"](filled, fields, target_bytes=output,
                                                   preview_values={"EMPLOYEE_NAME": value})
        self.assertGreater(targets[0]["rect"][2], original_targets[0]["rect"][2])

    def test_replacements_do_not_add_background_boxes_or_annotations(self):
        with fitz.open() as source:
            page = source.new_page()
            page.draw_rect(page.rect, fill=(0.8, 0.9, 1), color=None)
            page.insert_text((40, 80), "Employee: Alice Example")
            source_bytes = source.tobytes()
        fields = [{"replace": True, "original": "Alice Example", "placeholder": "EMPLOYEE_NAME"}]
        template, _ = pdf_functions["render_template"](source_bytes, fields)
        filled = pdf_functions["render_filled_template"](template, {"EMPLOYEE_NAME": "Zoë Example"})
        for output in (template, filled):
            with fitz.open(stream=output, filetype="pdf") as doc:
                page = doc[0]
                drawings = page.get_drawings()
                self.assertEqual(len(drawings), 1, "Replacement must not paint extra rectangles")
                self.assertAlmostEqual(drawings[0]["fill"][0], 0.8, places=5)
                self.assertEqual(list(page.annots()), [])
                self.assertNotIn("Alice Example", page.get_text())
                pix = page.get_pixmap()
                self.assertEqual(pix.pixel(115, 69), pix.pixel(20, 20))


if __name__ == "__main__":
    unittest.main()
