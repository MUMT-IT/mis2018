#!/usr/bin/env python3
"""Backfill procurement image assets to S3.

This script processes:
1) rows where image_url is NULL/empty and legacy image text exists:
   uploads full image + thumbnail, then updates both fields.
2) rows where image_url exists but image_thumbnail_url is NULL/empty:
   uploads only thumbnail from existing full image, then updates image_thumbnail_url.
"""

import argparse
import base64
import csv
import hashlib
import imghdr
import io
import re
import sys
from datetime import datetime

from sqlalchemy import text
from PIL import Image

from app.main import app, db, s3, S3_BUCKET_NAME


DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>.+)$", re.DOTALL)

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload procurement full images/thumbnails to S3 and backfill URL fields."
    )
    parser.add_argument(
        "--prefix",
        default="procurements/thumbnails",
        help="S3 key prefix where both full image and thumbnail will be uploaded",
    )
    parser.add_argument("--start-id", type=int, default=0, help="Only process id >= start-id")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 means all)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip upload if target key already exists")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload/update DB")
    parser.add_argument("--progress-every", type=int, default=100, help="Print progress every N processed rows")
    parser.add_argument(
        "--report-csv",
        default=f"/tmp/procurement_image_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        help="Write per-record report CSV",
    )
    return parser.parse_args()


def decode_image_text(raw_text):
    if not raw_text:
        return None, None
    raw_text = raw_text.strip()

    m = DATA_URL_RE.match(raw_text)
    if m:
        mime = m.group("mime").lower()
        b64_data = m.group("data")
        return base64.b64decode(b64_data), mime

    try:
        return base64.b64decode(raw_text), None
    except Exception:
        return None, None


def detect_extension(data, mime=None):
    if mime and mime in MIME_TO_EXT:
        return MIME_TO_EXT[mime]
    detected = imghdr.what(None, h=data)
    if detected == "jpeg":
        return "jpg"
    return detected or "bin"


def sha256_digest(data):
    return hashlib.sha256(data).hexdigest()


def s3_key(prefix, row_id, erp_code, ext):
    safe_code = (erp_code or f"id-{row_id}").replace("/", "-").strip()
    return f"{prefix.rstrip('/')}/{safe_code}.{ext}"


def thumbnail_s3_key(prefix, row_id, erp_code, ext):
    safe_code = (erp_code or f"id-{row_id}").replace("/", "-").strip()
    return f"{prefix.rstrip('/')}/{safe_code}_thumbnail.{ext}"


def object_exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def is_thumbnail_only_path(key):
    if not key:
        return False
    return "thumbnails/" in key.lower()


def ensure_s3_prefix(bucket, prefix):
    marker_key = f"{prefix.rstrip('/')}/"
    if object_exists(bucket, marker_key):
        return
    s3.put_object(Bucket=bucket, Key=marker_key, Body=b"")


def create_thumbnail_bytes(image_bytes, ext, size=(256, 256)):
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    image.thumbnail(size)
    out = io.BytesIO()
    format_map = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "gif": "GIF",
        "webp": "WEBP",
        "bmp": "BMP",
    }
    output_format = format_map.get(ext.lower(), "PNG")
    save_kwargs = {}
    if output_format == "JPEG":
        save_kwargs["quality"] = 85
        save_kwargs["optimize"] = True
    image.save(out, format=output_format, **save_kwargs)
    return out.getvalue(), output_format


