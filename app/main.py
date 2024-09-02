# -*- coding:utf-8 -*-
import base64
import os
import click
import arrow
import pandas
import pandas as pd
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
from psycopg2._range import DateTimeRange
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from flask_mail import Mail
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask_restful import Api

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
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('://', 'ql://', 1)
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
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = ('MUMT-MIS',
                                         os.environ.get('MAIL_USERNAME'))

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
@jwt.user_lookup_loader
def user_lookup_callback(identity, payload):
    print(payload)
    # TODO: Need to allow loading a client from other services.
    return ScbPaymentServiceApiClientAccount.get_account_by_id(payload.get('sub'))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html', error=e), 404


@app.errorhandler(500)
def internal_server_error(e):
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
    return render_template('index.html',
                           now=datetime.now(tz=timezone('Asia/Bangkok')))


@app.route('/user-support')
def user_support_index():
    return render_template('support.html')


json_keyfile = requests.get(os.environ.get('JSON_KEYFILE')).json()

from app.kpi import kpibp as kpi_blueprint

app.register_blueprint(kpi_blueprint, url_prefix='/kpi')

from app.complaint_tracker import complaint_tracker
from app.complaint_tracker.models import *

app.register_blueprint(complaint_tracker)

admin.add_views(ModelView(ComplaintTopic, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintCategory, db.session, category='Complaint'))
admin.add_views((ModelView(ComplaintSubTopic, db.session, category='Complaint')))
admin.add_views(ModelView(ComplaintAdmin, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintStatus, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintPriority, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintRecord, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintActionRecord, db.session, category='Complaint'))
admin.add_views(ModelView(ComplaintInvestigator, db.session, category='Complaint'))


class KPIAdminModel(ModelView):
    can_create = True
    column_list = ('id', 'created_by', 'created_at',
                   'updated_at', 'updated_by', 'name', 'target_account')


from app import models

from app.events import event_bp as event_blueprint

app.register_blueprint(event_blueprint, url_prefix='/events')

admin.add_views(KPIAdminModel(models.KPI, db.session, category='KPI'))

from app.studs import studbp as stud_blueprint

app.register_blueprint(stud_blueprint, url_prefix='/stud')

from app.food import foodbp as food_blueprint

app.register_blueprint(food_blueprint, url_prefix='/food')
from app.food.models import (Person, Farm, Produce, PesticideTest,
                             BactTest, ParasiteTest)

admin.add_views(ModelView(Person, db.session, category='Food'))
admin.add_views(ModelView(Farm, db.session, category='Food'))
admin.add_views(ModelView(Produce, db.session, category='Food'))
admin.add_views(ModelView(PesticideTest, db.session, category='Food'))
admin.add_views(ModelView(BactTest, db.session, category='Food'))
admin.add_views(ModelView(ParasiteTest, db.session, category='Food'))

from app.research import researchbp as research_blueprint

app.register_blueprint(research_blueprint, url_prefix='/research')
from app.research.models import *

admin.add_views(ModelView(ResearchPub, db.session, category='Research'))
admin.add_views(ModelView(Author, db.session, category='Research'))

from app.procurement import procurementbp as procurement_blueprint

app.register_blueprint(procurement_blueprint, url_prefix='/procurement')
from app.procurement.models import *


class MyProcurementModelView(ModelView):
    form_excluded_columns = ('qrcode', 'records', 'repair_records',
                             'computer_info', 'borrow_items')


admin.add_views(MyProcurementModelView(ProcurementDetail, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementCategory, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementStatus, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementRecord, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementRequire, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementPurchasingType, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementCommitteeApproval, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementInfoComputer, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementInfoCPU, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementInfoRAM, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementInfoWindowsVersion, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementSurveyComputer, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementBorrowDetail, db.session, category='Procurement'))
admin.add_views(ModelView(ProcurementBorrowItem, db.session, category='Procurement'))

from app.purchase_tracker import purchase_tracker_bp as purchase_tracker_blueprint

app.register_blueprint(purchase_tracker_blueprint, url_prefix='/purchase_tracker')
from app.purchase_tracker.models import *

admin.add_views(ModelView(PurchaseTrackerAccount, db.session, category='PurchaseTracker'))
admin.add_views(ModelView(PurchaseTrackerStatus, db.session, category='PurchaseTracker'))
admin.add_views(ModelView(PurchaseTrackerActivity, db.session, category='PurchaseTracker'))
admin.add_views(ModelView(PurchaseTrackerForm, db.session, category='PurchaseTracker'))

from app.receipt_printing import receipt_printing_bp as receipt_printing_blueprint

app.register_blueprint(receipt_printing_blueprint, url_prefix='/receipt_printing')
from app.receipt_printing.models import *


class ElectronicReceiptGLModel(ModelView):
    can_create = True
    form_columns = ('gl', 'receive_name', 'items_gl')
    column_list = ('gl', 'receive_name', 'items_gl')


