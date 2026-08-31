from datetime import datetime, timezone

from app.main import db


class ShortUrlMapping(db.Model):
    __tablename__ = 'shorturl_mappings'

    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(32), nullable=False, unique=True)
    long_url = db.Column(db.Text, nullable=False)
    click_count = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=db.func.now(),
        index=True,
    )
    staff_account_id = db.Column(
        db.Integer,
        db.ForeignKey('staff_account.id'),
        nullable=False,
        index=True,
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    staff_account = db.relationship('StaffAccount', foreign_keys=[staff_account_id])
