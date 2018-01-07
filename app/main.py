from flask import Flask
from sqlalchemy import create_engine, MetaData
engine = create_engine('postgres+psycopg2://postgres:genius01@localhost:5444/test')
meta = MetaData(bind=engine, reflect=True)
connect = engine.connect()

app = Flask(__name__)

from kpi import kpibp as kpi_blueprint
app.register_blueprint(kpi_blueprint, url_prefix='/kpi')


from database import *

@app.cli.command()
def initdb():
    """Initialize the database"""
    create_db()


@app.cli.command()
def populatedb():
    load_orgs()
    load_strategy()
    load_tactics()
    load_themes()
    load_activities()


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")