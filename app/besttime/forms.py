from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectMultipleField, QuerySelectField
from wtforms_components import DateField
from sqlalchemy.inspection import inspect as sa_inspect

from app.main import db
from wtforms import FieldList, FormField, BooleanField

from app.besttime.models import BestTimePoll, BestTimePollVote, BestTimePollMessage
from app.staff.models import StaffAccount

BaseModelForm = model_form_factory(FlaskForm)

from wtforms import SelectMultipleField
from wtforms.widgets import CheckboxInput, ListWidget


class CheckboxSelectMultipleField(SelectMultipleField):
    """
    A SelectMultipleField that uses checkboxes and ensures correct checked behavior.
    """

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

    def iter_choices(self):
        # Yields (value, label, checked) for each choice
        for value, label in self.choices:
            checked = self.data is not None and value in self.data
            yield (value, label, checked)

    def pre_validate(self, form):
        """
        Validate that all values in data exist in choices.
        Prevents rendering invalid choices as selected.
        """
        if self.data:
            choice_values = [str(val) for val, _ in self.choices]
            for val in self.data:
                if str(val) not in choice_values:
                    raise ValueError(f"'{val}' is not a valid choice")

    def process_data(self, value):
        """
        Ensures data is a list.
        """
        if value is None:
            self.data = []
        else:
            self.data = list(value)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class DateTimeSlotForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    time_slots = CheckboxSelectMultipleField('Time slots')


class MasterDateTimeSlotForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    time_slots = CheckboxSelectMultipleField('Time slots')


class PollForm(ModelForm):
    class Meta:
        model = BestTimePoll

    def populate_obj(self, obj):
        mapper = sa_inspect(obj.__class__)
        model_attrs = set(mapper.attrs.keys())

        # populate only real model-mapped attributes
        for name, field in self._fields.items():
            if name in model_attrs:
                print('populating..', name, obj)
                field.populate_obj(obj, name)

    chairman = QuerySelectField(query_factory=lambda: StaffAccount.query.all(), get_label="fullname")
    invitees = QuerySelectMultipleField(query_factory=lambda: StaffAccount.query.all(),
                                        get_label="fullname",
                                        widget=ListWidget(prefix_label=False),
                                        option_widget=CheckboxInput())
    datetime_slots = FieldList(FormField(MasterDateTimeSlotForm), min_entries=0)


class PollMessageForm(ModelForm):
    class Meta:
        model = BestTimePollMessage


class PollVoteForm(ModelForm):
    class Meta:
        model = BestTimePollVote

    date_time_slots = FieldList(FormField(DateTimeSlotForm), min_entries=0)