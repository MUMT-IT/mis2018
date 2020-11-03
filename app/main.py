# -*- coding:utf-8 -*-
import os
import click
import arrow
import pandas
import requests
from pytz import timezone
from flask.cli import AppGroup
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_wtf.csrf import CSRFProtect
from wtforms.validators import required
from datetime import timedelta, datetime
from flask_mail import Mail
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']


def get_credential(json_keyfile):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return gspread.authorize(credentials)


BASEDIR = os.path.abspath(os.path.dirname(__file__))

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'

ma = Marshmallow()
csrf = CSRFProtect()
admin = Admin()
mail = Mail()

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
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = ('MUMT-MIS', os.environ.get('MAIL_USERNAME'))

    db.init_app(app)
    ma.init_app(app)
    login.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    admin.init_app(app)
    mail.init_app(app)
    return app


app = create_app()


def get_weekdays(req):
    delta = req.end_datetime - req.start_datetime
    n = 0
    weekdays = 0
    while n <= delta.days:
        d = req.start_datetime + timedelta(n)
        if d.weekday() < 5:
            # if holidays and d not in holidays:
            weekdays += 1
        n += 1
    if delta.days == 0:
        if delta.seconds == 0:
            return weekdays
        if delta.seconds / 3600 < 8:
            if weekdays == 0:
                return 0
            else:
                return 0.5
        else:
            return weekdays
    else:
        return weekdays


@login.user_loader
def load_user(user_id):
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


from events import event_bp as event_blueprint

app.register_blueprint(event_blueprint, url_prefix='/events')

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

from staff.models import (StaffAccount, StaffPersonalInfo,
                          StaffLeaveApprover, StaffLeaveQuota,
                          StaffLeaveRequest, StaffLeaveType,
                          StaffLeaveApproval, StaffEmployment,
                          StaffWorkFromHomeRequest, StaffWorkFromHomeJobDetail,
                          StaffWorkFromHomeApprover, StaffWorkFromHomeApproval,
                          StaffWorkFromHomeCheckedJob, StaffLeaveRemainQuota, StaffWorkLogin)

admin.add_views(ModelView(StaffAccount, db.session, category='Staff'))
admin.add_views(ModelView(StaffPersonalInfo, db.session, category='Staff'))
admin.add_views(ModelView(StaffEmployment, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveType, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveApproval, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeRequest, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeJobDetail, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApproval, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeCheckedJob, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveRemainQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkLogin, db.session, category='Staff'))


class StaffLeaveRequestModelView(ModelView):
    can_export = True


admin.add_views(StaffLeaveRequestModelView(StaffLeaveRequest,
                                           db.session,
                                           category='Staff'))

from app.staff.views import LoginDataUploadView

admin.add_view(LoginDataUploadView(
    name='Upload login data',
    endpoint='login_data',
    category='Human Resource')
)

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
                    StudentCheckInRecord, Holidays)

admin.add_view(ModelView(Holidays, db.session, category='Holidays'))

from line import linebot_bp as linebot_blueprint

app.register_blueprint(linebot_blueprint, url_prefix='/linebot')

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
admin.add_view(ModelView(ComHealthTestProfile, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomer, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthOrg, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthRecord, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestProfileItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthService, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthTestGroup, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerInfoItem, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCashier, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthReceiptID, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerEmploymentType, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthReferenceTestProfile, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerInfo, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthSpecimensCheckinRecord, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthReceipt, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthInvoice, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthFinanceContactReason, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthCustomerGroup, db.session, category='Com Health'))


class ComHealthTestModelView(ModelView):
    form_args = {
        'name': {
            'validators': [required()]
        },
        'code': {
            'label': 'Test code',
            'validators': [required()]
        }
    }


class ComHealthContainerModelView(ModelView):
    form_args = {
        'name': {
            'validators': [required()]
        }
    }
    form_choices = {
        'group': [('basic', u'พื้นฐาน'), ('extra', u'เพิ่ม')]
    }

    form_columns = ['name', 'detail', 'desc', 'volume', 'group']


class ComHealthDepartmentModelView(ModelView):
    form_args = {
        'name': {
            'validators': [required()]
        }
    }


admin.add_view(ComHealthTestModelView(ComHealthTest, db.session, category='Com Health'))
admin.add_view(ComHealthContainerModelView(ComHealthContainer, db.session, category='Com Health'))
admin.add_view(ComHealthDepartmentModelView(ComHealthDepartment, db.session, category='Com Health'))

from smartclass_scheduler import smartclass_scheduler_blueprint

app.register_blueprint(smartclass_scheduler_blueprint, url_prefix='/smartclass')
from smartclass_scheduler.models import (SmartClassOnlineAccount,
                                         SmartClassResourceType,
                                         SmartClassOnlineAccountEvent)

