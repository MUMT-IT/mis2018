"""Small, dependency-free helpers for inspecting public organization pages."""

from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urldefrag, urljoin, urlparse

import requests


DEFAULT_DIRECTORY_URL = 'https://mt.mahidol.ac.th/department-th/department-of-clinical-chemistry/'
CURRENT_DIRECTORY_URL = 'https://mt.mahidol.ac.th/en/departments/department-of-clinical-chemistry-en/'

ACADEMIC_RANK_PATTERNS = (
    (re.compile(r'(?:^|\s)ศ\.?(?:\s|$)'), 'ศาสตราจารย์'),
    (re.compile(r'(?:^|\s)รศ\.?(?:\s|$)'), 'รองศาสตราจารย์'),
    (re.compile(r'(?:^|\s)ผศ\.?(?:\s|$)'), 'ผู้ช่วยศาสตราจารย์'),
    (re.compile(r'(?:^|\s)อ\.?(?:\s|$)'), 'อาจารย์'),
    (re.compile(r'(?:^|\s)อาจารย์(?:\s|$)'), 'อาจารย์'),
)
POSITION_LEVELS = ('ชำนาญการพิเศษ', 'ชำนาญการ', 'เชี่ยวชาญ', 'ทรงคุณวุฒิ', 'ปฏิบัติการ')


def normalize_position(text):
    """Split a non-academic position into position and analytics level."""
    raw = ' '.join(text or '').split() if not isinstance(text, str) else ' '.join(text.split())
    if not raw:
        return {'raw_position': None, 'position': None, 'position_level': None}
    for level in POSITION_LEVELS:
        if raw.endswith(level):
            position = raw[:-len(level)].strip(' -–—') or None
            return {'raw_position': raw, 'position': position, 'position_level': level}
    return {'raw_position': raw, 'position': raw, 'position_level': None}


def academic_rank_from_name(name):
    """Return the normalized academic rank represented by a scraped name."""
    value = ' '.join(name or '').split() if not isinstance(name, str) else ' '.join(name.split())
    for pattern, rank in ACADEMIC_RANK_PATTERNS:
        if pattern.search(value):
            return rank
    return None


def email_local_part(email):
    """Return the portion before @ for matching local and full email values."""
    return (email or '').strip().lower().split('@', 1)[0]


