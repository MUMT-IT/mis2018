from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory

from app.main import db
from app.models import Strategy, StrategyTactic, StrategyTheme, StrategyActivity

BaseModelForm = model_form_factory(FlaskForm)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class StrategyForm(ModelForm):
    class Meta:
        model = Strategy
        only = ['refno', 'content']


class StrategyTacticForm(ModelForm):
    class Meta:
        model = StrategyTactic
        only = ['refno', 'content']


class StrategyThemeForm(ModelForm):
    class Meta:
        model = StrategyTheme
        only = ['refno', 'content']


class StrategyActivityForm(ModelForm):
    class Meta:
        model = StrategyActivity
        only = ['refno', 'content']
