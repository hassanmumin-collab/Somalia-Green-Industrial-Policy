"""Tests for extract.py, build.py and the hook entry point."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

import build  # noqa: E402
import extract  # noqa: E402
import fixture  # noqa: E402
import verify  # noqa: E402


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(fixture.cleanup, self.tmp)

    def test_pdf_page_markers_and_quote_matching(self):
        import pymupdf
        pdf = self.tmp / "a.pdf"
        doc = pymupdf.open()
        for text in ("First page about livestock exports.", "GDP reached US$13.2 billion in 2025."):
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.save(pdf)
        doc.close()
        pages, method, missing = extract.extract_file(pdf)
        self.assertEqual(len(pages), 2)
        self.assertEqual(method, "text")
        out = self.tmp / "a.txt"
        extract.write_text(pages, out)
        pm = verify.split_pages(out.read_text(encoding="utf-8"))
        self.assertTrue(verify.quote_in("GDP reached US$13.2 billion", pm[2]))
        self.assertFalse(verify.quote_in("GDP reached US$13.2 billion", pm[1]))

    def test_image_only_pdf_page_is_reported_not_silently_empty(self):
        import pymupdf
        pdf = self.tmp / "scan.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
        pix.clear_with(200)
        page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pix)
        doc.save(pdf)
        doc.close()
        pages, method, missing = extract.extract_file(pdf)
        if not extract.ocr_available():
            self.assertEqual(missing, [1])

    def test_docx(self):
        docx = self.tmp / "a.docx"
        w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        body = (f'<w:document {w}><w:body>'
                '<w:p><w:r><w:t>Law No. 22 of 2024</w:t></w:r></w:p>'
                '<w:p><w:r><w:br w:type="page"/><w:t>Second page text</w:t></w:r></w:p>'
                '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell A</w:t></w:r></w:p></w:tc>'
                '<w:tc><w:p><w:r><w:t>Cell B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
                '</w:body></w:document>')
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr("word/document.xml", body)
        pages, method, _ = extract.extract_file(docx)
        self.assertEqual(len(pages), 2)
        self.assertIn("Law No. 22 of 2024", pages[0])
        self.assertIn("Cell A | Cell B", pages[1])

    def test_html(self):
        h = self.tmp / "a.html"
        h.write_text("<html><head><style>x{}</style><script>var a=1</script></head>"
                     "<body><p>GDP was <b>USD 13.2 billion</b>.</p><table><tr><td>A</td><td>1</td></tr></table></body></html>",
                     encoding="utf-8")
        pages, _, _ = extract.extract_file(h)
        self.assertIn("GDP was USD 13.2 billion.", pages[0])
        self.assertNotIn("var a", pages[0])

    def test_xlsx_one_page_per_sheet_rows_as_pipes(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fuels"
        ws.append(["Fuel", "Unit", "kg CO2e"])
        ws.append(["Diesel (100% mineral diesel)", "litres", 2.66155, None])
        wb.create_sheet("Notes").append(["Second sheet"])
        x = self.tmp / "a.xlsx"
        wb.save(x)
        pages, method, _ = extract.extract_file(x)
        self.assertEqual(len(pages), 2)
        self.assertIn("# Sheet: Fuels", pages[0])
        self.assertIn("Diesel (100% mineral diesel) | litres | 2.66155", pages[0])
        self.assertFalse(pages[0].rstrip().endswith("|"))
        self.assertIn("Second sheet", pages[1])

    def test_geojson_is_read_as_text(self):
        g = self.tmp / "a.geojson"
        g.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
        pages, method, _ = extract.extract_file(g)
        self.assertEqual(method, "text")
        self.assertIn("FeatureCollection", pages[0])

    def test_unknown_extension_is_rejected(self):
        g = self.tmp / "a.xyz"
        g.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            extract.extract_file(g)


@unittest.skipUnless(build.find_pandoc(), "pandoc not installed")
class TestBuild(unittest.TestCase):
    def test_build_resolves_footnotes(self):
        root = fixture.build(fixture.spec())
        self.addCleanup(fixture.cleanup, root)
        rc = build.main(["--root", str(root), "--no-pdf", "--out", "test"])
        self.assertEqual(rc, 0)
        docx = root / "report" / "build" / "test.docx"
        self.assertTrue(docx.exists())
        with zipfile.ZipFile(docx) as z:
            notes = z.read("word/footnotes.xml").decode("utf-8")
            doc = z.read("word/document.xml").decode("utf-8")
        self.assertIn("Test Bureau of Statistics", notes)
        self.assertIn("Calculated from", notes)
        self.assertIn("Modelled estimate, base scenario", notes)
        self.assertNotIn("{{C-", doc)
        self.assertIn("Verification statement", doc)

    def test_build_refused_when_verifier_fails(self):
        s = fixture.spec()
        s["chapters"]["09_bad.md"] = "# Bad\n\nThere are 12 parks.\n"
        root = fixture.build(s)
        self.addCleanup(fixture.cleanup, root)
        self.assertEqual(build.main(["--root", str(root), "--no-pdf", "--out", "test"]), 2)
        self.assertFalse((root / "report" / "build" / "test.docx").exists())


class TestHook(unittest.TestCase):
    def run_hook(self, root, event, payload):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        return subprocess.run([sys.executable, str(TOOLS / "hook.py"), event], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def setUp(self):
        s = fixture.spec()
        s["chapters"]["09_bad.md"] = "# Bad\n\nThere are 12 parks.\n"
        self.bad = fixture.build(s)
        self.good = fixture.build(fixture.spec())
        self.addCleanup(fixture.cleanup, self.bad)
        self.addCleanup(fixture.cleanup, self.good)
        # tools/verify.py must exist under the fixture root for the hook to call it
        for r in (self.bad, self.good):
            (r / "tools").mkdir(exist_ok=True)
            (r / "tools" / "verify.py").write_text((TOOLS / "verify.py").read_text(encoding="utf-8"), encoding="utf-8")

    def test_post_blocks_on_failure_in_watched_path(self):
        r = self.run_hook(self.bad, "post", {"tool_input": {"file_path": str(self.bad / "report" / "chapters" / "09_bad.md")}})
        self.assertEqual(r.returncode, 2)
        self.assertIn("12", r.stderr)

    def test_post_ignores_unwatched_path(self):
        r = self.run_hook(self.bad, "post", {"tool_input": {"file_path": str(self.bad / "tools" / "x.py")}})
        self.assertEqual(r.returncode, 0)

    def test_post_passes_on_good_project(self):
        r = self.run_hook(self.good, "post", {"tool_input": {"file_path": str(self.good / "data" / "claims.yaml")}})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_stop_blocks_then_releases_when_stop_hook_active(self):
        r = self.run_hook(self.bad, "stop", {"stop_hook_active": False})
        self.assertEqual(r.returncode, 2)
        r = self.run_hook(self.bad, "stop", {"stop_hook_active": True})
        self.assertEqual(r.returncode, 0)
        self.assertIn("systemMessage", r.stdout)
        self.assertTrue((self.bad / "reports" / "verification_report.md").exists())

    def test_stop_passes_on_good_project(self):
        self.assertEqual(self.run_hook(self.good, "stop", {"stop_hook_active": False}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