admin.add_views(ModelView(ElectronicReceiptDetail, db.session, category='ReceiptPrinting'))
admin.add_views(ModelView(ElectronicReceiptItem, db.session, category='ReceiptPrinting'))
admin.add_views(ModelView(ElectronicReceiptRequest, db.session, category='ReceiptPrinting'))
admin.add_views(ModelView(ElectronicReceiptReceivedMoneyFrom, db.session, category='ReceiptPrinting'))
admin.add_views(ModelView(ElectronicReceiptBankName, db.session, category='ReceiptPrinting'))
admin.add_views(ElectronicReceiptGLModel(ElectronicReceiptGL, db.session, category='ReceiptPrinting'))

from app.instruments import instrumentsbp as instruments_blueprint

app.register_blueprint(instruments_blueprint, url_prefix='/instruments')

from app.instruments.models import *

admin.add_views(ModelView(InstrumentsBooking, db.session, category='Instruments'))

from app.alumni import alumnibp as alumni_blueprint

app.register_blueprint(alumni_blueprint, url_prefix='/alumni')

from app.alumni.models import *

admin.add_views(ModelView(AlumniInformation, db.session, category='Alumni'))

from app.staff import staffbp as staff_blueprint

app.register_blueprint(staff_blueprint, url_prefix='/staff')

from app.staff.models import *
admin.add_view(ModelView(StrategyActivity, db.session, category='Strategy'))
admin.add_views(ModelView(Role, db.session, category='Permission'))
admin.add_views(ModelView(StaffAccount, db.session, category='Staff'))
admin.add_views(ModelView(StaffPersonalInfo, db.session, category='Staff'))
admin.add_views(ModelView(StaffEduDegree, db.session, category='Staff'))
admin.add_views(ModelView(StaffAcademicPosition, db.session, category='Staff'))
admin.add_views(ModelView(StaffAcademicPositionRecord, db.session, category='Staff'))
admin.add_views(ModelView(StaffEmployment, db.session, category='Staff'))
admin.add_views(ModelView(StaffJobPosition, db.session, category='Staff'))
admin.add_views(ModelView(StaffHeadPosition, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveType, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeRequest, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeJobDetail, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApprover, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeApproval, db.session, category='Staff'))
admin.add_views(ModelView(StaffWorkFromHomeCheckedJob, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveRemainQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffLeaveUsedQuota, db.session, category='Staff'))
admin.add_views(ModelView(StaffSeminarPreRegister, db.session, category='Seminar'))
admin.add_views(ModelView(StaffSeminar, db.session, category='Seminar'))
admin.add_views(ModelView(StaffSeminarAttend, db.session, category='Seminar'))
admin.add_views(ModelView(StaffWorkLogin, db.session, category='Staff'))
admin.add_views(ModelView(StaffRequestWorkLogin, db.session, category='Staff'))
admin.add_views(ModelView(StaffSpecialGroup, db.session, category='Staff'))
admin.add_views(ModelView(StaffShiftSchedule, db.session, category='Staff'))
admin.add_views(ModelView(StaffShiftRole, db.session, category='Staff'))
admin.add_views(ModelView(StaffSeminarApproval, db.session, category='Seminar'))
admin.add_views(ModelView(StaffSeminarMission, db.session, category='Seminar'))
admin.add_views(ModelView(StaffSeminarObjective, db.session, category='Seminar'))
admin.add_views(ModelView(StaffSeminarProposal, db.session, category='Seminar'))
admin.add_views(ModelView(StaffGroupDetail, db.session, category='Staff'))
admin.add_views(ModelView(StaffGroupPosition, db.session, category='Staff'))
admin.add_views(ModelView(StaffGroupAssociation, db.session, category='Staff'))


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

from app.ot import otbp as ot_blueprint

app.register_blueprint(ot_blueprint, url_prefix='/ot')
from app.ot.models import *

admin.add_views(ModelView(OtPaymentAnnounce, db.session, category='OT'))
admin.add_views(ModelView(OtDocumentApproval, db.session, category='OT'))
admin.add_views(ModelView(OtRecord, db.session, category='OT'))
admin.add_views(ModelView(OtRoundRequest, db.session, category='OT'))
admin.add_views(ModelView(OtCompensationRate, db.session, category='OT'))
admin.add_views(ModelView(OtTimeSlot, db.session, category='OT'))
admin.add_views(ModelView(OtShift, db.session, category='OT'))
admin.add_views(ModelView(OtJobRole, db.session, category='OT'))

from app.room_scheduler import roombp as room_blueprint

app.register_blueprint(room_blueprint, url_prefix='/room')
from app.room_scheduler.models import *

from app.vehicle_scheduler import vehiclebp as vehicle_blueprint

app.register_blueprint(vehicle_blueprint, url_prefix='/vehicle')
from app.vehicle_scheduler.models import *


class RoomModelView(ModelView):
    can_view_details = True
    form_excluded_columns = ['items', 'reservations', 'equipments']


admin.add_views(RoomModelView(RoomResource, db.session, category='Physicals'))
admin.add_views(ModelView(RoomEvent, db.session, category='Physicals'))
admin.add_views(ModelView(RoomType, db.session, category='Physicals'))
admin.add_views(ModelView(RoomAvailability, db.session, category='Physicals'))
admin.add_views(ModelView(EventCategory, db.session, category='Physicals'))

