from . import lisedu as lis
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_user
from models import StudentUser
from ..models import Student
from ..main import login_manager


@login_manager.user_loader
def load_user(user_id):
    user = Student.query.get(user_id)
    if user:
        return user
    else:
        return None


@lis.route('/')
def main_page():
    return render_template('/lisedu/main.html')


@lis.route('/login/<personnel>/')
def student_login(personnel='student'):
    user_id = request.args.get('user_id')
    if user_id is None:
        return 'no user id specified'
    else:
        if personnel == 'student':
            user_login = Student.query.get(user_id)
        if user_login:
            user = StudentUser(user_login)
            if login_user(user):
                flash('You have been logged in.')
                return render_template('/lisedu/main.html', user=user, login=True)
            else:
                flash('Login failed.')
                return render_template('/lisedu/main.html', user=None, login=False)
        else:
            flash('Login failed, user not found.')
            return render_template('/lisedu/main.html', user=None, login=False)
