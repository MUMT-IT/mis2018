import click
from flask import current_app
from flask.cli import with_appcontext

from app.main import db

from .models import DocsQueryDocument, DocsQueryFaq
from .views import (
    embed_faqs,
    extract_date_for_document,
    generate_document_summary,
    list_pdf_files,
    process_document,
)


def register_commands(app):
    @app.cli.group('docs-query')
    def docs_query_cli():
        """Commands for the Docs Query application."""

    @docs_query_cli.command('backfill-faq-embeddings')
    @with_appcontext
    def backfill_faq_embeddings():
        """Generate missing semantic-search embeddings for FAQ questions."""
        faqs = DocsQueryFaq.query.filter(DocsQueryFaq.embedding.is_(None)).all()
        if not faqs:
            click.echo('No FAQ embeddings need backfilling.')
            return
        try:
            count = embed_faqs(faqs)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            raise click.ClickException('FAQ embedding backfill failed: {}'.format(exc))
        click.echo('Generated embeddings for {} FAQ(s).'.format(count))

    @docs_query_cli.command('backfill')
    @click.option('--limit', type=click.IntRange(min=0), default=0, show_default=True,
                  help='Maximum number of documents to process; 0 means all.')
    @click.option('--retry-failed', is_flag=True,
                  help='Retry documents whose previous processing attempt failed.')
    @click.option('--file-id', 'file_ids', multiple=True,
                  help='Process only the specified Google Drive file ID; repeatable.')
    @click.option('--dry-run', is_flag=True,
                  help='Show which documents would be processed without changing the database.')
    @click.option('--date-only', is_flag=True,
                  help='Extract issue dates from existing text without rebuilding chunks or embeddings.')
    @click.option('--summary-only', is_flag=True,
                  help='Generate summaries for processed documents without rebuilding extraction or embeddings.')
    @with_appcontext
    def backfill(limit, retry_failed, file_ids, dry_run, date_only, summary_only):
        """Process new or unprocessed PDFs from the configured Drive folder."""
        if date_only and summary_only:
            raise click.UsageError('Use either --date-only or --summary-only, not both.')

        if summary_only:
            requested_ids = set(file_ids)
            documents = DocsQueryDocument.query.filter_by(status='processed').all()
            if requested_ids:
                documents = [
                    document for document in documents
                    if document.drive_file_id in requested_ids
                ]
            candidates = [
                {
                    'id': document.drive_file_id,
                    'name': document.document_title or document.filename or document.drive_file_id,
                }
                for document in documents
                if not document.summary or document.summary_error
            ]
            skipped = len(documents) - len(candidates)
            if limit:
                candidates = candidates[:limit]
            if dry_run:
                click.echo('Documents selected: {}'.format(len(candidates)))
                for pdf in candidates:
                    click.echo('- {} ({})'.format(pdf.get('name'), pdf.get('id')))
                click.echo('Documents skipped: {}'.format(skipped))
                return
        else:
            pdf_files = list_pdf_files()
            requested_ids = set(file_ids)
            if requested_ids:
                pdf_files = [pdf for pdf in pdf_files if pdf.get('id') in requested_ids]

            candidates = []
            skipped = 0
            for pdf in pdf_files:
                file_id = pdf.get('id')
                document = DocsQueryDocument.query.filter_by(drive_file_id=file_id).first()
                if date_only:
                    if not document or document.status != 'processed':
                        skipped += 1
                        continue
                    if document.issue_date is not None and document.date_extraction_method != 'not_found':
                        skipped += 1
                        continue
                    candidates.append(pdf)
                    continue
                if document and document.status == 'processed':
                    skipped += 1
                    continue
                if document and document.status == 'failed' and not retry_failed:
                    skipped += 1
                    continue
                candidates.append(pdf)

            if limit:
                candidates = candidates[:limit]

        if summary_only:
            action = 'Generating summaries for'
        elif date_only:
            action = 'Extracting dates from'
        else:
            action = 'Processing'

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
            click.echo('[{}/{}] {} {}'.format(index, len(candidates), action, title))
            try:
                if summary_only:
                    result = {'summary': generate_document_summary(file_id)}
                elif date_only:
                    result = extract_date_for_document(file_id)
                else:
                    result = process_document(file_id)
                processed_count += 1
                if summary_only:
                    click.echo('  Summary generated')
                elif date_only:
                    click.echo('  Issue date: {}'.format(result['issue_date'] or 'not found'))
                else:
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
