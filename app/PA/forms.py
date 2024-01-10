from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, FloatField, SelectField, TextAreaField
from wtforms_alchemy import model_form_factory, QuerySelectField
from sqlalchemy import and_
from app.PA.models import *
from app.staff.models import StaffJobPosition
from app.main import db
from ..models import Org, StaffAccount, KPI
from flask_login import current_user

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class PAKPIItemForm(ModelForm):
    class Meta:
        model = PAKPIItem

    level = QuerySelectField(query_factory=lambda: PALevel.query.all(),
                             get_label='level',
                             label=u'เกณฑ์การประเมิน',
                             blank_text='กรุณาเลือกเกณฑ์การประเมิน..', allow_blank=True)


class PAKPIForm(ModelForm):
    class Meta:
        model = PAKPI

    pa_kpi_items = FieldList(FormField(PAKPIItemForm, default=PAKPIItem), min_entries=5)


class KPIitemSelectForm(FlaskForm):
    item = QuerySelectField(allow_blank=True, blank_text='กำหนดเป้าหมาย')


class PAKPIJobPositionForm(ModelForm):
    class Meta:
        model = PAKPIJobPosition

    job_position = QuerySelectField('ตำแหน่ง',
                             get_label='th_title',
                             allow_blank=False,
                             query_factory=lambda: StaffJobPosition.query.all())


class PAKPIItemJobPositionForm(ModelForm):
    class Meta:
        model = PAKPIItemJobPosition

    level = QuerySelectField(query_factory=lambda: PALevel.query.all(),
                                 get_label='level',
                                 label=u'เกณฑ์การประเมิน')


class PAItemForm(FlaskForm):
    task = TextAreaField('ภาระงาน')
    percentage = FloatField('ร้อยละ')
    report = TextAreaField('ผลการดำเนินการ')
    category = QuerySelectField('Category',
                                query_factory=lambda: PAItemCategory.query.all(),
                                get_label='category')
    org_kpi = QuerySelectField('Orgkpi', get_label='name', query_factory=lambda: KPI.query.filter_by(target_account=current_user.email))

    kpi_items_ = FieldList(SelectField(validate_choice=False), min_entries=0)


class PACommitteeForm(ModelForm):
    class Meta:
        model = PACommittee

    round = QuerySelectField('รอบการประเมิน',
                             get_label='desc',
                             allow_blank=False,
                             query_factory=lambda: PARound.query.all())

    org = QuerySelectField('ประเมินหน่วยงาน',
                           get_label='name',
                           allow_blank=False,
                           query_factory=lambda: Org.query.all())

    staff = QuerySelectField('ผู้ประเมิน',
                             get_label='fullname',
                             allow_blank=False,
                             query_factory=lambda: StaffAccount.query.filter(
                                 StaffAccount.personal_info.has(retired=False)).all())

    subordinate = QuerySelectField('ผู้รับการประเมิน(ระบุกรณีอยู่ในทีมบริหาร)',
                                   get_label='fullname',
                                   allow_blank=True,
                                   query_factory=lambda: StaffAccount.query.filter(
                                       StaffAccount.personal_info.has(retired=False)).all())



class PARequestForm(ModelForm):
    class Meta:
        model = PARequest


class IDPRequestForm(ModelForm):
    class Meta:
        model = IDPRequest


def create_rate_performance_form(kpi_id):
    class PAScoreSheetItemForm(ModelForm):
        class Meta:
            model = PAScoreSheet

        kpi_item = QuerySelectField('เกณฑ์',
                                    allow_blank=False,
                                    query_factory=lambda: PAKPIItem.query.filter_by(kpi_id=kpi_id).all())

    return PAScoreSheetItemForm


class PAFCForm(ModelForm):
    class Meta:
        model = PAFunctionalCompetency

    job_position = QuerySelectField('ตำแหน่ง',
                             get_label='th_title',
                             allow_blank=False,
                             query_factory=lambda: StaffJobPosition.query.all())


def create_fc_indicator_form(job_position_id):
    class PAFCIndicatorForm(ModelForm):
        class Meta:
            model = PAFunctionalCompetencyIndicator

        functional = QuerySelectField('ทักษะด้าน',
                                    allow_blank=False,
                                    query_factory=lambda: PAFunctionalCompetency.query.filter_by(job_position_id=job_position_id).all())

        level = QuerySelectField('ระดับ',
                                get_label='order',
                                allow_blank=False,
                                query_factory=lambda: PAFunctionalCompetencyLevel.query.all())

    return PAFCIndicatorForm


class PAFCIndicatorForm(ModelForm):
    class Meta:
        model = PAFunctionalCompetencyIndicator
