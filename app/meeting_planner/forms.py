from flask_wtf import FlaskForm
from wtforms import FieldList, FormField
from wtforms.validators import Optional
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField

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


class MeetingAgendaNoteForm(ModelForm):
    class Meta:
        model = MeetingAgendaNote


class MeetingAgendaForm(ModelForm):
    class Meta:
        model = MeetingAgenda


class MeetingEventForm(ModelForm):
    class Meta:
        model = MeetingEvent
        exclude = ['updated_at', 'created_at', 'cancelled_at']    #

    meeting_events = FieldList(FormField(RoomEventForm, default=RoomEvent), min_entries=0)
    agendas = FieldList(FormField(MeetingAgendaForm, default=MeetingAgenda), min_entries=0)


class MeetingPollItemForm(ModelForm):
    class Meta:
        model = MeetingPollItem


class MeetingPollForm(ModelForm):
    class Meta:
        model = MeetingPoll

    poll_items = FieldList(FormField(MeetingPollItemForm, default=MeetingPollItem), min_entries=0)
    participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(), get_label='fullname')
