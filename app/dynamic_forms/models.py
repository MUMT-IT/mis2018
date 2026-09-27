from app.main import db
from app.staff.models import StaffAccount
from .scoring import raw_score, weighted_score


class DynamicForm(db.Model):
    __tablename__ = 'dynamic_forms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text())
    status = db.Column(db.String(32), nullable=False, default='Draft')
    created_by_id = db.Column(db.ForeignKey('staff_account.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    created_by = db.relationship(StaffAccount, foreign_keys=[created_by_id])
    versions = db.relationship('DynamicFormVersion', backref='form', cascade='all, delete-orphan', order_by='DynamicFormVersion.version')


class DynamicFormVersion(db.Model):
    __tablename__ = 'dynamic_form_versions'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.ForeignKey('dynamic_forms.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='Draft')
    created_by_id = db.Column(db.ForeignKey('staff_account.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    published_at = db.Column(db.DateTime(timezone=True))
    passing_percentage = db.Column(db.Numeric(5, 2))
    created_by = db.relationship(StaffAccount, foreign_keys=[created_by_id])
    fields = db.relationship('DynamicFormField', backref='version', cascade='all, delete-orphan', order_by='DynamicFormField.display_order')


class DynamicFormField(db.Model):
    __tablename__ = 'dynamic_form_fields'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.ForeignKey('dynamic_form_versions.id'), nullable=False)
    key = db.Column(db.String(128), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    field_type = db.Column(db.String(32), nullable=False)
    required = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=1)
    help_text = db.Column(db.Text())
    config = db.Column(db.JSON)
    options = db.relationship('DynamicFormOption', backref='field', cascade='all, delete-orphan', order_by='DynamicFormOption.display_order')


class DynamicFormOption(db.Model):
    __tablename__ = 'dynamic_form_options'
    id = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.ForeignKey('dynamic_form_fields.id'), nullable=False)
    value = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=1)


class DynamicFormSubmission(db.Model):
    __tablename__ = 'dynamic_form_submissions'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.ForeignKey('dynamic_form_versions.id'), nullable=False)
    respondent_type = db.Column(db.String(128), nullable=False)
    respondent_id = db.Column(db.Integer, nullable=False)
    subject_type = db.Column(db.String(128), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='Draft')
    submitted_at = db.Column(db.DateTime(timezone=True))
    version = db.relationship(DynamicFormVersion, backref=db.backref('submissions', cascade='all, delete-orphan'))
    answers = db.relationship('DynamicFormAnswer', backref='submission', cascade='all, delete-orphan')

    @property
    def weighted_score(self):
        return sum(score for score in (
            answer.weighted_score for answer in self.answers
        ) if score is not None)

    @property
    def maximum_weighted_score(self):
        maximum = 0
        for answer in self.answers:
            config = answer.field.config or {}
            if config.get('scorable'):
                maximum += (float(config.get('max_score') or 0) *
                            float(config.get('weight') or 0))
        return maximum

    @property
    def maximum_score(self):
        """Total configured raw maximum, without applying field weights."""
        return sum(float((answer.field.config or {}).get('max_score') or 0)
                   for answer in self.answers
                   if (answer.field.config or {}).get('scorable'))

    @property
    def score_percentage(self):
        if not self.maximum_score:
            return None
        return self.weighted_score / self.maximum_score * 100

    @property
    def passed(self):
        if self.score_percentage is None or self.version.passing_percentage is None:
            return None
        return self.score_percentage >= float(self.version.passing_percentage)


class DynamicFormAnswer(db.Model):
    __tablename__ = 'dynamic_form_answers'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.ForeignKey('dynamic_form_submissions.id'), nullable=False)
    field_id = db.Column(db.ForeignKey('dynamic_form_fields.id'), nullable=False)
    value = db.Column(db.JSON)
    field = db.relationship(DynamicFormField)

    @property
    def raw_score(self):
        return raw_score(self.value)

    @property
    def weighted_score(self):
        return weighted_score(self.value, self.field.config)

    @property
    def maximum_weighted_score(self):
        config = self.field.config or {}
        if not config.get('scorable'):
            return None
        return (float(config.get('max_score') or 0) *
                float(config.get('weight') or 0))

    @property
    def maximum_score(self):
        config = self.field.config or {}
        if not config.get('scorable'):
            return None
        return float(config.get('max_score') or 0)


class DynamicFormAssignment(db.Model):
    __tablename__ = 'dynamic_form_assignments'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.ForeignKey('dynamic_form_versions.id'), nullable=False)
    subject_type = db.Column(db.String(128), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)
    assigned_by_id = db.Column(db.ForeignKey('staff_account.id'), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    version = db.relationship(DynamicFormVersion, backref=db.backref('assignments', cascade='all, delete-orphan'))
    assigned_by = db.relationship(StaffAccount, foreign_keys=[assigned_by_id])