admin.add_view(ModelView(VehicleResource, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleAvailability, db.session, category='Physicals'))
admin.add_view(ModelView(VehicleType, db.session, category='Physicals'))

from app.auth import authbp as auth_blueprint
from app.roles import admin_permission

app.register_blueprint(auth_blueprint, url_prefix='/auth')

from app.models import (Org, OrgStructure, Mission, Holidays, Dashboard)

admin.add_view(ModelView(Holidays, db.session, category='Holidays'))

from app.line import linebot_bp as linebot_blueprint

app.register_blueprint(linebot_blueprint, url_prefix='/linebot')

from app import database


class MyOrgModelView(ModelView):
    form_excluded_columns = ('procurements', 'vehicle_bookings', 'document_approval', 'ot_records')


admin.add_view(ModelView(models.Student, db.session, category='Student Affairs'))
admin.add_view(MyOrgModelView(Org, db.session, category='Organization'))
admin.add_view(ModelView(Mission, db.session, category='Organization'))
admin.add_view(ModelView(Dashboard, db.session, category='Organization'))
admin.add_view(ModelView(OrgStructure, db.session, category='Organization'))

from app.asset import assetbp as asset_blueprint

app.register_blueprint(asset_blueprint, url_prefix='/asset')

from app.asset.models import *

admin.add_view(ModelView(AssetItem, db.session, category='Asset'))


class IOCodeAdminModel(ModelView):
    can_create = True
    form_columns = ('id', 'cost_center', 'mission', 'org', 'name', 'is_active')
    column_list = ('id', 'cost_center', 'mission', 'org', 'name', 'is_active')


admin.add_view(IOCodeAdminModel(models.IOCode, db.session, category='Finance'))


class CostCenterAdminModel(ModelView):
    can_create = True
    form_columns = ('id',)
    column_list = ('id',)


admin.add_view(CostCenterAdminModel(models.CostCenter, db.session, category='Finance'))

from app.lisedu import lisedu as lis_blueprint

app.register_blueprint(lis_blueprint, url_prefix='/lis')

from app.eduqa import eduqa_bp as eduqa_blueprint
from app.eduqa.models import *

app.register_blueprint(eduqa_blueprint, url_prefix='/eduqa')
admin.add_view(ModelView(EduQACourseCategory, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACourse, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAProgram, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACurriculum, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACurriculumnRevision, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAInstructorRole, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACourseSessionDetailRoleItem, db.session, category='EduQA'))
admin.add_view(ModelView(EduQACourseLearningOutcome, db.session, category='EduQA'))
admin.add_view(ModelView(EduQALearningActivity, db.session, category='EduQA'))
admin.add_view(ModelView(EduQALearningActivityAssessment, db.session, category='EduQA'))
admin.add_view(ModelView(EduQALearningActivityAssessmentPair, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAGradingScheme, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAGradingSchemeItem, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAGradingSchemeItemCriteria, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAPLO, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAInstructorEvaluationCategory, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAInstructorEvaluationItem, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAInstructorEvaluationChoice, db.session, category='EduQA'))
admin.add_view(ModelView(EduQAInstructorEvaluationResult, db.session, category='EduQA'))

from app.chemdb import chemdbbp as chemdb_blueprint
from app.chemdb.models import *

app.register_blueprint(chemdb_blueprint, url_prefix='/chemdb')

from app.comhealth import comhealth as comhealth_blueprint
from app.comhealth.models import *

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
            'validators': [InputRequired()]
        },
        'code': {
            'label': 'Test code',
            'validators': [InputRequired()]
        }
    }


class ComHealthContainerModelView(ModelView):
    form_args = {
        'name': {
            'validators': [InputRequired()]
        }
    }
    form_choices = {
        'group': [('basic', u'พื้นฐาน'), ('extra', u'เพิ่ม')]
    }

    form_columns = ['name', 'detail', 'desc', 'volume', 'group']


class ComHealthDepartmentModelView(ModelView):
    form_args = {
        'name': {
            'validators': [InputRequired()]
        }
    }


admin.add_view(ComHealthTestModelView(ComHealthTest, db.session, category='Com Health'))
admin.add_view(ComHealthContainerModelView(ComHealthContainer, db.session, category='Com Health'))
admin.add_view(ComHealthDepartmentModelView(ComHealthDepartment, db.session, category='Com Health'))

from app.pdpa import pdpa_blueprint

app.register_blueprint(pdpa_blueprint, url_prefix='/pdpa')

from app.pdpa.models import *

admin.add_view(ModelView(PDPARequest, db.session, category='PDPA'))
admin.add_view(ModelView(PDPARequestType, db.session, category='PDPA'))


class CoreServiceModelView(ModelView):
    form_excluded_columns = ('created_at', 'updated_at')


admin.add_view(CoreServiceModelView(CoreService, db.session, category='PDPA'))

from app.smartclass_scheduler import smartclass_scheduler_blueprint