admin.add_view(ModelView(SmartClassOnlineAccount, db.session, category='Smartclass'))
admin.add_view(ModelView(SmartClassResourceType, db.session, category='Smartclass'))
admin.add_view(ModelView(SmartClassOnlineAccountEvent, db.session, category='Smartclass'))

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


@dbutils.command('add-update-staff-gsheet')
def add_update_staff_gsheet():
    sheetid = '17lUlFNYk5znYqXL1vVCmZFtgTcjGvlNRZIlaDaEhy5E'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("index")
    df = pandas.DataFrame(sheet.get_all_records())
    df['employed'] = df.empdate.map(lambda x: datetime(*[int(x) for x in x.split('-')]))
    employments = {}
    orgs = {}
    for org in Org.query.all():
        orgs[org.name] = org
    for emp in StaffEmployment.query.all():
        employments[emp.title] = emp
    for idx, row in df.iterrows():
        account = StaffAccount.query.filter_by(email=row['e-mail']).first()
        if not account:
            account = StaffAccount(email=row['e-mail'])
            print('{} new account created..'.format(account.email))
        if not account.personal_info:
            personal_info = StaffPersonalInfo(
                th_firstname=row['firstname'],
                th_lastname=row['lastname'],
                en_firstname='-',
                en_lastname='-',
                employed_date=row['employed'],
                employment=employments[row['emptype']]
            )
            account.personal_info = personal_info
            db.session.add(personal_info)
        else:
            account.personal_info.employed_date = row['employed']
            account.personal_info.employment = employments[row['emptype']]

        if row['unit'] and orgs.get(row['unit']):
            account.personal_info.org = orgs[row['unit']]
        elif row['dept'] and orgs.get(row['dept']):
            account.personal_info.org = orgs[row['dept']]

        db.session.add(account)
        db.session.commit()
        print('{} has been added/updated'.format(account.email))


@dbutils.command('update-remaining-leave-quota')
def update_remaining_leave_quota():
    sheetid = '17lUlFNYk5znYqXL1vVCmZFtgTcjGvlNRZIlaDaEhy5E'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("remain")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        account = StaffAccount.query.filter_by(email=row['e-mail']).first()
        if account and account.personal_info:
            quota = StaffLeaveQuota.query.filter_by(leave_type_id=1,
                                                    employment=account.personal_info.employment).first()
            remain_quota = StaffLeaveRemainQuota.query.filter_by(quota=quota, staff=account).first()
            if not remain_quota:
                remain_quota = StaffLeaveRemainQuota(quota=quota)
                account.remain_quota.append(remain_quota)
            remain_quota.year = row['year']
            remain_quota.last_year_quota = row['quota']
            db.session.add(account)
            db.session.commit()
            # print('{} updated..'.format(row['e-mail']))
        else:
            print('{} not found..'.format(row['e-mail']))


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


@app.template_filter("localtime")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%-H:%M'
    if dt:
        return dt.astimezone(bangkok).strftime(datetime_format)
    else:
        return None


@app.template_filter("localdatetime")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%-d %b %Y %H:%M'
    if dt:
        return dt.astimezone(bangkok).strftime(datetime_format)
    else:
        return None


@app.template_filter("humanizedt")
def humanize_datetime(dt):
    if dt:
        return arrow.get(dt, 'Asia/Bangkok').humanize()
    else:
        return None


@app.template_filter("localdate")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%-d %b %Y'
    return dt.astimezone(bangkok).strftime(datetime_format)


@app.template_filter("sorttest")
def sort_test_item(tests):
    return sorted(tests, key=lambda x: x.test.name)


import time


@app.template_filter("tojsdatetime")
def convert_date_to_js_datetime(select_dates, single=False):
    if single:
        return int(time.mktime(select_dates.timetuple())) * 1000
    else:
        if select_dates:
            return [int(time.mktime(d.timetuple())) * 1000 for d in select_dates if d]
        else:
            return []


@app.template_filter("checkallapprovals")
def check_all_approval(leave_requests, approver_id):
    for req in leave_requests:
        approval = StaffLeaveApproval.query.filter_by(
            request_id=req.id,
            approver_id=approver_id).first()
        if approval:
            continue
        else:
            return False
    return True


@app.template_filter("checkapprovals")
def check_approval(leave_request, approver_id):
    approvals = StaffLeaveApproval.query.filter_by(request_id=leave_request.id,
                                                   approver_id=approver_id,
                                                   ).first()
    if approvals:
        return True
    else:
        return False


@app.template_filter("checkwfhapprovals")
def check_wfh_approval(wfh_request, approver_id):
    approvals = StaffWorkFromHomeApproval.query.filter_by(request_id=wfh_request.id,
                                                          approver_id=approver_id,
                                                          ).first()
    if approvals:
        return True
    else:
        return False


@app.template_filter("getweekdays")
def count_weekdays(req):
    return get_weekdays(req)


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
