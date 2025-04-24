import pytz
from flask_wtf import FlaskForm
from wtforms import FieldList, FormField
from wtforms.validators import Optional
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField

from app.main import RoomEvent, RoomResource
from app.meeting_planner.models import *

local_th = pytz.timezone('Asia/Bangkok')

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


def create_new_meeting(poll_id=None):
    if poll_id:
        poll = MeetingPoll.query.get(poll_id)

    class MeetingEventForm(ModelForm):
        class Meta:
            model = MeetingEvent
            exclude = ['updated_at', 'created_at', 'cancelled_at']

        meeting_events = FieldList(FormField(RoomEventForm, default=RoomEvent), min_entries=0)
        agendas = FieldList(FormField(MeetingAgendaForm, default=MeetingAgenda), min_entries=0)
        if poll_id:
            participant = QuerySelectMultipleField(query_factory=lambda: poll.participants, get_label='fullname')
    return MeetingEventForm


class MeetingPollItemForm(ModelForm):
    class Meta:
        model = MeetingPollItem


def create_meeting_poll_form(poll_id=None):
    class MeetingPollForm(ModelForm):
        class Meta:
            model = MeetingPoll
            exclude = ['start_vote']
        if not poll_id:
            poll_items = FieldList(FormField(MeetingPollItemForm, default=MeetingPollItem), min_entries=1)
        participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(),
                                            get_label='fullname')
    return MeetingPollForm


class MeetingPollItemParticipant(ModelForm):
    class Meta:
        model = MeetingPollItemParticipant


def format_datetime(item):
    start_time = item.start.astimezone(local_th)
    end_time = item.end.astimezone(local_th)
    return f'{start_time.strftime("%d/%m/%Y %H:%M:%S")} - {end_time.strftime("%d/%m/%Y %H:%M:%S")}'


def create_meeting_poll_result_form(poll_id):
    class MeetingPollResultForm(ModelForm):
        class Meta:
            model = MeetingPollResult
        item = QuerySelectField('วัน-เวลาประชุม', query_factory=lambda: MeetingPollItem.query.filter_by(poll_id=poll_id),
                                allow_blank=True, blank_text='กรุณาเลือกวัน-เวลา', get_label=format_datetime)
    return MeetingPollResultForm
