from ..main import db
from app.staff.models import StaffPersonalInfo
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSON


pub_authors = db.Table('pub_author_assoc',
                       db.Column('author_id', db.ForeignKey('research_authors.id')),
                       db.Column('pub_id', db.ForeignKey('research_pub.id')),
                       )


pub_subj_areas = db.Table('pub_subjarea_assoc',
                       db.Column('subj_id', db.ForeignKey('research_subject_areas.id')),
                       db.Column('pub_id', db.ForeignKey('research_pub.id')),
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
    publication_name = db.Column('publication_name', db.String())
    scopus_link = db.Column('scopus_link', db.String())
    doi = db.Column('doi', db.String())
    authors = db.relationship('Author',
                              secondary=pub_authors,
                              backref=db.backref('papers'))
    areas = db.relationship('SubjectArea',
                              secondary=pub_subj_areas,
                              backref=db.backref('papers'))


class Author(db.Model):
    __tablename__ = 'research_authors'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    firstname = db.Column('firstname', db.String())
    lastname = db.Column('lastname', db.String())
    affil_id = db.Column('affil_id', db.ForeignKey('research_affils.id'))
    affil = db.relationship('Affiliation', backref=db.backref('authors'))
    personal_info_id = db.Column('personal_info_id', db.ForeignKey('staff_personal_info.id'))
    personal_info = db.relationship(StaffPersonalInfo,
                                    backref=db.backref('research_author', uselist=False))
    h_index = db.Column('h_index', db.Integer())


class ScopusAuthorID(db.Model):
    __tablename__ = 'research_scopus_ids'
    id = db.Column('id', db.String(), primary_key=True)
    author_id = db.Column('author_id', db.ForeignKey('research_authors.id'))
    author = db.relationship('Author', backref=db.backref('scopus_ids'))


class Affiliation(db.Model):
    __tablename__ = 'research_affils'
    id = db.Column('id', db.String(), primary_key=True)
    name = db.Column('name', db.String(), nullable=False)
    country_id = db.Column('country_id', db.ForeignKey('research_countries.id'))
    country = db.relationship('Country', backref=db.backref('affiliations'))


class SubjectArea(db.Model):
    __tablename__ = 'research_subject_areas'
    id = db.Column('id', db.String(), primary_key=True)
    abbr = db.Column('abbr', db.String(), nullable=False)
    area = db.Column('area', db.String(), nullable=False)


class Country(db.Model):
    __tablename__ = 'research_countries'
    id = db.Column('id', db.Integer(), autoincrement=True, primary_key=True)
    name = db.Column('name', db.String(), nullable=False)
