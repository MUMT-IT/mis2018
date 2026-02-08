from flask_wtf import FlaskForm
from wtforms.validators import DataRequired
from wtforms_alchemy import model_form_factory, QuerySelectMultipleField, QuerySelectField
from wtforms_components import DateField
from sqlalchemy.inspection import inspect as sa_inspect

from app.main import db
from wtforms import FieldList, FormField, TextAreaField

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


class BestTimeDateTimeSlotForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    time_slots = CheckboxSelectMultipleField('Time slots')


class BestTimeMasterDateTimeSlotForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    time_slots = CheckboxSelectMultipleField('Time slots')


class BestTimePollForm(ModelForm):
    class Meta:
        model = BestTimePoll

    def populate_obj(self, obj):
        mapper = sa_inspect(obj.__class__)
        model_attrs = set(mapper.attrs.keys())

        # populate only real model-mapped attributes
        for name, field in self._fields.items():
            if name in model_attrs:
                field.populate_obj(obj, name)

    chairman = QuerySelectField('ประธาน', query_factory=lambda: StaffAccount.query.all(), get_label="fullname")
    invitees = QuerySelectMultipleField('กรรมการ', query_factory=lambda: StaffAccount.query.all(), get_label="fullname")
    admins = QuerySelectMultipleField(query_factory=lambda: StaffAccount.query.all(), get_label="fullname")
    datetime_slots = FieldList(FormField(BestTimeMasterDateTimeSlotForm), min_entries=0)


class BestTimePollMessageForm(ModelForm):
    class Meta:
        model = BestTimePollMessage
        field_args = {'message': {'validators': [DataRequired()]}}


class BestTimePollVoteForm(ModelForm):
    class Meta:
        model = BestTimePollVote
        date_format = '%d/%m/%Y'

    date_time_slots = FieldList(FormField(BestTimeDateTimeSlotForm), min_entries=0)


class BestTimeMailForm(FlaskForm):
    message = TextAreaField('ข้อความ')