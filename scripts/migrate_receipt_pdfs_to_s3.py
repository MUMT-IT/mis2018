#!/usr/bin/env python3
"""Backfill ElectronicReceiptDetail.pdf_file binaries to S3.

Default behavior uploads and verifies only.
Use --clear-db --yes to null out pdf_file after successful upload verification.
"""

import argparse
import csv
import hashlib
import sys
from datetime import datetime

from app.main import app, db, s3, S3_BUCKET_NAME
from app.receipt_printing.models import ElectronicReceiptDetail


def build_s3_key(prefix, receipt):
    number = (receipt.number or f"id-{receipt.id}").strip().replace("/", "-")
    return f"{prefix.rstrip('/')}/{receipt.id}_{number}.pdf"


def build_s3_url(bucket, key):
    return f"s3://{bucket}/{key}"


def sha256_digest(data):
    return hashlib.sha256(data).hexdigest()


def upload_and_verify(bucket, key, data):
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType="application/pdf",
    )
    meta = s3.head_object(Bucket=bucket, Key=key)
    return int(meta["ContentLength"]) == len(data)


def already_exists_with_same_size(bucket, key, data):
    try:
        meta = s3.head_object(Bucket=bucket, Key=key)
    except Exception:
        return False
    return int(meta["ContentLength"]) == len(data)


def parse_args():
    parser = argparse.ArgumentParser(description="Upload receipt PDF binaries from DB to S3.")
    parser.add_argument("--prefix", default="receipt-printing/pdfs", help="S3 key prefix")
    parser.add_argument("--start-id", type=int, default=0, help="Only process receipt id >= start-id")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 means all)")
    parser.add_argument("--batch-size", type=int, default=200, help="DB query batch size")
    parser.add_argument("--skip-existing", action="store_true", help="Skip upload if same-size object already exists")
    parser.add_argument("--clear-db", action="store_true", help="Set pdf_file=NULL after successful upload verification")
    parser.add_argument("--yes", action="store_true", help="Required when --clear-db is used")
    parser.add_argument(
        "--report-csv",
        default=f"/tmp/receipt_pdf_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        help="Write per-record migration report CSV",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.clear_db and not args.yes:
        print("Refusing to clear DB without --yes", file=sys.stderr)
        return 2
    if not S3_BUCKET_NAME:
        print("Missing S3 bucket config (BUCKETEER_BUCKET_NAME).", file=sys.stderr)
        return 2

    processed = 0
    uploaded = 0
    skipped = 0
    cleared = 0
    failed = 0

    with app.app_context():
        query = (
            ElectronicReceiptDetail.query
            .filter(ElectronicReceiptDetail.id >= args.start_id)
            .filter(ElectronicReceiptDetail.pdf_file.isnot(None))
            .order_by(ElectronicReceiptDetail.id.asc())
        )
        if args.limit > 0:
            query = query.limit(args.limit)
        rows = query.yield_per(args.batch_size)

        with open(args.report_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "receipt_id",
                    "receipt_number",
                    "s3_key",
                    "s3_url",
                    "pdf_bytes",
                    "sha256",
                    "action",
                    "status",
                    "error",
                ],
            )
            writer.writeheader()

            for receipt in rows:
                processed += 1
                data = receipt.pdf_file
                key = build_s3_key(args.prefix, receipt)
                digest = sha256_digest(data)
                action = "upload"
                status = "ok"
                error = ""
                try:
                    if args.skip_existing and already_exists_with_same_size(S3_BUCKET_NAME, key, data):
                        skipped += 1
                        action = "skip_existing"
                    else:
                        ok = upload_and_verify(S3_BUCKET_NAME, key, data)
                        if not ok:
                            raise RuntimeError("Uploaded object size mismatch")
                        uploaded += 1

                    receipt.pdf_url = build_s3_url(S3_BUCKET_NAME, key)
                    action = f"{action}+set_pdf_url"

                    if args.clear_db:
                        receipt.pdf_file = None
                        cleared += 1
                        action = f"{action}+clear_db"
                except Exception as exc:
                    status = "failed"
                    failed += 1
                    error = str(exc)
                    db.session.rollback()
                else:
                    db.session.add(receipt)
                    db.session.commit()

                writer.writerow(
                    {
                        "receipt_id": receipt.id,
                        "receipt_number": receipt.number,
                        "s3_key": key,
                        "s3_url": build_s3_url(S3_BUCKET_NAME, key),
                        "pdf_bytes": len(data),
                        "sha256": digest,
                        "action": action,
                        "status": status,
                        "error": error,
                    }
                )

    print(f"Bucket: {S3_BUCKET_NAME}")
    print(f"Processed: {processed}")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped existing: {skipped}")
    print(f"Cleared from DB: {cleared}")
    print(f"Failed: {failed}")
    print("pdf_url updated for all successful rows.")
    print(f"Report: {args.report_csv}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
