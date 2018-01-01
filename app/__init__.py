from flask import Flask
from sqlalchemy import create_engine, MetaData

engine = create_engine('postgres+psycopg2://likit@localhost/test')
meta = MetaData(bind=engine, reflect=True)
connect = engine.connect()

def create_app(config=None):
    if not config:
        app = Flask(__name__)

        from kpi import kpibp as kpi_blueprint
        app.register_blueprint(kpi_blueprint, url_prefix='/kpi')
        return app