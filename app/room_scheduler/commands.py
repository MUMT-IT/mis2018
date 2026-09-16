import click
from flask.cli import with_appcontext
from psycopg2.extras import DateTimeRange
from sqlalchemy import func

from app.main import db

from .models import RoomEvent, RoomResource, room_conjoined_assoc, room_event_room_assoc


def _range_bounds(value):
    return getattr(value, '_bounds', None) or getattr(value, 'bounds', None)


def register_commands(app):
    @app.cli.group('room-scheduler')
    def room_scheduler_cli():
        """Maintain room-scheduler data."""

    @room_scheduler_cli.command('link-conjoined-rooms')
    @click.argument('first_room_id', type=click.IntRange(min=1))
    @click.argument('second_room_id', type=click.IntRange(min=1))
    @with_appcontext
    def link_conjoined_rooms(first_room_id, second_room_id):
        """Mark two rooms as a valid conjoined-room pair."""
        if first_room_id == second_room_id:
            raise click.UsageError('A room cannot be conjoined with itself.')
        first_id, second_id = sorted((first_room_id, second_room_id))
        rooms = RoomResource.query.filter(RoomResource.id.in_([first_id, second_id])).all()
        if len(rooms) != 2:
            found = {room.id for room in rooms}
            missing = [str(room_id) for room_id in (first_id, second_id) if room_id not in found]
            raise click.ClickException('Room(s) not found: {}'.format(', '.join(missing)))
        exists = db.session.query(room_conjoined_assoc.c.room_id).filter(
            room_conjoined_assoc.c.room_id == first_id,
            room_conjoined_assoc.c.conjoined_room_id == second_id,
        ).first()
        if exists:
            click.echo('Rooms are already linked.')
            return
        db.session.execute(room_conjoined_assoc.insert().values(
            room_id=first_id, conjoined_room_id=second_id
        ))
        db.session.commit()
        click.echo('Linked rooms {} and {}.'.format(first_id, second_id))

    @room_scheduler_cli.command('unlink-conjoined-rooms')
    @click.argument('first_room_id', type=click.IntRange(min=1))
    @click.argument('second_room_id', type=click.IntRange(min=1))
    @click.option('--apply', 'apply_changes', is_flag=True,
                  help='Remove the relationship. Without this flag the command is a dry run.')
    @with_appcontext
    def unlink_conjoined_rooms(first_room_id, second_room_id, apply_changes):
        """Remove a conjoined-room pair without altering reservations."""
        first_id, second_id = sorted((first_room_id, second_room_id))
        statement = room_conjoined_assoc.delete().where(
            room_conjoined_assoc.c.room_id == first_id,
            room_conjoined_assoc.c.conjoined_room_id == second_id,
        )
        if not apply_changes:
            exists = db.session.query(room_conjoined_assoc.c.room_id).filter(
                room_conjoined_assoc.c.room_id == first_id,
                room_conjoined_assoc.c.conjoined_room_id == second_id,
            ).first()
            click.echo('DRY RUN: relationship {}'.format('would be removed' if exists else 'does not exist'))
            return
        result = db.session.execute(statement)
        db.session.commit()
        click.echo('Removed {} relationship(s).'.format(result.rowcount))

    @room_scheduler_cli.command('backfill-event-rooms')
    @click.option('--apply', 'apply_changes', is_flag=True,
                  help='Write changes. Without this flag the command is a dry run.')
    @click.option('--batch-size', type=click.IntRange(min=1), default=500, show_default=True)
    @click.option('--after-id', type=click.IntRange(min=0), default=0, show_default=True)
    @click.option('--limit', type=click.IntRange(min=0), default=0, show_default=True,
                  help='Maximum events to inspect; 0 means all.')
    @with_appcontext
    def backfill_event_rooms(apply_changes, batch_size, after_id, limit):
        """Add each legacy event's primary room to its room association."""
        inspected = added = already_present = 0
        cursor = after_id
        while not limit or inspected < limit:
            current_batch_size = min(batch_size, limit - inspected) if limit else batch_size
            events = (
                RoomEvent.query
                .filter(RoomEvent.id > cursor, RoomEvent.room_id.isnot(None))
                .order_by(RoomEvent.id)
                .limit(current_batch_size)
                .all()
            )
            if not events:
                break
            for event in events:
                inspected += 1
                cursor = event.id
                if any(room.id == event.room_id for room in event.rooms):
                    already_present += 1
                    continue
                added += 1
                if apply_changes:
                    event.rooms.append(event.room)
            if apply_changes:
                db.session.commit()
            else:
                db.session.expire_all()
        if not apply_changes:
            db.session.rollback()
        click.echo(
            '{}: inspected={}, would_add={}, already_present={}'.format(
                'APPLIED' if apply_changes else 'DRY RUN', inspected, added, already_present
            )
        )

    @room_scheduler_cli.command('normalize-range-boundaries')
    @click.option('--apply', 'apply_changes', is_flag=True,
                  help='Write changes. Without this flag the command is a dry run.')
    @click.option('--batch-size', type=click.IntRange(min=1), default=500, show_default=True)
    @click.option('--after-id', type=click.IntRange(min=0), default=0, show_default=True)
    @click.option('--limit', type=click.IntRange(min=0), default=0, show_default=True,
                  help='Maximum events to inspect; 0 means all.')
    @click.option('--future-only', is_flag=True,
                  help='Only normalize reservations that have not ended.')
    @with_appcontext
    def normalize_range_boundaries(apply_changes, batch_size, after_id, limit, future_only):
        """Normalize reservation ranges to inclusive-start/exclusive-end [)."""
        inspected = changed = invalid = 0
        cursor = after_id
        while not limit or inspected < limit:
            current_batch_size = min(batch_size, limit - inspected) if limit else batch_size
            query = RoomEvent.query.filter(RoomEvent.id > cursor, RoomEvent.datetime.isnot(None))
            if future_only:
                query = query.filter(RoomEvent.end >= func.now())
            events = query.order_by(RoomEvent.id).limit(current_batch_size).all()
            if not events:
                break
            for event in events:
                inspected += 1
                cursor = event.id
                value = event.datetime
                if value.lower is None or value.upper is None or value.lower >= value.upper:
                    invalid += 1
                    continue
                if _range_bounds(value) == '[)':
                    continue
                changed += 1
                if apply_changes:
                    event.datetime = DateTimeRange(value.lower, value.upper, bounds='[)')
            if apply_changes:
                db.session.commit()
            else:
                db.session.expire_all()
        if not apply_changes:
            db.session.rollback()
        click.echo(
            '{}: inspected={}, would_normalize={}, invalid={}'.format(
                'APPLIED' if apply_changes else 'DRY RUN', inspected, changed, invalid
            )
        )
        if invalid:
            raise click.ClickException('{} invalid range(s) require manual review.'.format(invalid))

    @room_scheduler_cli.command('verify-data')
    @with_appcontext
    def verify_data():
        """Verify room associations and reservation range boundaries."""
        legacy_total = RoomEvent.query.filter(RoomEvent.room_id.isnot(None)).count()
        missing_primary = (
            db.session.query(RoomEvent.id)
            .outerjoin(
                room_event_room_assoc,
                (room_event_room_assoc.c.event_id == RoomEvent.id)
                & (room_event_room_assoc.c.room_id == RoomEvent.room_id),
            )
            .filter(RoomEvent.room_id.isnot(None), room_event_room_assoc.c.event_id.is_(None))
            .count()
        )
        empty_room_sets = (
            db.session.query(RoomEvent.id)
            .outerjoin(room_event_room_assoc, room_event_room_assoc.c.event_id == RoomEvent.id)
            .filter(room_event_room_assoc.c.event_id.is_(None))
            .count()
        )
        invalid_ranges = RoomEvent.query.filter(
            RoomEvent.datetime.isnot(None), RoomEvent.start >= RoomEvent.end
        ).count()
        non_half_open = sum(
            1 for (value,) in db.session.query(RoomEvent.datetime).filter(RoomEvent.datetime.isnot(None))
            if _range_bounds(value) != '[)'
        )

        click.echo('events_with_primary_room={}'.format(legacy_total))
        click.echo('missing_primary_room_association={}'.format(missing_primary))
        click.echo('events_with_no_room_association={}'.format(empty_room_sets))
        click.echo('non_half_open_ranges={}'.format(non_half_open))
        click.echo('invalid_ranges={}'.format(invalid_ranges))
        if missing_primary or empty_room_sets or non_half_open or invalid_ranges:
            raise click.ClickException('Room scheduler data verification failed.')
        click.echo('Room scheduler data verification passed.')
