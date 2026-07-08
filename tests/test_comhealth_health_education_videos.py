from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

VIDEO_ADMIN_PATH = PROJECT_ROOT / 'app' / 'comhealth' / 'video_admin.py'
VIDEO_ADMIN_SPEC = importlib.util.spec_from_file_location('comhealth_video_admin_test', VIDEO_ADMIN_PATH)
VIDEO_ADMIN = importlib.util.module_from_spec(VIDEO_ADMIN_SPEC)
assert VIDEO_ADMIN_SPEC is not None and VIDEO_ADMIN_SPEC.loader is not None
VIDEO_ADMIN_SPEC.loader.exec_module(VIDEO_ADMIN)

build_health_education_video_attributes = VIDEO_ADMIN.build_health_education_video_attributes
build_youtube_embed_url = VIDEO_ADMIN.build_youtube_embed_url
extract_youtube_video_id = VIDEO_ADMIN.extract_youtube_video_id
filter_health_education_videos = VIDEO_ADMIN.filter_health_education_videos
is_valid_youtube_url = VIDEO_ADMIN.is_valid_youtube_url
normalize_csv_values = VIDEO_ADMIN.normalize_csv_values
persist_health_education_video = VIDEO_ADMIN.persist_health_education_video


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


class FakeVideo:
    _seq = 0

    def __init__(self):
        FakeVideo._seq += 1
        self.id = FakeVideo._seq
        self.title = ''
        self.youtube_url = ''
        self.youtube_video_id = ''
        self.source_name = ''
        self.source_channel = ''
        self.health_topics = []
        self.keywords = []
        self.summary = ''
        self.language = ''
        self.audience_level = ''
        self.is_active = True
        self.is_embeddable = True
        self.thumbnail_url = None
        self.duration_seconds = None
        self.display_order = None
        self.notes_internal = None


def test_extracts_youtube_video_id_from_common_url_patterns():
    assert extract_youtube_video_id('https://www.youtube.com/watch?v=dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    assert extract_youtube_video_id('https://youtu.be/dQw4w9WgXcQ?t=1') == 'dQw4w9WgXcQ'
    assert extract_youtube_video_id('https://www.youtube.com/shorts/dQw4w9WgXcQ') == 'dQw4w9WgXcQ'
    assert build_youtube_embed_url('dQw4w9WgXcQ') == 'https://www.youtube.com/embed/dQw4w9WgXcQ'


def test_rejects_invalid_youtube_urls():
    assert not is_valid_youtube_url('https://example.com/watch?v=dQw4w9WgXcQ')
    with pytest.raises(ValueError):
        build_health_education_video_attributes({
            'title': 'Invalid',
            'youtube_url': 'https://example.com/watch?v=dQw4w9WgXcQ',
            'health_topics': 'obesity',
        })


def test_rejects_non_numeric_duration_and_display_order():
    with pytest.raises(ValueError, match='Duration Seconds must be a number'):
        build_health_education_video_attributes({
            'title': 'Invalid duration',
            'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'health_topics': 'obesity',
            'duration_seconds': 'abc',
        })


def test_parses_topics_and_keywords_from_comma_separated_inputs():
    attrs = build_health_education_video_attributes({
        'title': 'Healthy Weight',
        'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'source_name': '',
        'source_channel': 'Mahidol University',
        'health_topics': ' obesity, diabetes risk, exercise, obesity ',
        'keywords': 'blood sugar, diet, walking',
        'summary': 'Short summary',
        'language': 'th',
        'audience_level': 'general',
        'is_active': '1',
        'is_embeddable': '0',
        'thumbnail_url': 'https://example.test/thumb.jpg',
        'duration_seconds': '123',
        'display_order': '2',
        'notes_internal': 'Admin note',
    })

    assert attrs['youtube_video_id'] == 'dQw4w9WgXcQ'
    assert attrs['source_name'] == 'Mahidol University YouTube'
    assert attrs['health_topics'] == ['obesity', 'diabetes risk', 'exercise']
    assert attrs['keywords'] == ['blood sugar', 'diet', 'walking']
    assert attrs['is_active'] is True
    assert attrs['is_embeddable'] is False
    assert attrs['thumbnail_url'] == 'https://example.test/thumb.jpg'
    assert attrs['duration_seconds'] == 123
    assert attrs['display_order'] == 2
    assert attrs['notes_internal'] == 'Admin note'


def test_normalize_csv_values_deduplicates_and_trims():
    assert normalize_csv_values(' a, b , a, , c ') == ['a', 'b', 'c']


def test_creating_video_persists_expected_fields_and_commits():
    session = FakeSession()

    attrs = build_health_education_video_attributes({
        'title': 'Exercise for hypertension',
        'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'source_name': 'Mahidol University YouTube',
        'source_channel': 'Mahidol Channel',
        'health_topics': 'hypertension, exercise',
        'keywords': 'blood pressure, walk',
        'summary': 'Short summary',
        'language': 'th',
        'audience_level': 'general',
        'is_active': 'true',
        'is_embeddable': 'true',
    })

    video = persist_health_education_video(
        session,
        FakeVideo,
        attrs,
        duplicate_lookup=lambda _video_id: None,
    )

    assert session.commits == 1
    assert session.added == [video]
    assert video.title == 'Exercise for hypertension'
    assert video.youtube_video_id == 'dQw4w9WgXcQ'
    assert video.health_topics == ['hypertension', 'exercise']
    assert video.keywords == ['blood pressure', 'walk']
    assert video.is_active is True
    assert video.is_embeddable is True


def test_editing_video_updates_existing_record_without_duplicate_error():
    session = FakeSession()
    existing = FakeVideo()
    existing.id = 99
    existing.youtube_video_id = 'old-id'

    attrs = build_health_education_video_attributes({
        'title': 'Updated title',
        'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'source_name': 'Mahidol University YouTube',
        'source_channel': 'Mahidol Channel',
        'health_topics': 'stress management',
        'keywords': 'sleep',
        'summary': 'Updated summary',
        'language': 'en',
        'audience_level': 'beginner',
        'is_active': 'false',
        'is_embeddable': 'false',
    })

    updated = persist_health_education_video(
        session,
        FakeVideo,
        attrs,
        existing_video=existing,
        duplicate_lookup=lambda _video_id: SimpleNamespace(id=99),
    )

    assert updated is existing
    assert updated.title == 'Updated title'
    assert updated.youtube_video_id == 'dQw4w9WgXcQ'
    assert updated.is_active is False
    assert updated.is_embeddable is False
    assert session.commits == 1


def test_duplicate_youtube_video_ids_are_rejected():
    session = FakeSession()

    attrs = build_health_education_video_attributes({
        'title': 'Duplicate',
        'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'health_topics': 'obesity',
    })

    with pytest.raises(ValueError, match='already exists'):
        persist_health_education_video(
            session,
            FakeVideo,
            attrs,
            duplicate_lookup=lambda _video_id: SimpleNamespace(id=1),
        )


def test_filtering_by_topic_keyword_language_and_active_status():
    videos = [
        SimpleNamespace(
            title='A',
            health_topics=['obesity', 'exercise'],
            keywords=['diet'],
            language='th',
            is_active=True,
        ),
        SimpleNamespace(
            title='B',
            health_topics=['diabetes risk'],
            keywords=['blood sugar'],
            language='en',
            is_active=False,
        ),
    ]

    filtered = filter_health_education_videos(videos, topic='obesity', keyword='diet', language='th', is_active='true')
    assert [video.title for video in filtered] == ['A']

    filtered = filter_health_education_videos(videos, is_active='false')
    assert [video.title for video in filtered] == ['B']
