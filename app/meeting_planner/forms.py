from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import FieldList, FormField
from wtforms.validators import Optional
from wtforms_alchemy import model_form_factory, QuerySelectField, QuerySelectMultipleField

from app.main import RoomEvent, RoomResource
from app.meeting_planner.models import *
from app.staff.models import StaffGroupDetail

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


def get_own_and_public_groups():
    public_groups = set(StaffGroupDetail.query.filter_by(public=True))
    own_groups = set([team.group_detail for team in current_user.teams])
    return public_groups.union(own_groups)


class MeetingPollForm(ModelForm):
    class Meta:
        model = MeetingPoll

    poll_items = FieldList(FormField(MeetingPollItemForm, default=MeetingPollItem), min_entries=0)
    participants = QuerySelectMultipleField(query_factory=lambda: StaffAccount.get_active_accounts(),
                                            get_label='fullname')
    groups = QuerySelectMultipleField('ทีม', query_factory=get_own_and_public_groups, get_label='activity_name')


class MeetingPollItemParticipant(ModelForm):
    class Meta:
        model = MeetingPollItemParticipant


def date_time_query():
    return MeetingPollItem.query


def format_datetime(item):
    return item.date_time.strftime('%d/%m/%Y %H:%M:%S')


class MeetingPollResultForm(ModelForm):
    class Meta:
        model = MeetingPollResult
    item = QuerySelectField('วัน-เวลาการประชุม', query_factory=date_time_query, allow_blank=True,
                            blank_text='กรุณาเลือกวัน-เวลา', get_label=format_datetime)
