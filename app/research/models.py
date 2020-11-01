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
    scopus_id = db.Column('scopus_id', db.String(128), index=True)
    data = db.Column('data', JSON)
    created_at = db.Column('created_at', db.DateTime, default=func.now())
    citedby_count = db.Column('cited_count', db.Integer, default=0)
    title = db.Column('title', db.String())
    abstract = db.Column('abstract', db.Text())
    cover_date = db.Column('cover_date', db.Date())

