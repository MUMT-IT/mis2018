from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, widgets
from wtforms_alchemy import (model_form_factory, QuerySelectField)
from .models import *


BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ProcurementRecordForm(ModelForm):
    class Meta:
        model = ProcurementRecord
        exclude = ['updated_at']

    location = QuerySelectField('Location', query_factory=lambda: RoomResource.query.all(),
                                blank_text='Select location..', allow_blank=False)
    status = QuerySelectField('Status', query_factory=lambda: ProcurementStatus.query.all(),
                                blank_text='Select status..', allow_blank=False)


