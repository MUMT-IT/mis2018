# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm
from wtforms import widgets, SelectField
from wtforms.validators import DataRequired
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.models import Mission, Org, CoreService, Process, Data, KPI, Dataset, ROPA, DataSubject
from app.main import db
from app.staff.models import StaffAccount, StaffPersonalInfo

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class CoreServiceForm(ModelForm):
    class Meta:
        model = CoreService
        only = ['service']
    mission = QuerySelectField(u'พันธกิจ', query_factory=lambda: Mission.query.all(),
                                get_label='name', blank_text='Select mission..', allow_blank=False)
    data = QuerySelectMultipleField(u'ข้อมูลที่ใช้', get_label='name',
                                     query_factory=lambda: Data.query.all(),
                                     widget=widgets.ListWidget(prefix_label=False),
                                     option_widget=widgets.CheckboxInput())


class DataForm(ModelForm):
    class Meta:
        model = Data
        only = ['name']
    core_services = QuerySelectMultipleField(u'บริการที่ใช้ข้อมูลนี้', get_label='service',
                                     query_factory=lambda: CoreService.query.all(),
                                     widget=widgets.ListWidget(prefix_label=False),
                                     option_widget=widgets.CheckboxInput())
    processes = QuerySelectMultipleField(u'กระบวนการที่ใช้ข้อมูลนี้', get_label='name',
                                     query_factory=lambda: Process.query.all(),
                                     widget=widgets.ListWidget(prefix_label=False),
                                     option_widget=widgets.CheckboxInput())


class ProcessForm(ModelForm):
    class Meta:
        model = Process
        only = ['name', 'category']
    org = QuerySelectField(u'หน่วยงาน', query_factory=lambda: Org.query.all(),
                                get_label='name', blank_text='Select organization..', allow_blank=False)
    data = QuerySelectMultipleField(u'ข้อมูลที่ใช้', get_label='name',
                                     query_factory=lambda: Data.query.all(),
                                     widget=widgets.ListWidget(prefix_label=False),
                                     option_widget=widgets.CheckboxInput())
    parent = QuerySelectField(u'กระบวนการหลัก', get_label='name',
                              allow_blank=True,
                              blank_text='ระบุกระบวนการหลัก (ถ้ามี)',
                              query_factory=lambda: Process.query.filter_by(parent_id=None).all())


class KPIForm(ModelForm):
    class Meta:
        model = KPI
        only = ['name', 'refno', 'frequency', 'unit', 'source', 'intent',
                'available', 'availability', 'formula', 'note', 'keeper']

    keeper = SelectField(u'เก็บโดย')

    # core_services = QuerySelectMultipleField(u'บริการที่เกี่ยวข้อง', get_label='service',
                                     # query_factory=lambda: CoreService.query.all(),
                                     # widget=widgets.ListWidget(prefix_label=False),
                                     # option_widget=widgets.CheckboxInput())
    # processes = QuerySelectMultipleField(u'กระบวนการที่เกี่ยวข้อง', get_label='name',
                                     # query_factory=lambda: Process.query.all(),
                                     # widget=widgets.ListWidget(prefix_label=False),
                                     # option_widget=widgets.CheckboxInput())


class KPITargetForm(ModelForm):
    class Meta:
        model = KPI
        only = ['target', 'target_source', 'target_setter', 'target_account', 'target_reporter']
    target_account = SelectField(u'ผู้รับผิดชอบหลัก')
    target_reporter = SelectField(u'ผู้รายงานเป้าหมาย')
    target_setter = SelectField(u'ผู้ตั้งเป้าหมาย')


class KPIReportForm(ModelForm):
    class Meta:
        model = KPI
        only = ['account', 'reporter', 'consult', 'informed', 'reportlink',
                'pfm_account', 'pfm_responsible', 'pfm_consult', 'pfm_informed']

    account = SelectField(u'ผู้รับผิดชอบ')
    pfm_account = SelectField(u'ผู้รับดูแลประสิทธิภาพตัวชี้วัด')
    pfm_responsible = SelectField(u'ผู้รับผิดชอบประสิทธิภาพตัวชี้วัด')
    pfm_consult = SelectField(u'ที่ปรึกษาประสิทธิภาพตัวชี้วัด')
    pfm_informed = SelectField(u'ผู้รับรายงานเรื่องประสิทธิภาพตัวชี้วัด')
    reporter = SelectField(u'ผู้รายงาน')
    consult = SelectField(u'ที่ปรึกษา')
    informed = SelectField(u'ผู้รับรายงานหลัก')


class QuerySelectEmailField(QuerySelectField):
    def _get_object_list(self):
        if self._object_list is None:
            query = (
                self.query if self.query is not None
                else self.query_factory()
            )
            self._object_list = list(
                ((obj.email), obj) for obj in query
            )
        return self._object_list


class KPIModalForm(ModelForm):
    class Meta:
        model = KPI
        only = ['name', 'refno', 'frequency', 'unit', 'formula', 'source', 'account', 'keeper', 'target']

    account = QuerySelectEmailField(u'ผู้รับผิดชอบ',
                                    query_factory=lambda: StaffAccount.query.join(StaffPersonalInfo).all(),
                                    get_label='fullname')
    keeper = QuerySelectEmailField(u'ผู้เก็บข้อมูล',
                                   query_factory=lambda: StaffAccount.query.join(StaffPersonalInfo).all(),
                                   get_label='fullname')


def createDatasetForm(data_id):
    data = Data.query.get(data_id)
    class DatasetForm(ModelForm):
        class Meta:
            model = Dataset
            only = ['reference', 'desc', 'source_url', 'sensitive', 'name', 'personal']
        processes = QuerySelectMultipleField(u'กระบวนการที่เกี่ยวข้อง', get_label='name',
                                         query_factory=lambda: data.processes,
                                         widget=widgets.ListWidget(prefix_label=False),
                                         option_widget=widgets.CheckboxInput())
        core_services = QuerySelectMultipleField(u'บริการที่เกี่ยวข้อง', get_label='service',
                                         query_factory=lambda: data.core_services,
                                         widget=widgets.ListWidget(prefix_label=False),
                                         option_widget=widgets.CheckboxInput())
    return DatasetForm


class ROPAForm(ModelForm):
    class Meta:
        model = ROPA
    subjects = QuerySelectMultipleField(u'เจ้าของข้อมูล', get_label='subject',
                                             query_factory=lambda: DataSubject.query.all(),
                                             widget=widgets.ListWidget(prefix_label=False),
                                             option_widget=widgets.CheckboxInput())


class DataSubjectForm(ModelForm):
    class Meta:
        model = DataSubject

