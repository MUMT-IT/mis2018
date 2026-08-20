from datetime import datetime, timezone
from pytz import timezone as pytz_timezone

from app.main import db


BANGKOK_TZ = pytz_timezone('Asia/Bangkok')
from sqlalchemy.types import TypeDecorator, UserDefinedType


class _PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions):
        self.dimensions = dimensions

    def get_col_spec(self, **kwargs):
        return 'vector({})'.format(self.dimensions)


class VectorType(TypeDecorator):
    impl = db.Text
    cache_ok = True

    def __init__(self, dimensions, **kwargs):
        self.dimensions = dimensions
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(_PgVector(self.dimensions))
        return dialect.type_descriptor(db.Text())


docs_query_document_tags = db.Table(
    'docs_query_document_tags',
    db.Column(
        'document_id',
        db.Integer,
        db.ForeignKey('docs_query_documents.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    db.Column(
        'tag_id',
        db.Integer,
        db.ForeignKey('docs_query_tags.id', ondelete='CASCADE'),
        primary_key=True,
    ),
)


class DocsQueryTag(db.Model):
    __tablename__ = 'docs_query_tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    documents = db.relationship(
        'DocsQueryDocument',
        secondary=docs_query_document_tags,
        back_populates='tags',
    )


class DocsQueryDocument(db.Model):
    __tablename__ = 'docs_query_documents'

    id = db.Column(db.Integer, primary_key=True)
    drive_file_id = db.Column(db.String(255), nullable=False, unique=True)
    document_title = db.Column(db.String(512))
    filename = db.Column(db.String(512))
    document_type = db.Column(db.String(255))
    tags = db.relationship(
        DocsQueryTag,
        secondary=docs_query_document_tags,
        back_populates='documents',
        order_by=DocsQueryTag.name,
    )
    note = db.Column(db.Text)
    is_expired = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(32), nullable=False, default='pending', index=True)
    extracted_text_key = db.Column(db.String(1024))
    chunks_key = db.Column(db.String(1024))
    artifact_key = db.Column(db.String(1024))
    extracted_at = db.Column(db.DateTime(timezone=True))
    issue_date = db.Column(db.Date, index=True)
    issue_date_raw = db.Column(db.String(255))
    date_extraction_method = db.Column(db.String(32))
    date_extracted_at = db.Column(db.DateTime(timezone=True))
    extracted_char_count = db.Column(db.Integer)
    total_chunks = db.Column(db.Integer)
    chunking_method = db.Column(db.String(64))
    error_message = db.Column(db.Text)
    summary = db.Column(db.Text)
    summary_generated_at = db.Column(db.DateTime(timezone=True))
    summary_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))


class DocsQueryChunk(db.Model):
    __tablename__ = 'docs_query_chunks'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey('docs_query_documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    chunk_index = db.Column(db.Integer, nullable=False)
    char_count = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    embedding = db.Column(VectorType(1024))

    document = db.relationship(
        DocsQueryDocument,
        backref=db.backref('chunks', cascade='all, delete-orphan', lazy=True),
    )


class DocsQuerySearch(db.Model):
    __tablename__ = 'docs_query_searches'

    id = db.Column(db.Integer, primary_key=True)
    query_text = db.Column(db.String(1000), nullable=False)
    result_count = db.Column(db.Integer, nullable=False, default=0)
    related_document_count = db.Column(db.Integer, nullable=False, default=0)
    search_method = db.Column(db.String(32), nullable=False, default='keyword')
    response_time_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc), index=True)


class DocsQueryFaq(db.Model):
    __tablename__ = 'docs_query_faqs'
    __versioned__ = {'exclude': ['embedding']}

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    embedding = db.Column(VectorType(1024))
    creator_name = db.Column(db.String(255), nullable=False)
    editor_name = db.Column(db.String(255), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=True)
    editor_id = db.Column(db.Integer, db.ForeignKey('staff_account.id'), nullable=True)
    create_datetime = db.Column(db.DateTime(timezone=True), nullable=False,
                                 default=lambda: datetime.now(BANGKOK_TZ))
    edit_datetime = db.Column(db.DateTime(timezone=True), nullable=False,
                               default=lambda: datetime.now(BANGKOK_TZ),
                               onupdate=lambda: datetime.now(BANGKOK_TZ))
    creator = db.relationship('StaffAccount', foreign_keys=[creator_id])
    editor = db.relationship('StaffAccount', foreign_keys=[editor_id])


class DocsQueryClick(db.Model):
    __tablename__ = 'docs_query_clicks'

    id = db.Column(db.Integer, primary_key=True)
    search_id = db.Column(
        db.Integer,
        db.ForeignKey('docs_query_searches.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    document_id = db.Column(
        db.Integer,
        db.ForeignKey('docs_query_documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    clicked_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc), index=True)

    search = db.relationship(
        DocsQuerySearch,
        backref=db.backref('clicks', cascade='all, delete-orphan', lazy=True),
    )
    document = db.relationship(DocsQueryDocument)
