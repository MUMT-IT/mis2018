from datetime import datetime, timezone

from app.main import db
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


class DocsQueryDocument(db.Model):
    __tablename__ = 'docs_query_documents'

    id = db.Column(db.Integer, primary_key=True)
    drive_file_id = db.Column(db.String(255), nullable=False, unique=True)
    document_title = db.Column(db.String(512))
    filename = db.Column(db.String(512))
    document_type = db.Column(db.String(255))
    tags = db.Column(db.JSON, nullable=False, default=list)
    note = db.Column(db.Text)
    is_expired = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(32), nullable=False, default='pending', index=True)
    extracted_text_key = db.Column(db.String(1024))
    chunks_key = db.Column(db.String(1024))
    artifact_key = db.Column(db.String(1024))
    extracted_at = db.Column(db.DateTime(timezone=True))
    extracted_char_count = db.Column(db.Integer)
    total_chunks = db.Column(db.Integer)
    chunking_method = db.Column(db.String(64))
    error_message = db.Column(db.Text)
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
