# -*- coding:utf-8 -*-
import os
import json
import click
import requests
from pytz import timezone
from flask.cli import AppGroup
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_wtf.csrf import CSRFProtect


BASEDIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.environ.get('DATABASE')

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'

ma = Marshmallow()
csrf = CSRFProtect()
admin = Admin()

dbutils = AppGroup('dbutils')


def create_app():
    """Create app based on the config setting
    """

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['LINE_CLIENT_ID'] = os.environ.get('LINE_CLIENT_ID')
    app.config['LINE_CLIENT_SECRET'] = os.environ.get('LINE_CLIENT_SECRET')
    app.config['LINE_MESSAGE_API_ACCESS_TOKEN'] = \
        os.environ.get('LINE_MESSAGE_API_ACCESS_TOKEN')
    app.config['LINE_MESSAGE_API_CLIENT_SECRET'] = \
        os.environ.get('LINE_MESSAGE_API_CLIENT_SECRET')

    db.init_app(app)
    ma.init_app(app)
    login.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    admin.init_app(app)
    return app


app = create_app()

@login.user_loader
def load_user(user_id):
    print('load user..')
    try:
        return StaffAccount.query.filter_by(id=int(user_id)).first()
    except:
        raise SystemExit


@app.route('/')
def index():
    return render_template('index.html')


json_keyfile = requests.get(os.environ.get('JSON_KEYFILE')).json()

from kpi import kpibp as kpi_blueprint

app.register_blueprint(kpi_blueprint, url_prefix='/kpi')


class KPIAdminModel(ModelView):
    can_create = True
    column_list = ('id', 'created_by', 'created_at',
                   'updated_at', 'updated_by', 'name')


from models import KPI

admin.add_views(KPIAdminModel(KPI, db.session, category='KPI'))

from studs import studbp as stud_blueprint

app.register_blueprint(stud_blueprint, url_prefix='/stud')

from food import foodbp as food_blueprint

app.register_blueprint(food_blueprint, url_prefix='/food')
from food.models import (Person, Farm, Produce, PesticideTest,
                         BactTest, ParasiteTest)

admin.add_views(ModelView(Person, db.session, category='Food'))
admin.add_views(ModelView(Farm, db.session, category='Food'))
admin.add_views(ModelView(Produce, db.session, category='Food'))
admin.add_views(ModelView(PesticideTest, db.session, category='Food'))
admin.add_views(ModelView(BactTest, db.session, category='Food'))
admin.add_views(ModelView(ParasiteTest, db.session, category='Food'))

from research import researchbp as research_blueprint

app.register_blueprint(research_blueprint, url_prefix='/research')
from research.models import ResearchPub

from staff import staffbp as staff_blueprint

app.register_blueprint(staff_blueprint, url_prefix='/staff')

from staff.models import StaffAccount, StaffPersonalInfo

admin.add_views(ModelView(StaffAccount, db.session, category='Staff'))
admin.add_views(ModelView(StaffPersonalInfo, db.session, category='Staff'))

from room_scheduler import roombp as room_blueprint

app.register_blueprint(room_blueprint, url_prefix='/room')
from room_scheduler.models import *

from vehicle_scheduler import vehiclebp as vehicle_blueprint

app.register_blueprint(vehicle_blueprint, url_prefix='/vehicle')
from vehicle_scheduler.models import *

admin.add_views(ModelView(RoomResource, db.session, category='Physicals'))
admin.add_views(ModelView(RoomEvent, db.session, category='Physicals'))
admin.add_views(ModelView(RoomType, db.session, category='Physicals'))
admin.add_views(ModelView(RoomAvailability, db.session, category='Physicals'))
admin.add_views(ModelView(EventCategory, db.session, category='Physicals'))

admin.add_view(ModelView(VehicleResource, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleAvailability, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleType, db.session, category='Physicals'))

from auth import authbp as auth_blueprint

app.register_blueprint(auth_blueprint, url_prefix='/auth')

from models import (Student, Class, ClassCheckIn,
                    Org, Mission, IOCode, CostCenter,
                    StudentCheckInRecord)
import database


class StudentCheckInAdminModel(ModelView):
    can_create = True
    form_columns = ('id', 'classchk', 'check_in_time', 'check_in_status', 'elapsed_mins')
    column_list = ('id', 'classchk', 'check_in_time', 'check_in_status', 'elapsed_mins')


admin.add_view(ModelView(Student, db.session, category='Student Affairs'))
admin.add_view(ModelView(ClassCheckIn, db.session, category='Student Affairs'))
admin.add_view(ModelView(Class, db.session, category='Student Affairs'))
admin.add_view(StudentCheckInAdminModel(
    StudentCheckInRecord, db.session, category='Student Affairs'))

admin.add_view(ModelView(Org, db.session, category='Organization'))
admin.add_view(ModelView(Mission, db.session, category='Organization'))

from asset import assetbp as asset_blueprint

app.register_blueprint(asset_blueprint, url_prefix='/asset')

from asset.models import *

admin.add_view(ModelView(AssetItem, db.session, category='Asset'))


class IOCodeAdminModel(ModelView):
    can_create = True
    form_columns = ('id', 'cost_center', 'mission', 'org', 'name')
    column_list = ('id', 'cost_center', 'mission', 'org', 'name')


admin.add_view(IOCodeAdminModel(IOCode, db.session, category='Finance'))


class CostCenterAdminModel(ModelView):
    can_create = True
    form_columns = ('id',)
    column_list = ('id',)


admin.add_view(CostCenterAdminModel(CostCenter, db.session, category='Finance'))

from lisedu import lisedu as lis_blueprint

app.register_blueprint(lis_blueprint, url_prefix='/lis')
from lisedu.models import *

from chemdb import chemdbbp as chemdb_blueprint
import chemdb.models

app.register_blueprint(chemdb_blueprint, url_prefix='/chemdb')

from comhealth import comhealth as comhealth_blueprint
from comhealth.models import *

app.register_blueprint(comhealth_blueprint, url_prefix='/comhealth')
admin.add_view(ModelView(ComHealthTest, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestProfile, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomer, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthOrg, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthRecord, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestProfileItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthService, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestGroup, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthContainer, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerInfoItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCashier, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthReceiptID, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerEmploymentType, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthReferenceTestProfile, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerInfo, db.session, category='Com Health'))
from comhealth.views import CustomerEmploymentTypeUploadView

admin.add_view(CustomerEmploymentTypeUploadView(
    name='Upload employment types',
    endpoint='employment_type', category='Com Health'))


@app.cli.command()
def populatedb():
    # database.load_orgs()
    # database.load_strategy()
    # database.load_tactics()
    # database.load_themes()
    database.load_activities()


from database import load_students


@dbutils.command('import_student')
@click.argument('excelfile')
def import_students(excelfile):
    load_students(excelfile)


app.cli.add_command(dbutils)


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


@dbutils.command('load_staff_list')
@click.argument('excel_file')
def load_staff_list(excel_file):
    database.load_staff_list(excel_file)


@dbutils.command('import_chem_items')
@click.argument('excel_file')
def import_chem_items(excel_file):
    database.load_chem_items(excel_file)


@app.template_filter("moneyformat")
def money_format(value):
    return '{:,.2f}'.format(value)


@app.template_filter("localdatetime")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%d/%m/%Y %H:%M'
    return dt.astimezone(bangkok).strftime(datetime_format)


@app.template_filter("localdate")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%d/%m/%Y'
    return dt.astimezone(bangkok).strftime(datetime_format)


@app.template_filter("sorttest")
def sort_test_item(tests):
    return sorted(tests, key=lambda x: x.test.name)


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
