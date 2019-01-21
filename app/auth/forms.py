from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log in')