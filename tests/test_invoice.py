import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from invoice_generator import compute_totals, generate  # noqa: E402


def load_example(name):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


class TotalsTests(unittest.TestCase):
    def test_totals_math(self):
        inv = load_example("invoice-en.json")
        totals = compute_totals(inv)
        self.assertEqual(totals["subtotal"], 10250.0)   # 8000 + 1500 + 3*250
        self.assertEqual(totals["discount"], 250.0)
        self.assertEqual(totals["tax"], 1400.0)          # 14% of 10000
        self.assertEqual(totals["grand"], 11400.0)

    def test_no_discount_no_tax(self):
        inv = {"items": [{"description": "x", "qty": 2, "unit_price": 100}]}
        totals = compute_totals(inv)
        self.assertEqual(totals["subtotal"], 200.0)
        self.assertEqual(totals["tax"], 0)
        self.assertEqual(totals["grand"], 200.0)

    def test_discount_never_below_zero(self):
        inv = {"items": [{"description": "x", "qty": 1, "unit_price": 50}], "discount": 100}
        self.assertEqual(compute_totals(inv)["grand"], 0)


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _check_pdf(self, path, min_pages=1):
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 5000)  # embedded fonts make real PDFs chunky
        pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
        self.assertGreaterEqual(pages, min_pages)

    def test_english_pdf(self):
        out = self.dir / "en.pdf"
        generate(load_example("invoice-en.json"), str(out), lang="en")
        self._check_pdf(out)

    def test_arabic_pdf(self):
        out = self.dir / "ar.pdf"
        generate(load_example("invoice-ar.json"), str(out), lang="ar")
        self._check_pdf(out)

    def test_bilingual_pdf_has_two_pages(self):
        out = self.dir / "both.pdf"
        generate(load_example("invoice-ar.json"), str(out), lang="both")
        self._check_pdf(out, min_pages=2)


if __name__ == "__main__":
    unittest.main()
