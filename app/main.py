# -*- coding:utf-8 -*-
import os
import click
import arrow
import pandas
import requests
from flask_principal import Principal, PermissionDenied, Identity
from flask.cli import AppGroup
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_wtf.csrf import CSRFProtect
from flask_qrcode import QRcode
from wtforms.validators import required
from flask_mail import Mail
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask_restful import Api, Resource


scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']


def get_credential(json_keyfile):
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return gspread.authorize(credentials)


BASEDIR = os.path.abspath(os.path.dirname(__file__))


class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and admin_permission.can()


load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
jwt = JWTManager()
login.login_view = 'auth.login'
cors = CORS()
ma = Marshmallow()
csrf = CSRFProtect()
admin = Admin(index_view=MyAdminIndexView())
mail = Mail()
qrcode = QRcode()
principal = Principal()

dbutils = AppGroup('dbutils')


@principal.identity_loader
def load_identity_when_session_expires():
    if hasattr(current_user, 'id'):
        return Identity(current_user.id)


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
    cors.init_app(app)
    qrcode.init_app(app)
    principal.init_app(app)
    jwt.init_app(app)

    return app


app = create_app()
api = Api(app)


# user_loader_callback_loader has renamed to user_lookup_loader in >=4.0
@jwt.user_loader_callback_loader
def user_lookup_callback(identity):
    return ScbPaymentServiceApiClientAccount.get_account_by_id(identity)


@app.errorhandler(403)
def page_not_found(e):
    return render_template('errors/403.html', error=e), 404


@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html', error=e), 404


@app.errorhandler(500)
def page_not_found(e):
    return render_template('errors/500.html', error=e), 500


@app.errorhandler(PermissionDenied)
def permission_denied(e):
    return render_template('errors/403.html', error=e), 403

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
from research.models import *

admin.add_views(ModelView(ResearchPub, db.session, category='Research'))
admin.add_views(ModelView(Author, db.session, category='Research'))

from procurement import procurementbp as procurement_blueprint

app.register_blueprint(procurement_blueprint, url_prefix='/procurement')
from procurement.models import *

admin.add_views(ModelView(ProcurementDetail, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementCategory, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementStatus, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementRecord, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementRequire, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementMaintenance, db.session, category='Procurement'))

from purchase_tracker import purchase_tracker_bp as purchase_tracker_blueprint

app.register_blueprint(purchase_tracker_blueprint, url_prefix='/purchase_tracker')
from app.purchase_tracker.models import *

admin.add_views(ModelView(PurchaseTrackerAccount, db.session, category='PurchaseTracker'))
admin.add_views(ModelView(PurchaseTrackerStatus, db.session, category='PurchaseTracker'))
admin.add_views(ModelView(PurchaseTrackerActivity, db.session, category='PurchaseTracker'))


from staff import staffbp as staff_blueprint

app.register_blueprint(staff_blueprint, url_prefix='/staff')


from staff.models import *

admin.add_views(ModelView(Role, db.session, category='Permission'))
admin.add_views(ModelView(StaffAccount, db.session, category='Staff'))
admin.add_views(ModelView(StaffPersonalInfo, db.session, category='Staff'))
admin.add_views(ModelView(StaffAcademicPosition, db.session, category='Staff'))
admin.add_views(ModelView(StaffEmployment, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveType, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeRequest, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeJobDetail, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApproval, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeCheckedJob, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveRemainQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffSeminar, db.session, category='Staff'))
admin.add_views(ModelView(StaffSeminarAttend, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkLogin, db.session, category='Staff'))
admin.add_views(ModelView(StaffSpecialGroup, db.session, category='Staff'))
admin.add_views(ModelView(StaffShiftSchedule, db.session, category='Staff'))
admin.add_views(ModelView(StaffShiftRole, db.session, category='Staff'))


