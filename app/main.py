# -*- coding:utf-8 -*-
from flask import Flask
from sqlalchemy import create_engine, MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_login import LoginManager
from config import config
import json

db = SQLAlchemy()
migrate = Migrate()
ma = Marshmallow()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    ma.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    return app

import os
config_name = os.environ.get('FLASK_CONFIG', 'default')
app = create_app(config_name)

with app.open_resource(os.environ.get('JSON_KEYFILE')) as jk:
    json_keyfile = json.load(jk)

from kpi import kpibp as kpi_blueprint
app.register_blueprint(kpi_blueprint, url_prefix='/kpi')

from studs import studbp as stud_blueprint
app.register_blueprint(stud_blueprint, url_prefix='/stud')

from food import foodbp as food_blueprint
app.register_blueprint(food_blueprint, url_prefix='/food')

from staff import staffbp as staff_blueprint
app.register_blueprint(staff_blueprint, url_prefix='/staff')

from research import researchbp as research_blueprint
app.register_blueprint(research_blueprint, url_prefix='/research')

from models import Student, Class, ClassCheckIn
import database

from lisedu import lisedu as lis_blueprint
app.register_blueprint(lis_blueprint, url_prefix='/lis')
from lisedu.models import *

@app.cli.command()
def populatedb():
    # database.load_orgs()
    # database.load_strategy()
    # database.load_tactics()
    # database.load_themes()
    database.load_activities()


from database import load_students

@app.cli.command()
def populate_students():
    load_students()

@app.cli.command()
def populate_classes():
    klass = Class(refno='MTID101',
                th_class_name=u'การเรียนรู้เพื่อการเปลี่ยงแปลงสำหรับ MT',
                en_class_name='Transformative learning for MT',
                academic_year='2560')
    db.session.add(klass)
    db.session.commit()

@app.cli.command()
def populate_checkin():
    class_checkin = ClassCheckIn(
                        class_id=1,
                        deadline='10:00:00',
                        late_mins=15,
                    )
    db.session.add(class_checkin)
    db.session.commit()

from database import load_provinces, load_districts, load_subdistricts
@app.cli.command()
def populate_provinces():
    load_provinces()


@app.cli.command()
def populate_districts():
    load_districts()


@app.cli.command()
def populate_subdistricts():
    load_subdistricts()



if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
