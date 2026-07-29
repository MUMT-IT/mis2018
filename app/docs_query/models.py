from datetime import datetime, timezone

from app.main import db


class DocsQueryDocument(db.Model):
    __tablename__ = 'docs_query_documents'

    id = db.Column(db.Integer, primary_key=True)
    drive_file_id = db.Column(db.String(255), nullable=False, unique=True)
    document_title = db.Column(db.String(512))
    filename = db.Column(db.String(512))
    document_type = db.Column(db.String(255))
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

    document = db.relationship(
        DocsQueryDocument,
        backref=db.backref('chunks', cascade='all, delete-orphan', lazy=True),
    )
