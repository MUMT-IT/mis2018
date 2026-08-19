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
