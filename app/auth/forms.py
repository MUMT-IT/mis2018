from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField
from wtforms.validators import DataRequired, EqualTo


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log in')


class PasswordSetup(FlaskForm):
    curr_pass = PasswordField('Current Password', validators=[DataRequired()])
    new_pass = PasswordField('New Password', validators=[DataRequired(), EqualTo(curr_pass)])