app.register_blueprint(smartclass_scheduler_blueprint, url_prefix='/smartclass')
from app.smartclass_scheduler.models import (SmartClassOnlineAccount,
                                             SmartClassResourceType,
                                             SmartClassOnlineAccountEvent)

admin.add_view(ModelView(SmartClassOnlineAccount, db.session, category='Smartclass'))
admin.add_view(ModelView(SmartClassResourceType, db.session, category='Smartclass'))
admin.add_view(ModelView(SmartClassOnlineAccountEvent, db.session, category='Smartclass'))

from app.comhealth.views import CustomerEmploymentTypeUploadView

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

from app.health_service_scheduler.apis import *

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

from app.doc_circulation.models import *
from app.doc_circulation import docbp as doc_blueprint

app.register_blueprint(doc_blueprint, url_prefix='/docs')

admin.add_view(ModelView(DocRound, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocRoundOrg, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocRoundOrgReach, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocCategory, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocDocument, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocDocumentReach, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocReceiveRecord, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocSendOut, db.session, category='Docs Circulation'))
admin.add_view(ModelView(DocOrg, db.session, category='Docs Circulation'))

from app.data_blueprint import data_bp as data_blueprint

app.register_blueprint(data_blueprint, url_prefix='/data-blueprint')

from app.scb_payment_service import scb_payment as scb_payment_blueprint

app.register_blueprint(scb_payment_blueprint)

from app.scb_payment_service.models import *

admin.add_view(ModelView(ScbPaymentServiceApiClientAccount, db.session, category='SCB Payment Service'))
admin.add_view(ModelView(ScbPaymentRecord, db.session, category='SCB Payment Service'))

from app.meeting_planner import meeting_planner as meeting_planner_blueprint

app.register_blueprint(meeting_planner_blueprint)

from app.meeting_planner.models import *

admin.add_view(ModelView(MeetingEvent, db.session, category='Meeting'))
admin.add_view(ModelView(MeetingInvitation, db.session, category='Meeting'))
admin.add_view(ModelView(MeetingPoll, db.session, category='Meeting'))
admin.add_view(ModelView(MeetingPollItem, db.session, category='Meeting'))
admin.add_view(ModelView(MeetingPollItemParticipant, db.session, category='Meeting'))
admin.add_views(ModelView(MeetingPollResult, db.session, category='Meeting'))
from app.PA import pa_blueprint

app.register_blueprint(pa_blueprint)

from app.PA.models import *

admin.add_view(ModelView(PARound, db.session, category='PA'))
admin.add_view(ModelView(PAAgreement, db.session, category='PA'))
admin.add_view(ModelView(PAKPI, db.session, category='PA'))
admin.add_view(ModelView(PAKPIItem, db.session, category='PA'))
admin.add_view(ModelView(PALevel, db.session, category='PA'))
admin.add_view(ModelView(PACommittee, db.session, category='PA'))
admin.add_view(ModelView(PAItem, db.session, category='PA'))
admin.add_view(ModelView(PAItemCategory, db.session, category='PA'))
admin.add_view(ModelView(PAKPIJobPosition, db.session, category='PA'))
admin.add_view(ModelView(PAKPIItemJobPosition, db.session, category='PA'))
admin.add_view(ModelView(PARequest, db.session, category='PA'))
admin.add_view(ModelView(PAScoreSheet, db.session, category='PA'))
admin.add_view(ModelView(PAScoreSheetItem, db.session, category='PA'))
admin.add_view(ModelView(PAApprovedScoreSheet, db.session, category='PA'))
admin.add_view(ModelView(PACoreCompetencyItem, db.session, category='PA'))
admin.add_view(ModelView(PACoreCompetencyScoreItem, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetency, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyLevel, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyIndicator, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyCriteria, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyRound, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyEvaluation, db.session, category='PA'))
admin.add_view(ModelView(PAFunctionalCompetencyEvaluationIndicator, db.session, category='PA'))

admin.add_view(ModelView(IDP, db.session, category='IDP'))
admin.add_view(ModelView(IDPRequest, db.session, category='IDP'))
admin.add_view(ModelView(IDPItem, db.session, category='IDP'))
admin.add_view(ModelView(IDPLearningType, db.session, category='IDP'))
admin.add_view(ModelView(IDPLearningPlan, db.session, category='IDP'))

from app.models import Dataset, DataFile

admin.add_view(ModelView(Dataset, db.session, category='Data'))
admin.add_view(ModelView(DataFile, db.session, category='Data'))

from app.e_sign_api.models import CertificateFile
from app.e_sign_api import esign as esign_blueprint

admin.add_views(ModelView(CertificateFile, db.session, category='E-sign'))

app.register_blueprint(esign_blueprint)


# Commands

@app.cli.command()
def populatedb():
    # database.load_orgs()
    # database.load_strategy()
    # database.load_tactics()
    # database.load_themes()
    database.load_activities()


from app.database import load_students


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


