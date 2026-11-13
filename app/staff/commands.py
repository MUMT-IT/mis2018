import click
import pytz
from datetime import datetime, timedelta
from flask.cli import with_appcontext

from app.main import db
from .views import refresh_daily_attendance


def register_commands(app):
    @app.cli.group('staff')
    def staff_cli():
        """Commands for staff administration."""

    @staff_cli.command('reconcile-daily-attendance')
    @click.option('--date', 'target_date', type=click.DateTime(formats=['%Y-%m-%d']))
    @click.option('--days', type=click.IntRange(min=1, max=31), default=14, show_default=True,
                  help='Number of dates to rebuild, counting backward from the target date.')
    @with_appcontext
    def reconcile_daily_attendance(target_date, days):
        """Rebuild daily attendance snapshots without an HTTP request timeout."""
        bangkok = pytz.timezone('Asia/Bangkok')
        target_date = (target_date.date() if target_date else
                       datetime.now(bangkok).date() - timedelta(days=1))
        failed = []

        for offset in range(days):
            attendance_date = target_date - timedelta(days=offset)
            try:
                summary = refresh_daily_attendance(attendance_date)
                db.session.commit()
                click.echo(
                    '{}: {} processed, {} absent'.format(
                        summary['date'],
                        summary['processed_count'],
                        summary['absent_count'],
                    )
                )
            except Exception as exc:
                db.session.rollback()
                failed.append((attendance_date.isoformat(), str(exc)))
                click.echo('{}: failed: {}'.format(attendance_date.isoformat(), exc), err=True)

        if failed:
            raise click.ClickException('{} date(s) failed during reconciliation.'.format(len(failed)))

    @app.cli.group('staff-reminders')
    def staff_reminders_cli():
        """Personal check-in reminder maintenance."""

    @staff_reminders_cli.command('refresh-times')
    @click.option('--date', 'as_of', type=click.DateTime(formats=['%Y-%m-%d']),
                  help='Calculation date in Bangkok; only earlier records are used.')
    @click.option('--dry-run', is_flag=True, help='Preview without saving or sending messages.')
    @with_appcontext
    def refresh_times(as_of, dry_run):
        from .reminder_times import refresh_reminder_times
        try:
            summaries = refresh_reminder_times(as_of.date() if as_of else None, dry_run=dry_run)
        except Exception:
            db.session.rollback()
            raise
        for summary in summaries:
            click.echo('staff_id={staff_id} days={sample_days} average={average_checkin_time} reminder={reminder_time}'.format(**summary))
        click.echo('{} {} preferences; no messages sent.'.format(
            'Previewed' if dry_run else 'Updated', len(summaries)))

    @staff_reminders_cli.command('send-due')
    @click.option('--dry-run', is_flag=True, help='Preview recipients without sending or claiming deliveries.')
    @with_appcontext
    def send_due(dry_run):
        """Send due personalized reminders during 08:00–09:00 Bangkok time."""
        from .views import send_personalized_checkin_reminders
        summary = send_personalized_checkin_reminders(dry_run=dry_run)
        for recipient in summary['recipients']:
            click.echo('staff_id={staff_id} time={time}'.format(**recipient))
        click.echo('Due: {recipient_count}; sent: {sent_count}; skipped: {skipped_count}; failed: {failed_count}'.format(**summary))
        if summary['failed_count']:
            raise click.ClickException('Some reminders failed; inspect delivery logs before retrying.')