class _PageParser(HTMLParser):
    """Collect visible text and links without assuming a site's CSS framework."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self.links = []
        self._skip_depth = 0
        self._active_link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'noscript', 'svg', 'style'}:
            self._skip_depth += 1
        if tag == 'a' and attrs.get('href'):
            self.links.append((attrs['href'], ''))
            self._active_link = len(self.links) - 1

    def handle_endtag(self, tag):
        if tag in {'script', 'noscript', 'svg', 'style'} and self._skip_depth:
            self._skip_depth -= 1
        if tag == 'a':
            self._active_link = None

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = ' '.join(data.split())
        if not text:
            return
        self.text_parts.append(text)
        if self._active_link is not None:
            href, label = self.links[self._active_link]
            self.links[self._active_link] = (href, ' '.join(filter(None, [label, text])))


class _EmployeeParser(HTMLParser):
    """Extract employee blocks from the saved WPBakery tab layout."""

    EMAIL_RE = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
    PHONE_RE = re.compile(r'(?:โทร|Tel|โทรสาร|Fax)?\.?\s*[+\d][\d()\-\s]{6,}')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self._block_depth = 0
        self._block_tag_depth = 0
        self._texts = []
        self._role_parts = []
        self._in_heading = False
        self._pending_image_url = None
        self._profile_url = None

    @staticmethod
    def _classes(attrs):
        return set((dict(attrs).get('class') or '').split())

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = self._classes(attrs)
        if self._block_depth == 0 and 'vc_tta-panel-body' in classes:
            self._block_depth = 1
            self._block_tag_depth = 1
            self._texts = []
            self._role_parts = []
            self._pending_image_url = None
            self._profile_url = None
            return
        if self._block_depth:
            if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self._block_tag_depth += 1
            if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                self._in_heading = True
            if tag == 'img':
                self._pending_image_url = attrs_dict.get('data-lazy-src') or attrs_dict.get('src')
            if tag == 'a' and attrs_dict.get('href'):
                href = attrs_dict['href']
                if 'profile' in href.lower() or 'person' in href.lower() or self._profile_url is None:
                    self._profile_url = href

    def handle_endtag(self, tag):
        if not self._block_depth:
            return
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self._in_heading = False
        self._block_tag_depth -= 1
        if self._block_tag_depth <= 0:
            self._finish_record()
            self._block_depth = 0

    def handle_data(self, data):
        if not self._block_depth:
            return
        text = ' '.join(data.split())
        if not text:
            return
        self._texts.append(text)
        if self._in_heading:
            self._role_parts.append(text)

    def _finish_record(self):
        lines = [line.strip() for line in self._texts if line.strip()]
        role = ' '.join(self._role_parts).strip() or None
        email = next((self.EMAIL_RE.search(line).group(0) for line in lines if self.EMAIL_RE.search(line)), None)
        phone = next((self.PHONE_RE.search(line).group(0).strip() for line in lines if self.PHONE_RE.search(line) and not self.EMAIL_RE.search(line)), None)
        candidates = [line for line in lines if line != role and not self.EMAIL_RE.search(line) and line != phone and line.lower() not in {'profile', 'ดูรายละเอียด'}]
        name = candidates[0] if candidates else None
        position_data = normalize_position(None)
        self.records.append({
            'name': name,
            'position': position_data['position'],
            'raw_position': position_data['raw_position'],
            'position_level': position_data['position_level'],
            'academic_rank': academic_rank_from_name(name),
            'role': role,
            'email': email,
            'phone': phone,
            'profile_url': self._profile_url,
            'image_url': self._pending_image_url,
        })


def fetch_page(url, timeout=20):
    """Fetch one page and return response metadata plus parsed text and links."""
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('URL must use http or https')
    response = requests.get(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,th;q=0.8',
        },
        timeout=timeout,
    )
    response.raise_for_status()
    parser = _PageParser()
    parser.feed(response.text)
    return {
        'url': response.url,
        'status': response.status_code,
        'content_type': response.headers.get('Content-Type', ''),
        'text': parser.text_parts,
        'links': parser.links,
    }


def fetch_page_with_browser(url, timeout=20):
    """Fetch a page with Chromium for sites that reject plain HTTP clients."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError('Playwright is not installed in the Python environment running Flask') from exc
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('URL must use http or https')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36', locale='en-US')
        response = page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
        page.wait_for_timeout(1500)
        parser = _PageParser()
        parser.feed(page.content())
        result = {
            'url': page.url,
            'status': response.status if response else None,
            'content_type': response.header_value('content-type') if response else '',
            'text': parser.text_parts,
            'links': parser.links,
        }
        browser.close()
        return result


def parse_saved_page(path, source_url=''):
    """Parse an HTML file saved from a permitted browser session."""
    html = Path(path).read_text(encoding='utf-8', errors='replace')
    parser = _EmployeeParser()
    parser.feed(html)
    return {
        'url': source_url,
        'status': None,
        'content_type': 'text/html (saved file)',
        'text': [],
        'links': [],
        'employees': parser.records,
    }


def same_site_links(page, limit=20):
    """Return unique navigational links on the page, restricted to its host."""
    base = urlparse(page['url'])
    results = OrderedDict()
    for href, label in page['links']:
        candidate = urldefrag(urljoin(page['url'], href))[0]
        parsed = urlparse(candidate)
        if parsed.scheme not in {'http', 'https'} or parsed.netloc != base.netloc:
            continue
        results.setdefault(candidate, label)
        if len(results) >= limit:
            break
    return list(results.items())
