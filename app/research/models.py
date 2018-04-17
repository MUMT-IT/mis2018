from ..main import db
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSON

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
    author_id = db.Column('author_id', db.ForeignKey('staff_account.email'))
    data = db.Column('data', JSON)
    updated_at = db.Column('updated_at', db.DateTime, onupdate=func.now())
    created_at = db.Column('created_at', db.DateTime, default=func.now())
