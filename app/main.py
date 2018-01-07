from flask import Flask
from sqlalchemy import create_engine, MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    migrate.init_app(app, db)
    return app

import os
config_name = os.environ.get('FLASK_CONFIG', 'default')
app = create_app(config_name)

'''
from kpi import kpibp as kpi_blueprint
app.register_blueprint(kpi_blueprint, url_prefix='/kpi')
'''

from studs import studbp as stud_blueprint
app.register_blueprint(stud_blueprint, url_prefix='/stud')

from models import Student, Class

@app.cli.command()
def populatedb():
    load_orgs()
    load_strategy()
    load_tactics()
    load_themes()
    load_activities()


from database import load_students

@app.cli.command()
def populate_students():
    load_students()


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")