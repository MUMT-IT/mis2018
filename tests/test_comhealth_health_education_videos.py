from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template

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
get_top_related_health_education_videos = VIDEO_ADMIN.get_top_related_health_education_videos
is_valid_youtube_url = VIDEO_ADMIN.is_valid_youtube_url
normalize_csv_values = VIDEO_ADMIN.normalize_csv_values
order_health_education_videos = VIDEO_ADMIN.order_health_education_videos
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


def test_related_videos_are_ranked_by_concern_and_limited_to_three():
    videos = [
        SimpleNamespace(
            title='Diabetes basics',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_video_id='dQw4w9WgXcQ',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['diabetes', 'exercise'],
            keywords=['blood sugar'],
            summary='How to manage blood sugar.',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
            youtube_thumbnail_url='https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
            display_order=2,
            created_at=None,
            updated_at=None,
        ),
        SimpleNamespace(
            title='Heart health',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_video_id='abcdefghijk',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['cardiovascular'],
            keywords=['cholesterol'],
            summary='Heart health guidance.',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/abcdefghijk',
            youtube_thumbnail_url='https://img.youtube.com/vi/abcdefghijk/hqdefault.jpg',
            display_order=1,
            created_at=None,
            updated_at=None,
        ),
        SimpleNamespace(
            title='Kidney care',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_video_id='lmnopqrstuv',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['kidney'],
            keywords=['creatinine'],
            summary='Kidney care guidance.',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/lmnopqrstuv',
            youtube_thumbnail_url='https://img.youtube.com/vi/lmnopqrstuv/hqdefault.jpg',
            display_order=3,
            created_at=None,
            updated_at=None,
        ),
        SimpleNamespace(
            title='Liver care',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_video_id='zyxwvutsrqp',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['liver'],
            keywords=['alt'],
            summary='Liver care guidance.',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/zyxwvutsrqp',
            youtube_thumbnail_url='https://img.youtube.com/vi/zyxwvutsrqp/hqdefault.jpg',
            display_order=4,
            created_at=None,
            updated_at=None,
        ),
    ]

    ordered = order_health_education_videos(videos, concern_keys=['diabetes_risk'])
    assert ordered[0].title == 'Diabetes basics'

    top_three = get_top_related_health_education_videos(videos, concern_keys=['diabetes_risk'], limit=3)
    assert len(top_three) == 3
    assert [video.title for video in top_three] == ['Diabetes basics', 'Heart health', 'Kidney care']


def test_thai_terms_match_related_videos():
    videos = [
        SimpleNamespace(
            title='ดูแลผู้ป่วยเบาหวาน',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            youtube_video_id='dQw4w9WgXcQ',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['เบาหวาน', 'อาหาร'],
            keywords=['น้ำตาลในเลือด'],
            summary='คลิปให้ความรู้เรื่องเบาหวาน',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
            youtube_thumbnail_url='https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
            display_order=1,
            created_at=None,
            updated_at=None,
        ),
        SimpleNamespace(
            title='เรื่องสุขภาพทั่วไป',
            youtube_url='https://www.youtube.com/watch?v=abcdefghijk',
            youtube_video_id='abcdefghijk',
            source_name='Mahidol University YouTube',
            source_channel='Health Channel',
            health_topics=['ทั่วไป'],
            keywords=['สุขภาพ'],
            summary='คลิปทั่วไป',
            language='th',
            audience_level='general',
            is_active=True,
            is_embeddable=True,
            youtube_embed_url='https://www.youtube.com/embed/abcdefghijk',
            youtube_thumbnail_url='https://img.youtube.com/vi/abcdefghijk/hqdefault.jpg',
            display_order=2,
            created_at=None,
            updated_at=None,
        ),
    ]

    top_one = get_top_related_health_education_videos(videos, concern_keys=['diabetes_risk'], limit=1)
    assert [video.title for video in top_one] == ['ดูแลผู้ป่วยเบาหวาน']


def test_videos_page_renders_titles_as_clickable_links():
    app = Flask("test", template_folder=str(PROJECT_ROOT / "app" / "templates"))
    video = SimpleNamespace(
        title='Diabetes basics',
        youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        youtube_embed_url='https://www.youtube.com/embed/dQw4w9WgXcQ',
        is_embeddable=True,
        source_name='Mahidol University YouTube',
        source_channel='Health Channel',
        language='th',
        audience_level='general',
        duration_seconds=245,
        summary='How to manage blood sugar.',
    )

    with app.test_request_context('/comhealth/health-education-videos'):
        rendered = render_template(
            'comhealth/health_education_videos.html',
            current_lang='en',
            ui={
                'videos_page_title': 'Health Education Videos',
                'videos_page_subtitle': 'Browse the full catalog with metadata for each video.',
                'videos_page_back': 'Back to result',
                'related_videos_title': 'Recommended related videos',
                'no_related_videos': 'No related videos are available yet',
                'no_related_videos_help': 'Recommended videos will appear here when the report finds a matching concern.',
            },
            recommended_videos=[video],
            report_url='',
            selected_concern_label='',
        )

    assert 'src="https://www.youtube.com/embed/dQw4w9WgXcQ"' in rendered
    assert 'Diabetes basics' in rendered
    assert 'Source' in rendered
    assert 'Mahidol University YouTube' in rendered
    assert 'Channel' in rendered
    assert 'Health Channel' in rendered
    assert 'Lang' in rendered
    assert 'TH' in rendered
    assert 'Level' in rendered
    assert 'general' in rendered
    assert 'Duration' in rendered
    assert '4m 05s' in rendered
    assert 'How to manage blood sugar.' in rendered
    assert 'All videos' not in rendered
