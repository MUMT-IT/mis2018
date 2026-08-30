from app.main import db
from app.staff.models import StaffAccount


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


class DynamicFormAnswer(db.Model):
    __tablename__ = 'dynamic_form_answers'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.ForeignKey('dynamic_form_submissions.id'), nullable=False)
    field_id = db.Column(db.ForeignKey('dynamic_form_fields.id'), nullable=False)
    value = db.Column(db.JSON)
    field = db.relationship(DynamicFormField)


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
