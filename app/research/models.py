from ..main import db
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSON

pubs_authors = db.Table('pub_author_table',
    db.Column('author_email', db.String, db.ForeignKey('staff_account.email'), primary_key=True),
    db.Column('pub_id', db.Integer, db.ForeignKey('research_pub.id'), primary_key=True)
)

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    service = db.Column('service', db.String(), nullable=False)
    key = db.Column('key', db.String(), nullable=False)
    description = db.Column('description', db.String())


class ResearchPub(db.Model):
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    uid = db.Column('uid', db.String())
    indexed_db = db.Column('indexed_db', db.String())
    data = db.Column('data', JSON)
    updated_at = db.Column('updated_at', db.DateTime, onupdate=func.now())
    created_at = db.Column('created_at', db.DateTime, default=func.now())
    citation_count = db.Column('citation_count', db.Integer, default=0)
    authors = db.relationship('StaffAccount', secondary=pubs_authors, lazy='subquery',
                                backref=db.backref('pubs', lazy=True))