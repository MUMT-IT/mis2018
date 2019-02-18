import os
import sys
from calendar import Calendar
from datetime import date
from sqlalchemy import (create_engine, Table,
                        MetaData, select, and_)

POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')

def main(year):
    # connect to the database
    print('Connecting to the database..')
    engine = create_engine('postgresql+psycopg2://postgres:{}@pg/mumtdw'
                           .format(POSTGRES_PASSWORD))

    connect = engine.connect()

    metadata = MetaData()

    date_table = Table('dates', metadata,
                       autoload=True, autoload_with=engine)

    quarters = {
        1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4, 11: 4, 12: 4
    }
    fc_quarters = {
        1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3, 7: 4, 8: 4, 9: 4, 10: 1, 11: 1, 12: 1
    }

    c = Calendar()
    newyear_date = date(year, 1, 1)

    for month in range(1, 13):
        for d in c.itermonthdates(year, month):
            if d.year == year:
                if connect.execute(select([date_table]).where(
                        and_(date_table.c.day == d.day,
                             date_table.c.month == d.month,
                             date_table.c.gregorian_year == d.year))).fetchone():
                    continue
                else:
                    if d.month != month:
                        continue
                    from_newyear = d - newyear_date
                    if d.month < 9:
                        fiscal_year = d.year - 1
                    else:
                        fiscal_year = d.year
                    date_id = str(d.year) + '{0:02d}'.format(d.month) + '{0:02d}'.format(d.day)
                    date_id = int(date_id)
                    ins = date_table.insert().values(
                        date_id=date_id,
                        day=d.day,
                        month=d.month,
                        month_name=d.strftime('%B'),
                        quarter=quarters[d.month],
                        fc_quarter=fc_quarters[d.month],
                        gregorian_year=d.year,
                        day_of_year=from_newyear.days + 1,
                        day_of_week=d.weekday() + 1,
                        buddhist_year=d.year + 543,
                        fiscal_year=fiscal_year,
                        weekday=d.strftime('%A')
                    )
                    result = connect.execute(ins)


if __name__ == '__main__':
    year = int(sys.argv[1])
    main(year)
