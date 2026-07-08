from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


DEFAULT_SOURCE_NAME = "Mahidol University YouTube"
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def normalize_csv_values(raw):
    if raw is None:
        return []

    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = str(raw).split(",")

    values = []
    for part in parts:
        value = str(part).strip()
        if value and value not in values:
            values.append(value)
    return values


def _normalize_youtube_netloc(netloc):
    netloc = (netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc.startswith("m."):
        netloc = netloc[2:]
    return netloc


def extract_youtube_video_id(url):
    if not url:
        return None

    parsed = urlparse(url if "://" in url else f"https://{url}")
    netloc = _normalize_youtube_netloc(parsed.netloc)
    path = parsed.path.strip("/")

    if netloc == "youtu.be" and path:
        return path.split("/")[0].split("?")[0]

    if netloc in {"youtube.com", "youtube-nocookie.com"}:
        if path == "watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if path.startswith("embed/"):
            return path.split("/", 1)[1].split("/")[0]
        if path.startswith("shorts/"):
            return path.split("/", 1)[1].split("/")[0]

    return None


def is_valid_youtube_video_id(video_id):
    return bool(video_id and YOUTUBE_VIDEO_ID_RE.match(str(video_id)))


def is_valid_youtube_url(url):
    return is_valid_youtube_video_id(extract_youtube_video_id(url))


def build_youtube_embed_url(youtube_video_id):
    if not is_valid_youtube_video_id(youtube_video_id):
        return None
    return f"https://www.youtube.com/embed/{youtube_video_id}"


def parse_checkbox_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "off", "no", "none"}


def build_health_education_video_attributes(form_data):
    youtube_url = (form_data.get("youtube_url") or "").strip()
    youtube_video_id = extract_youtube_video_id(youtube_url)
    if not youtube_video_id:
        raise ValueError("Please enter a valid YouTube URL.")

    title = (form_data.get("title") or "").strip()
    if not title:
        raise ValueError("Video title is required.")

    source_name = (form_data.get("source_name") or "").strip() or DEFAULT_SOURCE_NAME

    def _parse_optional_int(field_name):
        raw = str(form_data.get(field_name) or "").strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name.replace('_', ' ').title()} must be a number.") from exc

    return {
        "title": title,
        "youtube_url": youtube_url,
        "youtube_video_id": youtube_video_id,
        "source_name": source_name,
        "source_channel": (form_data.get("source_channel") or "").strip(),
        "health_topics": normalize_csv_values(form_data.get("health_topics")),
        "keywords": normalize_csv_values(form_data.get("keywords")),
        "summary": (form_data.get("summary") or "").strip(),
        "language": (form_data.get("language") or "").strip(),
        "audience_level": (form_data.get("audience_level") or "").strip(),
        "is_active": parse_checkbox_value(form_data.get("is_active"), default=True),
        "is_embeddable": parse_checkbox_value(form_data.get("is_embeddable"), default=True),
        "thumbnail_url": (form_data.get("thumbnail_url") or "").strip() or None,
        "duration_seconds": _parse_optional_int("duration_seconds"),
        "display_order": _parse_optional_int("display_order"),
        "notes_internal": (form_data.get("notes_internal") or "").strip() or None,
    }


def apply_health_education_video_attributes(video, attrs):
    for key, value in attrs.items():
        setattr(video, key, value)
    return video


def persist_health_education_video(session, model_cls, attrs, *, existing_video=None, duplicate_lookup=None):
    current_id = getattr(existing_video, "id", None)

    if duplicate_lookup is not None:
        duplicate = duplicate_lookup(attrs["youtube_video_id"])
        duplicate_id = getattr(duplicate, "id", None) if duplicate is not None else None
        if duplicate is not None and duplicate_id != current_id:
            raise ValueError("A video with this YouTube video ID already exists.")

    video = existing_video or model_cls()
    apply_health_education_video_attributes(video, attrs)
    session.add(video)
    session.commit()
    return video


def filter_health_education_videos(videos, *, topic=None, keyword=None, language=None, is_active=None):
    topic = (topic or "").strip().lower()
    keyword = (keyword or "").strip().lower()
    language = (language or "").strip().lower()

    if is_active in {"true", "1", "yes", "active"}:
        active_filter = True
    elif is_active in {"false", "0", "no", "inactive"}:
        active_filter = False
    else:
        active_filter = None

    def _matches(video):
        if active_filter is not None and bool(getattr(video, "is_active", False)) is not active_filter:
            return False

        video_language = (getattr(video, "language", "") or "").strip().lower()
        if language and language != video_language:
            return False

        topics = [str(item).strip().lower() for item in (getattr(video, "health_topics", None) or [])]
        keywords = [str(item).strip().lower() for item in (getattr(video, "keywords", None) or [])]

        if topic and topic not in topics:
            return False

        if keyword and keyword not in keywords:
            return False

        return True

    return [video for video in videos if _matches(video)]
