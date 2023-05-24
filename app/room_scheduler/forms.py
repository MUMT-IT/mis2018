from wtforms.validators import DataRequired, ValidationError

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.room_scheduler.models import *
from app.staff.models import StaffAccount

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RoomEventForm(ModelForm):
    class Meta:
        model = RoomEvent
        datetime_format = '%d-%m-%Y %H:%M:%S'

    category = QuerySelectField(query_factory=lambda: EventCategory.query.all())
    participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(),
                                            get_label='fullname')
