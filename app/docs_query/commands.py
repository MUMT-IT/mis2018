import click
from flask import current_app
from flask.cli import with_appcontext

from app.main import db

from .models import DocsQueryDocument
from .views import list_pdf_files, process_document


def register_commands(app):
    @app.cli.group('docs-query')
    def docs_query_cli():
        """Commands for the Docs Query application."""

    @docs_query_cli.command('backfill')
    @click.option('--limit', type=click.IntRange(min=0), default=0, show_default=True,
                  help='Maximum number of documents to process; 0 means all.')
    @click.option('--retry-failed', is_flag=True,
                  help='Retry documents whose previous processing attempt failed.')
    @click.option('--file-id', 'file_ids', multiple=True,
                  help='Process only the specified Google Drive file ID; repeatable.')
    @click.option('--dry-run', is_flag=True,
                  help='Show which documents would be processed without changing the database.')
    @with_appcontext
    def backfill(limit, retry_failed, file_ids, dry_run):
        """Process new or unprocessed PDFs from the configured Drive folder."""
        pdf_files = list_pdf_files()
        requested_ids = set(file_ids)
        if requested_ids:
            pdf_files = [pdf for pdf in pdf_files if pdf.get('id') in requested_ids]

        candidates = []
        skipped = 0
        for pdf in pdf_files:
            file_id = pdf.get('id')
            document = DocsQueryDocument.query.filter_by(drive_file_id=file_id).first()
            if document and document.status == 'processed':
                skipped += 1
                continue
            if document and document.status == 'failed' and not retry_failed:
                skipped += 1
                continue
            candidates.append(pdf)

        if limit:
            candidates = candidates[:limit]

        if dry_run:
            click.echo('Documents selected: {}'.format(len(candidates)))
            for pdf in candidates:
                click.echo('- {} ({})'.format(pdf.get('name') or pdf.get('id'), pdf.get('id')))
            click.echo('Documents skipped: {}'.format(skipped))
            return

        click.echo('Documents selected: {}'.format(len(candidates)))
        processed_count = 0
        failed = []
        for index, pdf in enumerate(candidates, start=1):
            file_id = pdf.get('id')
            title = pdf.get('name') or file_id
            click.echo('[{}/{}] Processing {}'.format(index, len(candidates), title))
            try:
                result = process_document(file_id)
                processed_count += 1
                click.echo(
                    '  Processed: {} chunks, {} characters'.format(
                        result['total_chunk_count'],
                        result['extracted_char_count'],
                    )
                )
            except Exception as exc:
                db.session.rollback()
                failed.append((file_id, title, str(exc)))
                current_app.logger.exception('Docs Query backfill failed for %s', file_id)
                click.echo('  Failed: {}'.format(exc), err=True)

        click.echo('Completed: {} processed, {} failed, {} skipped'.format(
            processed_count,
            len(failed),
            skipped,
        ))
        if failed:
            raise click.ClickException('{} document(s) failed during backfill.'.format(len(failed)))