class StaffLeaveApprovalModelView(ModelView):
    form_widget_args = {
        'updated_at': {
            'readonly': True
        },
    }

    def update_model(self, form, model):
        model.approver = form.approver.data
        model.is_approved = form.is_approved.data
        model.approval_comment = form.approval_comment.data
        self.session.add(model)
        self._on_model_change(form, model, False)
        self.session.commit()
        return redirect(url_for('staffaccount.index_view'))


admin.add_views(StaffLeaveApprovalModelView(StaffLeaveApproval,
                                            db.session,
                                            category='Staff'))


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


from ot import otbp as ot_blueprint

app.register_blueprint(ot_blueprint, url_prefix='/ot')
from ot.models import *

admin.add_views(ModelView(OtPaymentAnnounce, db.session, category='OT'))
admin.add_views(ModelView(OtCompensationRate, db.session, category='OT'))
admin.add_views(ModelView(OtDocumentApproval, db.session, category='OT'))
admin.add_views(ModelView(OtRecord, db.session, category='OT'))
admin.add_views(ModelView(OtRoundRequest, db.session, category='OT'))



from room_scheduler import roombp as room_blueprint

app.register_blueprint(room_blueprint, url_prefix='/room')
from room_scheduler.models import *

from vehicle_scheduler import vehiclebp as vehicle_blueprint

app.register_blueprint(vehicle_blueprint, url_prefix='/vehicle')
from vehicle_scheduler.models import *

admin.add_views(ModelView(RoomResource, db.session, category='Physicals'))
admin.add_views(ModelView(RoomComplaintTopic, db.session, category='Physicals'))
admin.add_views(ModelView(RoomComplaint, db.session, category='Physicals'))
admin.add_views(ModelView(RoomEvent, db.session, category='Physicals'))
admin.add_views(ModelView(RoomType, db.session, category='Physicals'))
admin.add_views(ModelView(RoomAvailability, db.session, category='Physicals'))
admin.add_views(ModelView(EventCategory, db.session, category='Physicals'))

admin.add_view(ModelView(VehicleResource, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleAvailability, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleType, db.session, category='Physicals'))

from auth import authbp as auth_blueprint
from app.roles import admin_permission

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

from eduqa import eduqa_bp as eduqa_blueprint
from eduqa.models import *
app.register_blueprint(eduqa_blueprint, url_prefix='/eduqa')
admin.add_view(ModelView(EduQACourseCategory, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACourse, db.session, category='EduQA'))


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
admin.add_view(ModelView(ComHealthDivision, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthConsentDetail, db.session, category='Com Health'))
admin.add_view(ModelView(ComHealthConsentRecord, db.session, category='Com Health'))


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


from pdpa import pdpa_blueprint
app.register_blueprint(pdpa_blueprint, url_prefix='/pdpa')

from app.pdpa.models import *

admin.add_view(ModelView(PDPARequest, db.session, category='PDPA'))
admin.add_view(ModelView(PDPARequestType, db.session, category='PDPA'))


class CoreServiceModelView(ModelView):
    form_excluded_columns = ('created_at', 'updated_at')


admin.add_view(CoreServiceModelView(CoreService, db.session, category='PDPA'))


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

from app.km import km_bp as km_blueprint

app.register_blueprint(km_blueprint, url_prefix='/km')

from app.km.models import *

admin.add_view(ModelView(KMProcess, db.session, category='Knowledge Management'))
admin.add_view(ModelView(KMTopic, db.session, category='Knowledge Management'))

from app.health_service_scheduler import health_service_blueprint

app.register_blueprint(health_service_blueprint, url_prefix='/health-service-scheduler')

# Restful APIs

from health_service_scheduler.apis import *

