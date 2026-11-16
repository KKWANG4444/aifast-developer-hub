import importlib.util
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('audit_sitemap', ROOT / 'scripts/audit-sitemap.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SitemapTests(unittest.TestCase):
    def test_current_sitemap(self):
        self.assertEqual(MODULE.audit(), 2)

    def test_hong_kong_midnight_boundary(self):
        tree = ElementTree.parse(ROOT / 'sitemap.xml')
        latest = max(date.fromisoformat(item.text) for item in tree.findall('s:url/s:lastmod', MODULE.NAMESPACE))
        midnight = datetime.combine(latest, time(), timezone(timedelta(hours=8))).astimezone(timezone.utc)
        self.assertEqual(MODULE.audit(now=midnight), 2)
        with self.assertRaisesRegex(AssertionError, '更新时间在未来'):
            MODULE.audit(now=midnight - timedelta(seconds=1))

    def test_stale_date_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text((ROOT / 'index.html').read_text(), encoding='utf-8')
            (root / 'sitemap.xml').write_text(
                (ROOT / 'sitemap.xml').read_text().replace('2026-11-17', '2026-09-01'), encoding='utf-8')
            with self.assertRaisesRegex(AssertionError, '日期早于正文更新'):
                MODULE.audit(root)


if __name__ == '__main__':
    unittest.main()
