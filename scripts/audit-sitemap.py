import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://kkwang4444.github.io/aifast-developer-hub/'
NAMESPACE = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs.get('href'))

    def handle_data(self, text):
        self.text.append(text)


def audit(root=ROOT):
    sitemap = ElementTree.parse(root / 'sitemap.xml')
    seen = set()
    for entry in sitemap.findall('s:url', NAMESPACE):
        url = entry.findtext('s:loc', namespaces=NAMESPACE)
        assert url and url.startswith(BASE), f'站点地图包含非本仓库地址：{url}'
        assert url not in seen, f'重复地址：{url}'
        seen.add(url)
        relative = url[len(BASE):]
        path = (root / relative / 'index.html').resolve()
        assert path.is_relative_to(root.resolve()) and path.is_file(), f'页面不存在：{url}'
        page = Page()
        page.feed(path.read_text(encoding='utf-8'))
        assert page.canonical == [url], f'Canonical 与 Sitemap 不一致：{url}'
        changed = date.fromisoformat(entry.findtext('s:lastmod', namespaces=NAMESPACE))
        assert changed <= date.today(), f'更新时间在未来：{url}'
        # 仅将页面明确标注的更新日期作为下限，不把所有文章日期当作发布日期。
        dates = re.findall(r'(?:Checked on|Updated)\s+(\d{4}-\d{2}-\d{2})', ' '.join(page.text))
        assert all(changed >= date.fromisoformat(value) for value in dates), f'Sitemap 日期早于正文更新：{url}'
    assert BASE in seen, 'Sitemap 缺少首页'
    return len(seen)


if __name__ == '__main__':
    print(f'Sitemap 审计通过：{audit()} 个页面，日期与 Canonical 一致。')
