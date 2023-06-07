# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import widgets
from wtforms.validators import DataRequired
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from .models import StaffSeminar, StaffSeminarMission, StaffSeminarAttend, StaffSeminarObjective, StaffLeaveApprover
from app.main import db

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class StaffSeminarForm(ModelForm):
    class Meta:
        model = StaffSeminar


def create_seminar_attend_form(current_user):
    class StaffSeminarAttendForm(ModelForm):
        class Meta:
            model = StaffSeminarAttend

        objectives = QuerySelectMultipleField(u'ดำเนินการภายใต้', get_label='objective',
                                              query_factory=lambda: StaffSeminarObjective.query.all(),
                                              widget=widgets.ListWidget(prefix_label=False),
                                              option_widget=widgets.CheckboxInput()
                                              )
        missions = QuerySelectMultipleField(u'รายละเอียดการเข้าร่วม ดำเนินการภายใต้', get_label='mission',
                                              query_factory=lambda: StaffSeminarMission.query.all(),
                                              widget=widgets.ListWidget(prefix_label=False),
                                              option_widget=widgets.CheckboxInput()
                                              )
        approver = QuerySelectField(u'ผู้บังคับบัญชา',
                                    get_label='approver_name',
                                    allow_blank=True,
                                    blank_text=u'กรุณาเลือกผู้อนุมัติ',
                                    query_factory=lambda: StaffLeaveApprover.\
                                    query.filter_by(staff_account_id=current_user.id).all())

    return StaffSeminarAttendForm
