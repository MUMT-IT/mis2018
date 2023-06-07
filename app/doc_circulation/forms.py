from wtforms.validators import DataRequired

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectMultipleField, widgets, BooleanField
from wtforms_alchemy import (model_form_factory, QuerySelectField, QuerySelectMultipleField)
from app.doc_circulation.models import *


BaseModelForm = model_form_factory(FlaskForm)


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class RoundForm(ModelForm):
    class Meta:
        model = DocRound
        only = ['date']


class DocumentForm(ModelForm):
    class Meta:
        model = DocDocument
        exclude = ['stage']
        field_args = {'title': {'validators': [DataRequired()]},
                      'number': {'validators': [DataRequired()]}}

    category = QuerySelectField('Category', query_factory=lambda: DocCategory.query.all(),
                                get_label='name', blank_text='Select category..', allow_blank=False)

    upload = FileField('File Upload')


def create_doc_receipt_form(org):
    class DocumentReceiptForm(ModelForm):
        class Meta:
            model = DocReceiveRecord
            only = ['comment', 'predefined_comment']
        send_all = BooleanField('All', default=False)
        members = QuerySelectMultipleField(u'Members', get_label='fullname',
                                         validators=[DataRequired()],
                                         query_factory=lambda: org.staff,
                                         widget=widgets.ListWidget(prefix_label=False),
                                         option_widget=widgets.CheckboxInput())
    return DocumentReceiptForm


class RoundSendForm(FlaskForm):
    targets = SelectMultipleField('Targets', validators=[DataRequired()],
                                  coerce=int,
                                  widget=widgets.ListWidget(prefix_label=False),
                                  option_widget=widgets.CheckboxInput())


class PrivateMessageForm(ModelForm):
    class Meta:
        model = DocDocumentReach
        only = ['sender_comment']