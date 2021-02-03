from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, PasswordField
from wtforms.validators import DataRequired, EqualTo


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log in')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Submit')


class PasswordSetup(FlaskForm):
    curr_pass = PasswordField('Current Password', validators=[DataRequired()])
    new_pass = PasswordField('New Password', validators=[DataRequired(), EqualTo(curr_pass)])


class ResetPasswordForm(FlaskForm):
    new_pass = PasswordField('New Password', validators=[DataRequired()])
    confirm_pass = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('new_pass')])
    submit = SubmitField('Submit')