def main():
    args = parse_args()
    if not S3_BUCKET_NAME:
        print("Missing S3 bucket config (BUCKETEER_BUCKET_NAME).", file=sys.stderr)
        return 2

    processed = 0
    uploaded = 0
    updated = 0
    skipped = 0
    failed = 0
    repaired_thumbnail_only = 0
    min_processed_id = None
    max_processed_id = None

    where_clause = """
        id >= :start_id
          AND (
                (
                    (image_url IS NULL OR image_url = '')
                    AND image IS NOT NULL
                    AND image <> ''
                )
                OR (
                    image_url IS NOT NULL
                    AND image_url <> ''
                    AND (image_thumbnail_url IS NULL OR image_thumbnail_url = '')
                )
          )
    """

    sql = f"""
        SELECT id, erp_code, image, image_url
        FROM procurement_details
        WHERE {where_clause}
        ORDER BY id ASC
    """
    count_sql = f"""
        SELECT COUNT(*)
        FROM procurement_details
        WHERE {where_clause}
    """
    if args.limit > 0:
        sql += " LIMIT :limit_n"

    with app.app_context():
        if not args.dry_run:
            ensure_s3_prefix(S3_BUCKET_NAME, args.prefix)

        params = {"start_id": args.start_id}
        if args.limit > 0:
            params["limit_n"] = args.limit
        total_match = db.session.execute(text(count_sql), {"start_id": args.start_id}).scalar()
        print(f"Matched rows (before limit): {total_match}", flush=True)
        if args.limit > 0:
            print(f"Run limit: {args.limit}", flush=True)

        # Avoid server-side named cursor here because we commit inside the loop.
        # Server-side cursor becomes invalid after commit on PostgreSQL.
        result = db.session.execute(text(sql), params).mappings().all()

        with open(args.report_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "erp_code",
                    "full_s3_key",
                    "thumbnail_s3_key",
                    "sha256",
                    "action",
                    "status",
                    "error",
                ],
            )
            writer.writeheader()

            for row in result:
                processed += 1
                row_id = int(row["id"])
                if min_processed_id is None or row_id < min_processed_id:
                    min_processed_id = row_id
                if max_processed_id is None or row_id > max_processed_id:
                    max_processed_id = row_id
                action = "process"
                status = "ok"
                error = ""
                full_key = ""
                thumb_key = ""
                digest = ""
                try:
                    raw_image_url = (row["image_url"] or "").strip()
                    has_full_image_url = bool(raw_image_url) and not is_thumbnail_only_path(raw_image_url)
                    thumbnail_only_in_image_url = bool(raw_image_url) and is_thumbnail_only_path(raw_image_url)
                    image_bytes = None
                    mime = None

                    if has_full_image_url:
                        # Existing full image is already on S3: only generate/upload thumbnail.
                        full_key = raw_image_url
                        full_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key=full_key)
                        image_bytes = full_obj["Body"].read()
                        mime = full_obj.get("ContentType")
                        ext = detect_extension(image_bytes, mime)
                        thumb_key = thumbnail_s3_key(args.prefix, row["id"], row["erp_code"], ext)
                        action = "upload_thumbnail+update_image_thumbnail_url"
                    else:
                        # Legacy DB image or thumbnail-only image_url: upload full image and thumbnail.
                        image_bytes, mime = decode_image_text(row["image"])
                        if not image_bytes:
                            raise RuntimeError("Cannot decode image text (not base64/data URL)")
                        ext = detect_extension(image_bytes, mime)
                        full_key = s3_key(args.prefix, row["id"], row["erp_code"], ext)
                        thumb_key = thumbnail_s3_key(args.prefix, row["id"], row["erp_code"], ext)
                        action = "upload_full+upload_thumbnail+update_urls"
                        if thumbnail_only_in_image_url:
                            action = "repair_thumbnail_only_image_url"

                    digest = sha256_digest(image_bytes)
                    thumbnail_bytes, thumbnail_format = create_thumbnail_bytes(image_bytes, ext)
                    thumbnail_content_type = f"image/{thumbnail_format.lower()}"

                    if args.skip_existing and (
                        (has_full_image_url and object_exists(S3_BUCKET_NAME, thumb_key)) or
                        ((not has_full_image_url) and object_exists(S3_BUCKET_NAME, full_key) and object_exists(S3_BUCKET_NAME, thumb_key))
                    ):
                        skipped += 1
                        action = "skip_existing"
                    else:
                        if not has_full_image_url and not args.dry_run and (not args.skip_existing or not object_exists(S3_BUCKET_NAME, full_key)):
                            s3.put_object(
                                Bucket=S3_BUCKET_NAME,
                                Key=full_key,
                                Body=image_bytes,
                                ContentType=mime or "application/octet-stream",
                            )
                            uploaded += 1
                        if not args.dry_run and (not args.skip_existing or not object_exists(S3_BUCKET_NAME, thumb_key)):
                            s3.put_object(
                                Bucket=S3_BUCKET_NAME,
                                Key=thumb_key,
                                Body=thumbnail_bytes,
                                ContentType=thumbnail_content_type,
                            )
                            uploaded += 1

                    if not args.dry_run:
                        if has_full_image_url:
                            db.session.execute(
                                text(
                                    """
                                    UPDATE procurement_details
                                    SET image_thumbnail_url = :image_thumbnail_url
                                    WHERE id = :id
                                    """
                                ),
                                {
                                    "id": row["id"],
                                    "image_thumbnail_url": thumb_key,
                                },
                            )
                        else:
                            db.session.execute(
                                text(
                                    """
                                    UPDATE procurement_details
                                    SET image_url = :image_url,
                                        image_thumbnail_url = :image_thumbnail_url
                                    WHERE id = :id
                                    """
                                ),
                                {
                                    "id": row["id"],
                                    "image_url": full_key,
                                    "image_thumbnail_url": thumb_key,
                                },
                            )
                            if thumbnail_only_in_image_url:
                                repaired_thumbnail_only += 1
                        db.session.commit()
                        updated += 1
                except Exception as exc:
                    db.session.rollback()
                    failed += 1
                    status = "failed"
                    error = str(exc)

                writer.writerow(
                    {
                        "id": row["id"],
                        "erp_code": row["erp_code"],
                        "full_s3_key": full_key,
                        "thumbnail_s3_key": thumb_key,
                        "sha256": digest,
                        "action": action,
                        "status": status,
                        "error": error,
                    }
                )

                if args.progress_every > 0 and processed % args.progress_every == 0:
                    print(
                        f"[progress] processed={processed} uploaded={uploaded} "
                        f"updated={updated} skipped={skipped} failed={failed} "
                        f"last_id={row_id}",
                        flush=True,
                    )

    print(f"Bucket: {S3_BUCKET_NAME}")
    print(f"Processed: {processed}")
    print(f"Uploaded: {uploaded}")
    print(f"Updated image_url: {updated}")
    print(f"Skipped existing: {skipped}")
    print(f"Failed: {failed}")
    print(f"Repaired thumbnail-only image_url rows: {repaired_thumbnail_only}")
    print(f"Min processed ID: {min_processed_id}")
    print(f"Max processed ID: {max_processed_id}")
    if max_processed_id is not None:
        next_start_id = max_processed_id + 1
        print(f"Suggested next start-id: {next_start_id}")
        print(f"Next command example: python scripts/migrate_procurement_images_to_s3.py --skip-existing --start-id {next_start_id}")
    print(f"Report: {args.report_csv}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