@dbutils.command('import-procurement-data')
def import_procurement_data():
    def convert_date(d, format='%d.%m.%Y'):
        try:
            new_date = pandas.to_datetime(d, format=format)
        except ValueError:
            new_date = None
        return new_date

    def convert_number(d):
        if isinstance(d, int) or isinstance(d, float):
            return d
        try:
            new_number = float(d.replace(",", "").replace("-", ""))
        except ValueError:
            new_number = None
        return new_number

    sheetid = '165tgZytipxxy5jY2ZOY5EaBJwxt3ZVRDwaBqggqmccY'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wb = gc.open_by_key(sheetid)
    sheet = wb.worksheet("Data")
    df = pandas.DataFrame(sheet.get_all_records())
    df['curr_acq_value'] = df['curr_acq_value'].apply(convert_number)
    df['received_date'] = df['received_date'].apply(convert_date)
    for n, record in enumerate(df.iterrows()):
        if n % 1000 == 0:
            print(n)
        idx, row = record
        item = ProcurementDetail.query.filter_by(procurement_no=str(row['procurement_no'])).first()
        if row['purchasing_type_id']:
            purchasing_type = ProcurementPurchasingType.query.filter_by(
                fund=int(str(row['purchasing_type_id'])[0])).first()
        else:
            purchasing_type = None
        if not item:
            item = ProcurementDetail(procurement_no=str(row['procurement_no']))
            procurement_record = ProcurementRecord(item=item)
            db.session.add(procurement_record)
        item.cost_center = row['cost_center']
        item.erp_code = row['erp_code']
        item.sub_number = row['sub_number']
        item.name = row['name']
        item.curr_acq_value = row['curr_acq_value']
        item.price = row['price']
        item.available = row['available']
        item.budget_year = row['budget_year']
        item.received_date = row['received_date'] if not pd.isna(row['received_date']) else None
        item.purchasing_type = purchasing_type
        db.session.add(item)
    db.session.commit()


def initialize_gdrive():
    gauth = GoogleAuth()
    scope = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
    return GoogleDrive(gauth)


