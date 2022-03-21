# -*- coding:utf-8 -*-
from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.models import Mission, Org, CoreService, Process, Data, KPI, Dataset


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



class KPIForm(ModelForm):
    class Meta:
        model = KPI
        only = ['name', 'refno', 'frequency', 'unit', 'source', 'intent',
                'available', 'availability', 'formula', 'note', 'keeper']
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


class KPIReportForm(ModelForm):
    class Meta:
        model = KPI
        only = ['account', 'reporter', 'consult', 'informed', 'reportlink',
                'pfm_account', 'pfm_responsible', 'pfm_consult', 'pfm_informed']


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

