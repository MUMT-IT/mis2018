from flask_wtf import FlaskForm
from flask_wtf.file import FileField
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
    work_process = QuerySelectField('กระบวนการทำงาน/โครงการที่เกี่ยวข้อง', query_factory=lambda: Process.query.all(), allow_blank=True,
                            blank_text='กรุณาเลือกกระบวนการทำงาน/โครงการที่เกี่ยวข้อง', get_label='name')