@dbutils.command('import-procurement-image')
@click.argument('index')
@click.argument('limit')
def import_procurement_image(index, limit):
    sheetid = '16A6yb_W-GcWRLbpqV-9cAnpqgh7nQsZogsNlzz_73ds'
    print('Authorizing with Google sheet..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("Asset")
    drive = initialize_gdrive()
    img_name = 'temp_image.jpg'
    for n, rec in enumerate(sheet.get_all_records(), start=1):
        if n >= int(index) and n < int(limit) + int(index):
            print(n)
            asset_code = str(rec['AssetCode'])
            item = ProcurementDetail.query.filter_by(procurement_no=asset_code).first()
            if item:
                if not item.image:
                    print(rec['Picture'])
                    query = u"title = '{}'".format(rec['Picture'])
                    for file_list in drive.ListFile({'q': query, 'spaces': 'drive'}):
                        if file_list:
                            print(query)
                            for fi in file_list:
                                fi.GetContentFile(img_name)
                                with open(img_name, "rb") as img_file:
                                    item.image = base64.b64encode(img_file.read())
                                    db.session.add(item)
                                print('The image has been added to item with Asset code={}'.format(item.procurement_no))
                            db.session.commit()
            else:
                print(u'\tItem with Asset code={} not found..'.format(rec['AssetCode']))


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


@dbutils.command('update-used-leave-quota')
def update_leave_used_leave_quota():
    pass


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

from app.database import load_provinces, load_districts, load_subdistricts


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


@app.template_filter('upcoming_polls')
def filter_upcoming_polls(polls):
    return [poll for poll in polls
            if poll.start_vote >= arrow.now('Asia/Bangkok').datetime or poll.close_vote > arrow.now('Asia/Bangkok').datetime]


@app.template_filter('upcoming_meeting_events')
def filter_upcoming_meeting_events(events):
    return [event for event in events
            if event.meeting.start >= arrow.now('Asia/Bangkok').datetime]


@app.template_filter('upcoming_events')
def filter_upcoming_events(events):
    bangkok = timezone('Asia/Bangkok')
    return [event for event in events
            if event.datetime.lower.astimezone(tz)
            >= arrow.now('Asia/Bangkok').datetime]


@app.template_filter('upcoming_pre_register')
def filter_upcoming_pre_register(pre_seminars):
    return [pre_seminar for pre_seminar in pre_seminars
            if pre_seminar.seminar.end_datetime
            >= arrow.now('Asia/Bangkok').datetime]


@app.template_filter('total_hours')
def cal_total_hours(instructor, course_id):
    total_seconds = []
    for session in instructor.sessions.filter_by(course_id=course_id):
        detail = EduQACourseSessionDetail.query.filter_by(session_id=session.id,
                                                          staff_id=instructor.account.id).first()
        if detail:
            factor = detail.factor if detail.factor else 1
            seconds = session.total_seconds * factor
            total_seconds.append(seconds)
        else:
            total_seconds.append(session.total_seconds)
    hours = sum(total_seconds) // 3600
    mins = (sum(total_seconds) // 60) % 60
    return u'{} ชม. {} นาที'.format(hours, mins)


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
        if dt.tzinfo:
            return dt.astimezone(bangkok).strftime(datetime_format)
    else:
        return None


@app.template_filter("localize")
def localize(dt):
    bangkok = timezone('Asia/Bangkok')
    datetime_format = '%d/%m/%Y %X'
    if dt:
        return bangkok.localize(dt)
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


def get_fiscal_date(date):
    if date.month >= 10:
        start_fiscal_date = datetime(date.year, 10, 1)
        end_fiscal_date = datetime(date.year + 1, 9, 30, 23, 59, 59, 0)
    else:
        start_fiscal_date = datetime(date.year - 1, 10, 1)
        end_fiscal_date = datetime(date.year, 9, 30, 23, 59, 59, 0)
    return start_fiscal_date, end_fiscal_date


from datetime import datetime


@dbutils.command('migrate-room-datetime')
def migrate_room_datetime():
    print('Migrating...')
    for event in RoomEvent.query:
        if event.start > event.end:
            print(f'{event.id}')
        else:
            event.datetime = DateTimeRange(lower=event.start.astimezone(bangkok),
                                           upper=event.end.astimezone(bangkok), bounds='[]')
            db.session.add(event)
    db.session.commit()


@dbutils.command('calculate-leave-quota')
@click.argument("date_time")
def calculate_leave_quota(date_time):
    """Calculate used quota for the fiscal year from a given date.

    """
    # date_time = '2022/09/30'
    print('Calculating leave quota from all requests...')
    date_time = datetime.strptime(date_time, '%Y/%m/%d')
    start_fiscal_date, end_fiscal_date = get_fiscal_date(date_time)
    for leave_request in StaffLeaveRequest.query.filter(StaffLeaveRequest.start_datetime >= start_fiscal_date,
                                                        StaffLeaveRequest.end_datetime <= end_fiscal_date,
                                                        StaffLeaveRequest.cancelled_at == None):
        if leave_request.staff.personal_info.retired:
            continue
        personal_info = leave_request.staff.personal_info
        quota = leave_request.quota

        pending_days = personal_info.get_total_pending_leaves_request(quota.id,
                                                                      leave_request.start_datetime,
                                                                      leave_request.end_datetime)
        total_leave_days = personal_info.get_total_leaves(quota.id,
                                                          leave_request.start_datetime,
                                                          leave_request.end_datetime)

        used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=quota.leave_type_id,
                                                         staff=leave_request.staff,
                                                         fiscal_year=end_fiscal_date.year).first()
        if used_quota:
            used_quota.used_days += total_leave_days + pending_days
            used_quota.pending_days = pending_days
        else:
            delta = personal_info.get_employ_period()
            max_cum_quota = personal_info.get_max_cum_quota_per_year(quota)
            # use StaffLeaveRemainQuota until fiscal year of 2022
            last_quota = StaffLeaveRemainQuota.query.filter(and_(
                StaffLeaveRemainQuota.leave_quota_id == quota.id,
                StaffLeaveRemainQuota.year == (start_fiscal_date.year - 1),
                StaffLeaveRemainQuota.staff_account_id == leave_request.staff.id)).first()
            if delta.years > 0:
                if max_cum_quota:
                    if last_quota:
                        last_year_quota = last_quota.last_year_quota
                    else:
                        last_year_quota = 0
                    before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                    quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                else:
                    quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year
            used_quota = StaffLeaveUsedQuota(leave_type_id=quota.leave_type_id,
                                             staff_account_id=leave_request.staff.id,
                                             fiscal_year=end_fiscal_date.year,
                                             used_days=total_leave_days + pending_days,
                                             pending_days=pending_days,
                                             quota_days=quota_limit)
        db.session.add(used_quota)
        db.session.commit()


@dbutils.command('update-cumulative-leave-quota')
@click.argument("year1")
@click.argument("year2")
def update_cumulative_leave_quota(year1, year2):
    """Update cumulative leave quota from the previous year.
    Make sure to run calculate_leave_quota for the year2 prior to running this command.

    """
    print('Running; this could take a moment...')
    for used_quota in StaffLeaveUsedQuota.query.filter(StaffLeaveUsedQuota.fiscal_year == year2):
        last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=used_quota.staff,
                                                              fiscal_year=year1,
                                                              leave_type=used_quota.leave_type).first()
        delta = used_quota.staff.personal_info.get_employ_period()
        quota = StaffLeaveQuota.query.filter_by(employment=used_quota.staff.personal_info.employment,
                                                leave_type=used_quota.leave_type).first()
        max_cum_quota = used_quota.staff.personal_info.get_max_cum_quota_per_year(quota)

        if last_used_quota:
            remaining_days = last_used_quota.quota_days - last_used_quota.used_days
            if delta.years > 0 or delta.months > 5:
                if max_cum_quota:
                    before_cut_max_quota = remaining_days + LEAVE_ANNUAL_QUOTA
                    quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                else:
                    quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year

            used_quota.quota_days = quota_limit

            start_fiscal_date = tz.localize(datetime(int(year1), 10, 1))
            end_fiscal_date = tz.localize(datetime(int(year2), 9, 30))
            used_quota.pending_days = used_quota.staff.personal_info \
                .get_total_pending_leaves_request(quota.id, start_fiscal_date, end_fiscal_date)

        db.session.add(used_quota)
        db.session.commit()


