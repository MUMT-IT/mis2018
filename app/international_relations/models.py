"""Database models owned by the International Relations module."""

from datetime import datetime

from flask_login import UserMixin

from app.main import db


class InternalRelationParticipant(UserMixin, db.Model):
    """A non-staff participant authenticated by an external Google account."""

    __tablename__ = 'ir_participants'

    id = db.Column(db.Integer, primary_key=True)
    google_subject = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    profile_image_url = db.Column(db.Text, nullable=True)
    preferred_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    nationality = db.Column(db.String(100), nullable=True)
    home_institution = db.Column(db.String(255), nullable=True)
    department = db.Column(db.String(255), nullable=True)
    research_topic = db.Column(db.Text, nullable=True)
    emergency_contact_name = db.Column(db.String(200), nullable=True)
    emergency_contact_phone = db.Column(db.String(50), nullable=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    last_login_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self):
        return self.is_active_account

    @property
    def full_name(self):
        return ' '.join(
            part.strip() for part in (self.first_name, self.last_name)
            if part and part.strip()
        ) or self.email

    # The host's shared navigation was originally written for StaffAccount and
    # reads these attributes for every authenticated identity. Participants are
    # intentionally not staff, so expose neutral compatibility values instead
    # of constructing a fake staff-personal-info relationship.
    @property
    def personal_info(self):
        return None

    @property
    def roles(self):
        return ()

    @property
    def fullname(self):
        return self.full_name

    @property
    def en_fullname(self):
        return self.full_name

    @property
    def line_id(self):
        return None

    @property
    def display_name(self):
        return self.preferred_name or self.full_name

    @property
    def profile_fields(self):
        return {
            'phone': self.phone,
            'nationality': self.nationality,
            'home_institution': self.home_institution,
            'department': self.department,
            'research_topic': self.research_topic,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
        }

    @property
    def profile_completion(self):
        completed = sum(bool(value and str(value).strip()) for value in self.profile_fields.values())
        total = len(self.profile_fields)
        return round((completed / total) * 100) if total else 100

    @property
    def missing_profile_fields(self):
        labels = {
            'phone': 'Phone number',
            'nationality': 'Nationality',
            'home_institution': 'Home institution',
            'department': 'Department',
            'research_topic': 'Research topic',
            'emergency_contact_name': 'Emergency contact name',
            'emergency_contact_phone': 'Emergency contact phone',
        }
        return [labels[name] for name, value in self.profile_fields.items() if not value]

    def update_from_google_profile(self, profile):
        """Refresh non-authoritative display fields on every Google login."""
        self.email = (profile.get('email') or self.email).strip().lower()
        self.first_name = (profile.get('given_name') or self.first_name or '').strip() or None
        self.last_name = (profile.get('family_name') or self.last_name or '').strip() or None
        self.profile_image_url = profile.get('picture') or self.profile_image_url
        self.last_login_at = datetime.utcnow()

    def __str__(self):
        return self.full_name
