from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import FieldList, FormField

from app.software_request.models import *
from wtforms_alchemy import model_form_factory, QuerySelectField
BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class SoftwareRequestTimelineForm(ModelForm):
    class Meta:
        model = SoftwareRequestTimeline

    admin = QuerySelectField('ผู้รับผิดชอบ', query_factory=lambda: StaffAccount.get_active_accounts(), allow_blank=True,
                             blank_text='กรุณาเลือกผู้รับผิดชอบ', get_label='fullname')


def create_request_form(status):
    class SoftwareRequestDetailForm(ModelForm):
        class Meta:
            model = SoftwareRequestDetail

        file_upload = FileField('File Upload')
        system = QuerySelectField('ระบบที่ต้องการปรับปรุง', query_factory=lambda: SoftwareRequestSystem.query.all(), allow_blank=True,
                                  blank_text='กรุณาเลือกระบบี่ต้องการปรับปรุง', get_label='system')
        work_process = QuerySelectField('กระบวนการทำงาน/โครงการที่เกี่ยวข้อง', query_factory=lambda: Process.query.all(), allow_blank=True,
                                blank_text='กรุณาเลือกกระบวนการทำงาน/โครงการที่เกี่ยวข้อง', get_label='name')
        if status:
            timelines = FieldList(FormField(SoftwareRequestTimelineForm, default=SoftwareRequestTimeline), min_entries=1)
    return SoftwareRequestDetailForm