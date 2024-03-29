import os
from sqlalchemy import (create_engine, Column, Integer, Text,
                        String, Date, ForeignKey, Float, Boolean)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship, backref

POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')

Base = declarative_base()

engine = create_engine('postgres+psycopg2://postgres:{}@pg/mumtdw'
                       .format(POSTGRES_PASSWORD))

class DateTable(Base):
    __tablename__ = 'dates'
    date_id = Column(Integer, primary_key=True)
    day = Column(Integer)
    month = Column(Integer)
    month_name = Column(String(16))
    quarter = Column(Integer)
    fc_quarter = Column(Integer)
    day_of_year = Column(Integer)
    day_of_week = Column(Integer)
    gregorian_year = Column(Integer)
    buddhist_year = Column(Integer)
    fiscal_year = Column(Integer)
    weekday = Column(String(16))

# Change att duration and funding_contract
class FundingSource(Base):
    __tablename__ = 'research_funding_sources'
    id = Column('id', Integer, autoincrement=True, primary_key=True)
    source = Column('source', String())


class FundingAgency(Base):
    __tablename__ = 'research_funding_agencies'
    id = Column('id', Integer, autoincrement=True, primary_key=True)
    name = Column('name', String())


class Staff(Base):
    __tablename__ = 'research_funding_staff'
    id = Column('id', Integer, autoincrement=True, primary_key=True)
    en_firstname = Column('firstname', String())
    en_lastname = Column('lastname', String())
    email = Column('email', String())


class Department(Base):
    __tablename__ = 'research_funding_department'
    id = Column('id', Integer, autoincrement=True, primary_key=True)
    mis_id = Column('mis_id', Integer)
    name = Column('name', String(), index=True)


class ResearchProject(Base):
    __tablename__ = 'research_funding_projects'
    id = Column('id', Integer, autoincrement=True, primary_key=True)
    title_th = Column('title_th', String(), index=True)
    title_en = Column('title_en', String(), index=True)
    est_funding = Column('est_funding',Float())
    startdate = Column('startdate', Date())
    enddate = Column('enddate', Date())
    contract = Column('contract', Boolean())


class FundingResearchFact(Base):
    __tablename__ = 'research_funding_fact'
    id = Column('id', Integer, primary_key=True, autoincrement=True)
    source_id = Column('source_id', ForeignKey('research_funding_sources.id'))
    agency_id = Column('agency_id', ForeignKey('research_funding_agencies.id'))
    project_id = Column('project_id', ForeignKey('research_funding_projects.id'))
    staff_id = Column('staff_id', ForeignKey('research_funding_staff.id'))
    # department_id = Column('department_id', ForeignKey('department.department_id'))
    startdate_id = Column('startdate_id', ForeignKey('dates.date_id'))
    enddate_id = Column('enddate_id', ForeignKey('dates.date_id'))
    total_funding = Column('total_funding', Float())


class Abstract(Base):
    __tablename__ = 'research_abstracts'
    id = Column('id', Integer, primary_key=True, autoincrement=True)
    scopus_id = Column('scopus_id', String(128), index=True)
    date_id = Column('date_id', ForeignKey('dates.date_id'))
    cover_date = relationship(DateTable, backref=backref('abstracts'))
    abstract = Column('abstract', Text())
    title = Column('title', String())
    publication = Column('publication', String())
    authors = Column('authors', JSON)
    cited = Column('cited', Integer(), default=0)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
