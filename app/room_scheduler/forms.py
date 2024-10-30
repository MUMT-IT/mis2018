from datetime import datetime

from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import Field
from wtforms.widgets import TextInput
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.room_scheduler.models import *
from app.staff.models import StaffAccount, StaffGroupDetail

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class DateTimePickerField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.strftime('%d-%m-%Y %H:%M:%S')
        else:
            return ''

    def process_formdata(self, value):
        if value[0]:
            self.data = datetime.strptime(value[0], '%d-%m-%Y %H:%M:%S')
        else:
            self.data = None


class RoomEventForm(ModelForm):
    class Meta:
        model = RoomEvent

    start = DateTimePickerField('เริ่มต้น')
    end = DateTimePickerField('สิ้นสุด')

    category = QuerySelectField(query_factory=lambda: EventCategory.query.all())
    participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.query.filter(
                                 StaffAccount.personal_info.has(retired=False)).all(), get_label='fullname')