from sqlalchemy import (create_engine, Column, Integer)
from sqlalchemy.ext.declarative import declarative_base

dw_engine = create_engine('postgresql+psycopg2://postgres:{}@pg/mumtdw')

Base = declarative_base()


class Date(Base):
    __tablename__ = 'dates'
    date_id = Column(Integer, primary_key=True)
    day = Column(Integer)
    month = Column(Integer)
    quarter = Column(Integer)
    day_no = Column(Integer)
    gregorian_year = Column(Integer)
    fiscal_year = Column(Integer)


Base.metadata.create_all(dw_engine)