def update_leave_information(current_date, staff_email):
    for type_ in StaffLeaveType.query.all():
        staff = StaffAccount.query.filter_by(email=staff_email).first()
        date_time = datetime.strptime(current_date, '%Y/%m/%d')
        start_fiscal_date, end_fiscal_date = get_fiscal_date(date_time)

        quota = StaffLeaveQuota.query.filter_by(employment=staff.personal_info.employment,
                                                leave_type=type_).first()
        if not quota and not staff.is_retired:
            print(staff.id, staff.email, staff.personal_info.employment, 'Quota not found.')
            return
        pending_days = staff.personal_info.get_total_pending_leaves_request(quota.id,
                                                                            tz.localize(start_fiscal_date),
                                                                            tz.localize(end_fiscal_date))
        total_leave_days = staff.personal_info.get_total_leaves(quota.id, tz.localize(start_fiscal_date),
                                                                tz.localize(end_fiscal_date))
        delta = staff.personal_info.get_employ_period()
        max_cum_quota = staff.personal_info.get_max_cum_quota_per_year(quota)
        last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=staff,
                                                              fiscal_year=end_fiscal_date.year - 1,
                                                              leave_type=type_).first()
        if delta.years > 0:
            if max_cum_quota:
                if last_used_quota:
                    remaining_days = last_used_quota.quota_days - last_used_quota.used_days
                else:
                    remaining_days = max_cum_quota
                before_cut_max_quota = remaining_days + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = quota.max_per_year or quota.first_year
        else:
            if delta.months > 5:
                if date_time.month in [10, 11, 12]:
                    if max_cum_quota:
                        if last_used_quota:
                            remaining_days = last_used_quota.quota_days - last_used_quota.used_days
                        else:
                            remaining_days = max_cum_quota
                        before_cut_max_quota = remaining_days + LEAVE_ANNUAL_QUOTA
                        quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = quota.max_per_year or quota.first_year
                else:
                    quota_limit = quota.first_year
            else:
                quota_limit = quota.first_year if not quota.min_employed_months else 0

        used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=type_.id,
                                                         staff_account_id=staff.id,
                                                         fiscal_year=end_fiscal_date.year,
                                                         ).first()
        if used_quota:
            used_quota.pending_days = pending_days
            used_quota.quota_days = quota_limit
            used_quota.used_days = total_leave_days + pending_days
        else:
            used_quota = StaffLeaveUsedQuota(leave_type_id=type_.id,
                                             staff_account_id=staff.id,
                                             fiscal_year=end_fiscal_date.year,
                                             used_days=total_leave_days + pending_days,
                                             pending_days=pending_days,
                                             quota_days=quota_limit)
        db.session.add(used_quota)
        db.session.commit()
        # print (used_quota.leave_type_id, used_quota.used_days, used_quota.pending_days, used_quota.quota_days)


@dbutils.command('update-staff-leave-info')
@click.argument('staff_email')
@click.argument('currentdate')
def update_staff_leave_info(currentdate, staff_email=None):
    # currentdate format '2022/09/30'
    if staff_email != 'all':
        update_leave_information(currentdate, staff_email)
    else:
        for staff in StaffAccount.query.all():
            if not staff.is_retired:
                update_leave_information(currentdate, staff.email)


@dbutils.command('update-room-event-datetime')
def update_room_event_datetime():
    bkk = timezone('Asia/Bangkok')
    for event in RoomEvent.query:
        if not event.datetime:
            event.datetime = DateTimeRange(lower=event.start.astimezone(bkk),
                                           upper=event.end.astimezone(bkk),
                                           bounds='[]')
            db.session.add(event)
    db.session.commit()


@dbutils.command('import-seminar-data')
def import_seminar_data():
    tz = timezone('Asia/Bangkok')
    sheetid = '1GzNUS14c6dkUNh1Xz5cis1IXlPGtZTlGHgeU_3HS7HQ'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("seminar")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        topic_type = row['topic_type']
        start_date = pandas.to_datetime(row['start_datetime'], format='%d/%m/%Y')
        end_date = pandas.to_datetime(row['end_datetime'], format='%d/%m/%Y')
        location = row['location']
        topic = row['topic']
        if topic:
            seminar = StaffSeminar(
                topic=topic,
                topic_type=topic_type,
                location=location,
                start_datetime=tz.localize(start_date),
                end_datetime=tz.localize(end_date),
                created_at=tz.localize(datetime.today())
            )
            db.session.add(seminar)
        else:
            topic_type = row['topic_type']
            print(u'Cannot save data of topic:{} start date: {} end_date: {}'.format(topic_type, start_date, end_date))
    db.session.commit()