api.add_resource(HealthServiceSiteListResource, '/api/v1.0/hscheduler/sites')
api.add_resource(HealthServiceSiteResource, '/api/v1.0/hscheduler/sites/<int:id>')
api.add_resource(HealthServiceSlotListResource, '/api/v1.0/hscheduler/slots')
api.add_resource(HealthServiceSlotResource, '/api/v1.0/hscheduler/slots/<int:id>')
api.add_resource(HealthServiceBookingListResource, '/api/v1.0/hscheduler/bookings')
api.add_resource(HealthServiceBookingResource, '/api/v1.0/hscheduler/bookings/<int:id>')
api.add_resource(HealthServiceAppUserResource, '/api/v1.0/hscheduler/users/<int:id>')
api.add_resource(HealthServiceServiceListResource, '/api/v1.0/hscheduler/services')
api.add_resource(HealthServiceServiceResource, '/api/v1.0/hscheduler/services/<int:id>')

admin.add_view(ModelView(HealthServiceBooking, db.session, category='HealthScheduler'))
admin.add_view(ModelView(HealthServiceAppUser, db.session, category='HealthScheduler'))
admin.add_view(ModelView(HealthServiceTimeSlot, db.session, category='HealthScheduler'))
admin.add_view(ModelView(HealthServiceService, db.session, category='HealthScheduler'))
admin.add_view(ModelView(HealthServiceSite, db.session, category='HealthScheduler'))

from doc_circulation.models import *
from doc_circulation import docbp as doc_blueprint

app.register_blueprint(doc_blueprint, url_prefix='/docs')

admin.add_view(ModelView(DocRound, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocRoundOrg, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocRoundOrgReach, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocCategory, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocDocument, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocDocumentReach, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocReceiveRecord, db.session, category='Docs Circulation'))


from data_blueprint import data_bp as data_blueprint

app.register_blueprint(data_blueprint, url_prefix='/data-blueprint')


from scb_payment_service import scb_payment as scb_payment_blueprint

app.register_blueprint(scb_payment_blueprint)

from scb_payment_service.models import *


# Commands

@app.cli.command()
def populatedb():
    # database.load_orgs()
    # database.load_strategy()
    # database.load_tactics()
    # database.load_themes()
    database.load_activities()


from database import load_students


@dbutils.command('add-update-staff-finger-print-gsheet')
def add_update_staff_finger_print_gsheet():
    sheetid = '13_wlcGpl5BWtCdqMi9WxXXJL_CfPnd5t54gCjA6mYtE'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("Sheet1")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        firstname = row['firstname']
        lastname = row['lastname']
        accnt = StaffPersonalInfo.query.filter_by(th_firstname=firstname,
                                                  th_lastname=lastname).first()
        if accnt:
            accnt.finger_scan_id = row['ID']
            try:
                db.session.add(accnt)
                db.session.commit()
            except:
                print(u'{} {} failed'.format(row['firstname'], row['lastname']))


@dbutils.command('import-leave-data')
def import_leave_data():
    tz = timezone('Asia/Bangkok')

    sheetid = '1cM3T-kj1qgn24gZIUpOT3SGUQeIGhDdLdsCjgwj4Pgo'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("leave")
    df = pandas.DataFrame(sheet.get_all_records())
    df['start_date'] = df['start_date'].apply(pandas.to_datetime)
    df['end_date'] = df['end_date'].apply(pandas.to_datetime)
    for idx, row in df.iterrows():
        email = row['email']
        quota_id = row['quota_id']
        start_date = row['start_date']
        start_time = row['start_time']
        end_date = row['end_date']
        end_time = row['end_time']
        total_day = row['days']
        if not start_time:
            new_start_datetime = datetime(start_date.year, start_date.month, start_date.day, 8, 30)
        else:
            hour, mins = start_time.split(':')
            new_start_datetime = datetime(start_date.year, start_date.month, start_date.day, int(hour), int(mins))
        if not end_time:
            new_end_datetime = datetime(end_date.year, end_date.month, end_date.day, 8, 30)
        else:
            hour, mins = end_time.split(':')
            new_end_datetime = datetime(end_date.year, end_date.month, end_date.day, int(hour), int(mins))
        staff_account = StaffAccount.query.filter_by(email=row['email']).first()
        if staff_account:
            leave_request = StaffLeaveRequest(
                leave_quota_id=quota_id,
                staff_account_id=staff_account.id,
                start_datetime=tz.localize(new_start_datetime),
                end_datetime=tz.localize(new_end_datetime),
                created_at=tz.localize(datetime.today()),
                total_leave_days=total_day
            )
            db.session.add(leave_request)
            for approver in staff_account.leave_requesters:
                leave_approval = StaffLeaveApproval(
                    request=leave_request,
                    approver=approver,
                    updated_at=tz.localize(datetime.today()),
                    is_approved=True
                )
                db.session.add(leave_approval)
        else:
            print(u'Cannot save data of email: {} start date: {}'.format(email, start_date))
    db.session.commit()


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


