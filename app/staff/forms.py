# -*- coding:utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import widgets, FieldList, FormField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from .models import (StaffSeminar, StaffSeminarMission, StaffSeminarAttend, StaffSeminarObjective, StaffLeaveApprover
, StaffAccount, StaffGroupPosition, StaffGroupDetail, StaffGroupAssociation)
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
        missions = QuerySelectMultipleField(u'เพื่อพัฒนาในด้าน', get_label='mission',
                                              query_factory=lambda: StaffSeminarMission.query.all(),
                                              widget=widgets.ListWidget(prefix_label=False),
                                              option_widget=widgets.CheckboxInput()
                                              )
        approver = QuerySelectField(u'ผู้บังคับบัญชา',
                                    get_label='approver_name',
                                    allow_blank=True,
                                    blank_text=u'กรุณาเลือกผู้อนุมัติ',
                                    query_factory=lambda: StaffLeaveApprover.
                                    query.filter_by(staff_account_id=current_user.id).all())

    return StaffSeminarAttendForm


class QuerySelectFieldAppendable(QuerySelectField):
    def __init__(self, label, validators=None, **kwargs):
        super(QuerySelectFieldAppendable, self).__init__(label, validators, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            if self.allow_blank and valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                value = valuelist[0]
                if not value.isdigit():
                    position = StaffGroupPosition.query.filter_by(position=value).first()
                    if not position:
                        position = StaffGroupPosition(position=value)
                        db.session.add(position)
                        db.session.commit()
                    self._formdata = str(position.id)
                else:
                    self._formdata = value


class StaffPositionForm(ModelForm):
    class Meta:
        model = StaffGroupAssociation

    staff = QuerySelectField('ชื่อ', query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname',
                             allow_blank=True, blank_text='กรุณาเลือกชื่อ')
    position = QuerySelectFieldAppendable('ตำแหน่ง', query_factory=lambda: StaffGroupPosition.query.all(),
                                allow_blank=True, blank_text='กรุณาเลือกตำแหน่ง', get_label='position')


class StaffGroupDetailForm(ModelForm):
    class Meta:
        model = StaffGroupDetail

    group_members = FieldList(FormField(StaffPositionForm, default=StaffGroupAssociation), min_entries=0)