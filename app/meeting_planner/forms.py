from flask_wtf import FlaskForm
from wtforms import FieldList, FormField
from wtforms.validators import Optional
from wtforms_alchemy import model_form_factory, QuerySelectField

from app.main import RoomEvent, RoomResource
from app.meeting_planner.models import *

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RoomEventForm(ModelForm):
    class Meta:
        model = RoomEvent
        field_args = {
            'start': {'validators': [Optional()]},
            'end': {'validators': [Optional()]},
            'title': {'validators': [Optional()]}
        }
    room = QuerySelectField('ห้อง', query_factory=lambda: RoomResource.query.all(),
                            allow_blank=True, blank_text='กรุณาเลือกห้อง')


class MeetingEventForm(ModelForm):
    class Meta:
        model = MeetingEvent
        exclude = ['updated_at', 'created_at', 'cancelled_at']
    meeting_events = FieldList(FormField(RoomEventForm, default=RoomEvent), min_entries=0)
