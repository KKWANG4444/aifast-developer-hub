import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('audit_sitemap', ROOT / 'scripts/audit-sitemap.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SitemapTests(unittest.TestCase):
    def test_current_sitemap(self):
        self.assertEqual(MODULE.audit(), 2)

    def test_stale_date_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text((ROOT / 'index.html').read_text(), encoding='utf-8')
            (root / 'sitemap.xml').write_text(
                (ROOT / 'sitemap.xml').read_text().replace('2026-11-10', '2026-09-01'), encoding='utf-8')
            with self.assertRaisesRegex(AssertionError, '日期早于正文更新'):
                MODULE.audit(root)


if __name__ == '__main__':
    unittest.main()
