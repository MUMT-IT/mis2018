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
        self._events = []
        self._person_segments = []
        self._person_depth = 0
        self._person_events = []
        self._role_parts = []
        self._in_heading = False

    @staticmethod
    def _classes(attrs):
        return set((dict(attrs).get('class') or '').split())

    def handle_startendtag(self, tag, attrs):
        # Saved WordPress pages use self-closing <img /> tags. They are void
        # elements and must not decrement the employee panel depth.
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr',
        }:
            self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = self._classes(attrs)
        if self._block_depth == 0 and 'vc_tta-panel-body' in classes:
            self._block_depth = 1
            self._block_tag_depth = 1
            self._events = []
            self._person_segments = []
            self._person_depth = 0
            self._person_events = []
            self._role_parts = []
            return
        if self._block_depth:
            if self._person_depth == 0 and 'wpb_text_column' in classes:
                self._person_depth = 1
                self._person_events = []
                self._block_tag_depth += 1
                return
            if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self._block_tag_depth += 1
                if self._person_depth:
                    self._person_depth += 1
            if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                self._in_heading = True
            if tag == 'img':
                image_url = self._image_url_from_attrs(attrs_dict)
                if image_url:
                    event = ('image', image_url, attrs_dict.get('alt', ''), attrs_dict.get('class', ''))
                    self._events.append(event)
                    if self._person_depth:
                        self._person_events.append(event)
            style = attrs_dict.get('style', '')
            background_match = re.search(r'background-image\s*:\s*url\(["\']?([^"\')]+)', style, re.I)
            if background_match:
                event = ('image', background_match.group(1), attrs_dict.get('aria-label', ''), attrs_dict.get('class', ''))
                self._events.append(event)
                if self._person_depth:
                    self._person_events.append(event)
            if tag == 'a' and attrs_dict.get('href'):
                event = ('link', attrs_dict['href'])
                self._events.append(event)
                if self._person_depth:
                    self._person_events.append(event)

    def handle_endtag(self, tag):
        if not self._block_depth:
            return
        if self._person_depth:
            if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self._person_depth -= 1
                if self._person_depth == 0:
                    self._person_segments.append(self._person_events)
                    self._person_events = []
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
        self._events.append(('text', text))
        if self._person_depth:
            self._person_events.append(('text', text))
        if self._in_heading:
            self._role_parts.append(text)

    def _finish_record(self):
        role = ' '.join(self._role_parts).strip() or None
        segments = self._person_segments or []
        if not segments:
            email_indexes = [
                index for index, event in enumerate(self._events)
                if event[0] == 'text' and self.EMAIL_RE.search(event[1])
            ]
            for index, email_index in enumerate(email_indexes):
                start = 0 if index == 0 else email_indexes[index - 1] + 1
                end = email_indexes[index + 1] if index + 1 < len(email_indexes) else len(self._events)
                segments.append(self._events[start:end])

        # Some WPBakery layouts put the photo in one text-column and the
        # employee's name/contact details in the following text-column.
        # Carry image/link-only columns forward so they remain attached to the
        # employee whose email appears next.
        merged_segments = []
        pending_segment = []
        for segment in segments:
            has_email = any(event[0] == 'text' and self.EMAIL_RE.search(event[1]) for event in segment)
            if not has_email:
                pending_segment.extend(segment)
                continue
            if pending_segment:
                segment = pending_segment + segment
                pending_segment = []
            merged_segments.append(segment)
        segments = merged_segments

        profile_urls = [event[1] for event in self._events if event[0] == 'link']
        for record_index, segment in enumerate(segments):
            lines = [event[1].strip() for event in segment if event[0] == 'text' and event[1].strip()]
            email_match = next(
                (self.EMAIL_RE.search(line) for line in lines if self.EMAIL_RE.search(line)),
                None,
            )
            if not email_match:
                continue
            email = email_match.group(0)
            phone = next(
                (self.PHONE_RE.search(line).group(0).strip()
                 for line in lines
                 if self.PHONE_RE.search(line) and not self.EMAIL_RE.search(line)),
                None,
            )
            candidates = [
                line for line in lines
                if line != role
                and not self.EMAIL_RE.search(line)
                and not self.PHONE_RE.search(line)
                and line.lower() not in {'profile', 'ดูรายละเอียด'}
            ]
            name = candidates[0] if candidates else None
            position_text = ' '.join(candidates[1:]).strip() if len(candidates) > 1 else None
            position_data = normalize_position(position_text)
            image_url = next(
                (event[1] for event in segment if event[0] == 'image' and not self._is_logo_image(event[1], event[2], event[3])),
                None,
            )
            profile_url = profile_urls[record_index] if record_index < len(profile_urls) else None
            self.records.append({
                'name': name,
                'position': position_data['position'],
                'raw_position': position_data['raw_position'],
                'position_level': position_data['position_level'],
                'academic_rank': academic_rank_from_name(name),
                'role': role,
                'email': email,
                'phone': phone,
                'profile_url': profile_url,
                'image_url': image_url,
            })

    @staticmethod
    def _image_url_from_attrs(attrs):
        for key in ('data-lazy-src', 'data-src', 'data-original', 'data-image', 'src'):
            value = (attrs.get(key) or '').strip()
            if value and not value.startswith('data:image/'):
                return value
        for key in ('data-lazy-srcset', 'data-srcset', 'srcset'):
            value = (attrs.get(key) or '').strip()
            if value:
                return value.split(',')[0].strip().split(' ')[0]
        return None

    @staticmethod
    def _is_logo_image(url, alt='', classes=''):
        value = ' '.join((url or '', alt or '', classes or '')).lower()
        return any(token in value for token in ('murex', 'logo', 'default-avatar', 'placeholder'))


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
