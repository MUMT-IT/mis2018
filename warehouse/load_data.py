import os
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from create_research_fund_tables import *
from pandas import read_excel
import numpy

Base = automap_base()

POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')

engine = create_engine('postgres+psycopg2://postgres:{}@pg/mumtdw'\
                       .format(POSTGRES_PASSWORD))

mis_engine = create_engine('postgres+psycopg2://postgres:{}@pg/mumtmis_dev' \
                       .format(POSTGRES_PASSWORD))

Base.prepare(mis_engine, reflect=True)

Session = sessionmaker(bind=engine)
session = Session()

MisSession = sessionmaker(bind=mis_engine)
mis_session = MisSession()

StaffAccount = Base.classes.staff_account


def load_funding_resource(input_file, sheet_name=None):
    """ Read funding resources from the input file and add to the db if not exist.

    :param input_file:
    :param sheet_name:
    :return None:
    """
    df = read_excel(input_file, sheet_name=sheet_name)

    for source_name in df[df.columns[1]]:
        src_ = session.query(FundingSource).filter(
            FundingSource.source == source_name).first()
        if src_ is None:
            funding_source = FundingSource(source=source_name)
            session.add(funding_source)
    session.commit()

    '''
    staff = Staff(
        #staff_fname = row['first name'],
        #staff_lname = row['last name'],
        staff_email = row['all main researcher email']
    )
    department = Department(
        department_name=row['all department']
    )
    '''
    #session.add(staff)
    #session.add(department)

def load_funding_agency(input_file, sheet_name=None):
    df = read_excel(input_file, sheet_name=sheet_name)

    for agency_name in df[df.columns[2]]:
        ag = session.query(FundingAgency).filter(
            FundingAgency.name == agency_name).first()
        if ag is None:
            agency = FundingAgency(name=agency_name)
            session.add(agency)
    session.commit()


def load_research_project(input_file, sheet_name=None):
    """
    Load project information to the db.
    :param input_file:
    :param sheet_name:
    :return None:
    """

    df = read_excel(input_file, sheet_name=sheet_name)

    for idx, project in df[[df.columns[4], df.columns[5]]].iterrows():
        th_name, en_name = project

        en_name = en_name.strip() if not isinstance(en_name, float) else None
        th_name = th_name.strip() if not isinstance(th_name, float) else None

        if not th_name: # None or empty string
            th_name = en_name

        if th_name:
            project_ = session.query(ResearchProject).filter(
                ResearchProject.title_th == th_name
            ).first()
            if not project_:
                p = ResearchProject(title_th=th_name, title_en=en_name)
                session.add(p)

    session.commit()


def create_fact_table(input_file, sheet_name=None):
    """
    Load data from file and create the fact table.
    :param input_file:
    :param sheet_name:
    :return:
    """

    df = read_excel(input_file, sheet_name=sheet_name)
    for idx, row in df.iterrows():
        funding_source = session.query(FundingSource).filter(
            FundingSource.source == row['funding source']
        ).first()
        funding_agency = session.query(FundingAgency).filter(
            FundingAgency.name == row['funding agency']
        ).first()

        en_name = row['research title eng']
        th_name = row['research title thai']

        en_name = en_name.strip() if not isinstance(en_name, float) else None
        th_name = th_name.strip() if not isinstance(th_name, float) else None

        project = session.query(ResearchProject).filter(
                                    ResearchProject.title_th == th_name).first()
        if not project:
            project = session.query(ResearchProject).filter(
                                        ResearchProject.title_en == en_name).first()

        total_funding = row['amount fund']

        staff_email = row['main researcher email']
        staff_ = mis_session.query(StaffAccount).filter(StaffAccount.email == staff_email).first()
        if staff_:
            s = Staff(
                email=staff_.email,
                en_firstname=staff_.staff_personal_info.en_firstname,
                en_lastname=staff_.staff_personal_info.en_lastname,

            )
            session.add(s)
            session.commit()
        else:
            print('Staff not found.')


        if project and staff_:
            ft = FundingResearchFact(
                funding_source_id=funding_source.id,
                funding_agency_id=funding_agency.id,
                project_id=project.id,
                total_funding=total_funding,
                id=s.id,
            )
            session.add(ft)
        session.commit()


def load_researcher(input_file, sheet_name=None):
    """

    :param input_file:
    :param sheet_name:
    :return:
    """
    research_df = read_excel('samplefunding.xlsx',sheet_name='funding')

    for ix,row in research_df.iterrows():
        research = Research(
            research_title_th = row['research title thai'],
            research_title_en = row['research title eng'],
           # research_field = row['research_field'],
           # research_budget_thisyear = row['research_budget_thisyear'],
            est_funding = row['amount fund'],
            research_startdate = row['start date'],
            research_enddate = row['end date'],
          # duration = row['duration'],
            research_contract = row['research contract']
        )
        session.add(research)
    session.commit()


#st = session.query(Staff).filter(Staff.staff_email=='napat.son').first()
#st = session.query(Staff).filter(Staff.staff_email==row['staff_email']).first()
#st.staff_id

#int(datetime.strftime(row['research_startdate'], '%Y%m%d'))


if __name__ == '__main__':
    inputfile = sys.argv[1]
    sheetname = sys.argv[2]

    #load_funding_resource(inputfile, sheetname)
    #load_funding_agency(inputfile, sheetname)
    #load_research_project(inputfile, sheetname)
    create_fact_table(inputfile, sheetname)