"""Check the most recently added Docs Query document.

Usage:
    python scripts/check_latest_docs_query.py
    python scripts/check_latest_docs_query.py --json

The script uses the application's configured database and only reads data.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError

# Make direct execution from the repository root work without requiring
# callers to set PYTHONPATH explicitly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app.docs_query.models import DocsQueryDocument


def get_latest_document() -> Optional[DocsQueryDocument]:
    """Return the newest Docs Query document, or ``None`` when none exists."""
    return (
        DocsQueryDocument.query
        .order_by(
            DocsQueryDocument.created_at.desc(),
            DocsQueryDocument.id.desc(),
        )
        .first()
    )


def document_details(document: DocsQueryDocument) -> Dict[str, Any]:
    """Convert a document record into stable, CLI-friendly fields."""
    return {
        "id": document.id,
        "drive_file_id": document.drive_file_id,
        "title": document.document_title,
        "filename": document.filename,
        "status": document.status,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "extracted_at": document.extracted_at.isoformat() if document.extracted_at else None,
        "extracted_char_count": document.extracted_char_count,
        "total_chunks": document.total_chunks,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "error_message": document.error_message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show the most recently added Docs Query document."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the document details as JSON.",
    )
    args = parser.parse_args()

    with app.app_context():
        try:
            document = get_latest_document()
        except SQLAlchemyError as exc:
            error = str(exc).splitlines()[0]
            print("Could not read Docs Query documents: {}".format(error), file=sys.stderr)
            return 2

        if document is None:
            message = "No Docs Query documents found."
            if args.json:
                print(json.dumps({"document": None}, ensure_ascii=False))
            else:
                print(message)
            return 1

        details = document_details(document)
        if args.json:
            print(json.dumps(details, ensure_ascii=False, indent=2))
        else:
            print("Latest Docs Query document")
            print("  Title: {}".format(details["title"] or "(untitled)"))
            print("  Filename: {}".format(details["filename"] or "(none)"))
            print("  Drive file ID: {}".format(details["drive_file_id"]))
            print("  Status: {}".format(details["status"]))
            print("  Added: {}".format(details["created_at"]))
            print("  Extracted: {}".format(details["extracted_at"] or "not yet"))
            print("  Chunks: {}".format(details["total_chunks"] or 0))
            print("  Characters: {}".format(details["extracted_char_count"] or 0))
            if details["error_message"]:
                print("  Error: {}".format(details["error_message"]))

        return 0


if __name__ == "__main__":
    sys.exit(main())