@dbutils.command('import-seminar-attend-data')
def import_seminar_attend_data():
    tz = timezone('Asia/Bangkok')
    sheetid = '1GzNUS14c6dkUNh1Xz5cis1IXlPGtZTlGHgeU_3HS7HQ'
    print('Authorizing with Google..')
    gc = get_credential(json_keyfile)
    wks = gc.open_by_key(sheetid)
    sheet = wks.worksheet("attend")
    df = pandas.DataFrame(sheet.get_all_records())
    for idx, row in df.iterrows():
        staff_account = StaffAccount.query.filter_by(email=row['email']).first()
        seminar = StaffSeminar.query.filter_by(topic=row['seminar']).first()
        role = row['role']
        budget_type = row['budget_type']
        budget = row['budget']
        objective = StaffSeminarObjective.query.filter_by(objective=row['objective']).first()
        mission = StaffSeminarMission.query.filter_by(mission=row['mission']).first()
        start_date = pandas.to_datetime(row['start_date'], format='%d/%m/%Y')
        end_date = pandas.to_datetime(row['end_date'], format='%d/%m/%Y')
        if staff_account:
            attend = StaffSeminarAttend(
                seminar_id=seminar.id,
                staff_account_id=staff_account.id,
                start_datetime=tz.localize(start_date),
                end_datetime=tz.localize(end_date),
                created_at=tz.localize(datetime.today()),
                role=role,
                budget_type=budget_type,
                budget=budget
            )
            db.session.add(attend)
            if objective:
                objective.objective_attends.append(attend)
            if mission:
                mission.mission_attends.append(attend)
        else:
            print(u'Cannot save data of email: {} start date: {}'.format(row['seminar'], start_date))
    db.session.commit()


@dbutils.command('add-pa-head-id')
@click.argument('pa_round_id')
def add_pa_head_id(pa_round_id):
    all_req = PARequest.query.filter_by(for_='ขอรับการประเมิน').all()
    for req in all_req:
        if req.pa.round_id == int(pa_round_id):
            pa = PAAgreement.query.filter_by(id=req.pa_id).first()
            if not pa.head_committee_staff_account_id:
                pa.head_committee_staff_account_id = req.supervisor_id
                db.session.add(req)
                print('save {} head committee {}'.format(req.pa.staff.email, req.supervisor.email))
    db.session.commit()

# from collections import defaultdict, namedtuple
# from flask_wtf.csrf import generate_csrf
# import gspread
# from wtforms import DecimalField, FormField, StringField, BooleanField, TextAreaField, DateField, SelectField, \
#     SelectMultipleField, HiddenField
# from flask_wtf import FlaskForm
#
# FieldTuple = namedtuple('FieldTuple', ['type_', 'class_'])
#
# field_types = {
#     'string': FieldTuple(StringField, 'input'),
#     'text': FieldTuple(TextAreaField, 'textarea'),
#     'number': FieldTuple(DecimalField, 'input'),
#     'boolean': FieldTuple(BooleanField, ''),
#     'date': FieldTuple(DateField, 'input'),
#     'choice': FieldTuple(SelectField, ''),
#     'multichoice': FieldTuple(SelectMultipleField, '')
#   }
#
#
# def create_field_group_form_factory(field_group):
#     class GroupForm(FlaskForm):
#         for field in field_group:
#             _field = field_types[field['fieldType']]
#             _field_label = f"{field['fieldLabel']}"
#             _field_placeholder = f"{field['fieldPlaceHolder']}"
#             if field['fieldType'] == 'choice' or field['fieldType'] =='multichoice':
#                 choices = field['fieldChoice'].split(', ')
#                 vars()[f"{field['fieldName']}"] = _field.type_(label=_field_label,
#                                                                choices=((c, c) for c in choices),
#                                                                render_kw={'class':_field.class_,
#                                                                           'placeholder':_field_placeholder})
#             else:
#                 vars()[f"{field['fieldName']}"] = _field.type_(label=_field_label,
#                                                                render_kw={'class': _field.class_,
#                                                                           'placeholder': _field_placeholder})
#     return GroupForm
#
#
# def create_request_form(table):
#     field_groups = defaultdict(list)
#     for idx,row in table.iterrows():
#         field_groups[row['fieldGroup']].append(row)
#
#     class MainForm(FlaskForm):
#         for group_name, field_group in field_groups.items():
#             vars()[f"{group_name}"] = FormField(create_field_group_form_factory(field_group))
#         vars()["csrf_token"] = HiddenField(default=generate_csrf())
#     return MainForm
#
#
# @app.route('/academic-service-form', methods=['GET'])
# def get_request_form():
#     sheetid = '1EHp31acE3N1NP5gjKgY-9uBajL1FkQe7CCrAu-TKep4'
#     print('Authorizing with Google..')
#     gc = get_credential(json_keyfile)
#     wks = gc.open_by_key(sheetid)
#     sheet = wks.worksheet("information")
#     df = pandas.DataFrame(sheet.get_all_records())
#     form = create_request_form(df)()
#     template = ''
#     for f in form:
#         template += str(f)
#     return template
#
#
# @app.route('/academic-service-request', methods=['GET'])
# def create_service_request():
#
#     return render_template('academic_services/request_form.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")
