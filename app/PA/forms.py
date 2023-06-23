from flask_wtf import FlaskForm
from .models import PACommittee, PARound, PARequest
from wtforms import FieldList, FormField, FloatField, SelectField, TextAreaField, widgets
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.PA.models import *
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
                             allow_blank=False,
                             query_factory=lambda: PARound.query.all())

    org = QuerySelectField('หน่วยงาน',
                           get_label='name',
                           allow_blank=False,
                           query_factory=lambda: Org.query.all())

    staff = QuerySelectField('ผู้ประเมิน',
                             get_label='fullname',
                             allow_blank=False,
                             query_factory=lambda: StaffAccount.query.filter(
                                 StaffAccount.personal_info.has(retired=False)).all())


class PARequestForm(ModelForm):
    class Meta:
        model = PARequest


def create_rate_performance_form(kpi_id):
    class PAScoreSheetItemForm(ModelForm):
        class Meta:
            model = PAScoreSheet

        kpi_item = QuerySelectField('เกณฑ์',
                                    allow_blank=False,
                                    query_factory=lambda: PAKPIItem.query.filter_by(kpi_id=kpi_id).all())

    return PAScoreSheetItemForm