@dbutils.command('update-remaining-leave-quota-2020')
def update_remaining_leave_quota():
    sheetid = '17lUlFNYk5znYqXL1vVCmZFtgTcjGvlNRZIlaDaEhy5E'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("remain2021")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        account = StaffAccount.query.filter_by(email=row['email']).first()
        if account and account.personal_info:
            quota = StaffLeaveQuota.query.filter_by(leave_type_id=1,
                                                    employment=account.personal_info.employment).first()
            remain_quota = StaffLeaveRemainQuota.query.filter_by(quota=quota, staff=account, year=2020).first()
            if not remain_quota:
                remain_quota = StaffLeaveRemainQuota(quota=quota)
                account.remain_quota.append(remain_quota)
            remain_quota.year = row['year']
            remain_quota.last_year_quota = row['quota']
            remain_quota.staff_account_id = account.id
            db.session.add(account)
            db.session.commit()
            # print('{} updated..'.format(row['e-mail']))
        else:
            print('{} not found..'.format(row['email']))


@dbutils.command('update-approver-gsheet')
def update_approver_gsheet():
    sheetid = '17lUlFNYk5znYqXL1vVCmZFtgTcjGvlNRZIlaDaEhy5E'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("approver")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        account = StaffAccount.query.filter_by(email=row['e-mail']).first()
        if not account:
            print('{} not found'.format(row['e-mail']))
            continue
        approver1 = StaffAccount.query.filter_by(email=row['approver1']).first()
        approver2 = StaffAccount.query.filter_by(email=row['approver2']).first()
        ap1 = StaffLeaveApprover.query.filter_by(staff_account_id=account.id,
                                                 approver_account_id=approver1.id).first()
        if not ap1:
            ap1 = StaffLeaveApprover(requester=account, account=approver1)
            db.session.add(ap1)
        if row['approver1'] != row['approver2']:
            ap2 = StaffLeaveApprover.query.filter_by(staff_account_id=account.id,
                                                     approver_account_id=approver2.id).first()
            if not ap2:
                ap2 = StaffLeaveApprover(requester=account, approver=approver2)
                db.session.add(ap2)
        db.session.commit()


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
    datetime_format = '%X'
    if dt:
        return dt.astimezone(bangkok).strftime(datetime_format)
    else:
        return None


@app.template_filter("localdatetime")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%d/%m/%Y %X'
    if dt:
        return dt.astimezone(bangkok).strftime(datetime_format)
    else:
        return None


@app.template_filter("humanizedt")
def humanize_datetime(dt):
    if dt:
        return arrow.get(dt.astimezone(bangkok)).humanize()
    else:
        return None


@app.template_filter("localdate")
def local_datetime(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%x'
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


@app.template_filter("truncate")
def truncate_text(text, length=150):
    if text:
        if len(text) > length:
            return u'{}...'.format(text[:length])
        else:
            return text
    return ''


@app.template_filter("getweekdays")
def count_weekdays(req):
    return get_weekdays(req)


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
