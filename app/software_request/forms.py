from sqlalchemy import or_
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import TextAreaField, DateField, SelectField
from flask_login import current_user
from wtforms.validators import DataRequired, InputRequired

from app.software_request.models import *
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


def create_request_form(detail_id):
    class SoftwareRequestDetailForm(ModelForm):
        class Meta:
            model = SoftwareRequestDetail

        if detail_id:
            room = QuerySelectField('ห้อง', query_factory=lambda: RoomResource.query.order_by(RoomResource.number.asc()),
                                allow_blank=True, blank_text='กรุณาเลือกห้อง')
            staffs = QuerySelectMultipleField('ผู้รับผิดชอบ', query_factory=lambda: StaffAccount.get_it_unit(),
                                              get_label='fullname')
        else:
            file_upload = FileField('File Upload')
            system = QuerySelectField('ระบบที่ต้องการปรับปรุง', query_factory=lambda: SoftwareRequestSystem.query.all(), allow_blank=True,
                                      blank_text='กรุณาเลือกระบบที่ต้องการปรับปรุง', get_label='system')
            work_process = QuerySelectField('กระบวนการทำงาน', allow_blank=True, get_label='name',
                                            query_factory=lambda: Process.query.filter(or_(Process.staff.contains(current_user),
                                                                                           Process.staff.any(StaffAccount.personal_info.has(org=current_user.personal_info.org)))),
                                            blank_text='กรุณาเลือกกระบวนการทำงาน')
            activity = QuerySelectField('โครงการที่เกี่ยวข้อง', query_factory=lambda: StrategyActivity.query.all(), allow_blank=True,
                                        blank_text='กรุณาเลือกโครงการที่เกี่ยวข้อง', get_label='content')
    return SoftwareRequestDetailForm


def create_timeline_form(detail_id):
    class SoftwareRequestTimelineForm(ModelForm):
        class Meta:
            model = SoftwareRequestTimeline

        task = TextAreaField('Task', validators=[DataRequired()])
        start = DateField('วันที่เริ่มต้น', validators=[DataRequired()])
        estimate = DateField('วันที่คาดว่าจะแล้วเสร็จ', validators=[DataRequired()])
        status = SelectField('status', choices=[('รอดำเนินการ', 'รอดำเนินการ'), ('เสร็จสิ้น', 'เสร็จสิ้น'), ('ยกเลิกการพัฒนา', 'ยกเลิกการพัฒนา')],
                             validators=[DataRequired()])
        issue = QuerySelectField('ปํญหาที่พบ', query_factory=lambda: SoftwareIssues.query.filter_by(software_request_detail_id=detail_id).all(), allow_blank=True,
                                 blank_text='', get_label='issue')
        admin = QuerySelectField('ผู้รับผิดชอบ', query_factory=lambda: StaffAccount.get_it_unit(), get_label='fullname')
    return SoftwareRequestTimelineForm


class QuerySelectFieldAppendable(QuerySelectField):
    def __init__(self, label, validators=None, **kwargs):
        super(QuerySelectFieldAppendable, self).__init__(label, validators, **kwargs)

    def iter_choices(self):
        for value, label, selected in super().iter_choices():
            if value == '__None':
                yield '', label, selected
            else:
                yield value, label, selected

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0] == '':
            valuelist = ['__None']
        if valuelist:
            if self.allow_blank and valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                value = valuelist[0]

                if value.isdigit():
                    phase = SoftwareRequestPhase.query.get(int(value))
                    if phase:
                        self._formdata = value
                    else:
                        phase = SoftwareRequestPhase.query.filter_by(phase=value).first()
                        if not phase:
                            phase = SoftwareRequestPhase(phase=value)
                            db.session.add(phase)
                            db.session.commit()
                        self._formdata = str(phase.id)


class SoftwareRequestIssueForm(ModelForm):
    class Meta:
        model = SoftwareIssues
        only = ['issue', 'label', 'start', 'end']

    status_ = SelectField('Status',
                          default='Draft',
                          choices=[(c,c) for c in ('Draft', 'Working', 'Cancelled', 'Closed')])
    phase = QuerySelectFieldAppendable('Phase', query_factory=lambda: SoftwareRequestPhase.query.all(),
                                       allow_blank=True,
                                       blank_text='กรุณาเลือก Phase',
                                       get_label='phase',
                                       render_kw={'required': True})
    staff = QuerySelectField('ผู้รับผิดชอบ', query_factory=lambda: StaffAccount.get_it_unit(), get_label='fullname')


class QuerySelectFieldRequired(QuerySelectField):
    def iter_choices(self):
        for value, label, selected in super().iter_choices():
            if value == '__None':
                yield '', label, selected
            else:
                yield value, label, selected

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0] == '':
            valuelist = ['__None']
        return super().process_formdata(valuelist)


def create_test_result_form(detail_id, has_note=False):
    class SoftwareRequestTestResultForm(ModelForm):
        class Meta:
            model = SoftwareRequestTestResult
        if not has_note:
            issue = QuerySelectFieldRequired('Requirement',
                                             query_factory=lambda: SoftwareIssues.query.filter(SoftwareIssues.label == 'Request',
                                                                                               SoftwareIssues.accepted_at != None,
                                                                                               SoftwareIssues.software_request_detail_id==detail_id).all(),
                                             allow_blank=True,
                                             blank_text='กรุณาเลือก Requirement',
                                             get_label='issue',
                                             render_kw={'required': True})
    return SoftwareRequestTestResultForm