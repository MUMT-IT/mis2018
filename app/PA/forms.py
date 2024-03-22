from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, FloatField, SelectField, TextAreaField, widgets
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField
from app.PA.models import *
from app.staff.models import StaffJobPosition
from app.main import db
from ..models import Org, StaffAccount

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
    kpi_items_ = FieldList(SelectField(validate_choice=False), min_entries=0)


class PACommitteeForm(ModelForm):
    class Meta:
        model = PACommittee

    round = QuerySelectField('รอบการประเมิน',
                             get_label='desc',
                             allow_blank=False,
                             query_factory=lambda: PARound.query.all())

    org = QuerySelectField('ประเมินหน่วยงาน(หากประเมินรายบุคคล เลือกทีมบริหารและหัวหน้างาน)',
                           get_label='name',
                           allow_blank=False,
                           query_factory=lambda: Org.query.all())

    staff = QuerySelectMultipleField('ผู้ประเมิน',
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


class IDPItemForm(ModelForm):
    class Meta:
        model = IDPItem

    learning_type = QuerySelectField(
                             allow_blank=False,
                             query_factory=lambda: IDPLearningType.query.all())


class IDPItemReviewForm(ModelForm):
    class Meta:
        model = IDPItem
        only = ['approver_comment']


class IDPForm(ModelForm):
    class Meta:
        model = IDP
        only = ['approver_review']
    idp_item = FieldList(FormField(IDPItemReviewForm, default=IDPItem))


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
                                      query_factory=lambda: PAFunctionalCompetency.query.filter_by(
                                          job_position_id=job_position_id).all())

        level = QuerySelectField('ระดับ',
                                 get_label='order',
                                 allow_blank=False,
                                 query_factory=lambda: PAFunctionalCompetencyLevel.query.all())

    return PAFCIndicatorForm


class PAFCIndicatorForm(ModelForm):
    class Meta:
        model = PAFunctionalCompetencyIndicator


class PAFunctionalCompetencyEvaluationIndicatorForm(ModelForm):
    class Meta:
        model = PAFunctionalCompetencyEvaluationIndicator

    criterion = QuerySelectField(query_factory=lambda: PAFunctionalCompetencyCriteria.query.all(),
                                 widget=widgets.ListWidget(prefix_label=False),
                                 option_widget=widgets.RadioInput())


class PAFunctionalCompetencyEvaluationForm(ModelForm):
    class Meta:
        model = PAFunctionalCompetencyEvaluation

    evaluation_eva_indicator = FieldList(FormField(PAFunctionalCompetencyEvaluationIndicatorForm,
                                                   default=PAFunctionalCompetencyEvaluationIndicator))