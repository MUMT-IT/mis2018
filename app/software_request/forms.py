from sqlalchemy import or_
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import FieldList, FormField
from flask_login import current_user
from app.software_request.models import *
from wtforms_alchemy import model_form_factory, QuerySelectField
BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class SoftwareRequestDetailForm(ModelForm):
    class Meta:
        model = SoftwareRequestDetail

    file_upload = FileField('File Upload')
    system = QuerySelectField('ระบบที่ต้องการปรับปรุง', query_factory=lambda: SoftwareRequestSystem.query.all(), allow_blank=True,
                              blank_text='กรุณาเลือกระบบี่ต้องการปรับปรุง', get_label='system')
    work_process = QuerySelectField('กระบวนการทำงาน/โครงการที่เกี่ยวข้อง', allow_blank=True, get_label='name',
                                    query_factory=lambda: Process.query.filter(or_(Process.staff.contains(current_user),
                                                                                   Process.staff.any(StaffAccount.personal_info.has(org=current_user.personal_info.org)))),
                                    blank_text='กรุณาเลือกกระบวนการทำงาน/โครงการที่เกี่ยวข้อง')


class SoftwareRequestTimelineForm(ModelForm):
    class Meta:
        model = SoftwareRequestTimeline

    admin = QuerySelectField('ผู้รับผิดชอบ', query_factory=lambda: StaffAccount.get_it_unit(), allow_blank=True,
                             blank_text='กรุณาเลือกผู้รับผิดชอบ', get_label='fullname')