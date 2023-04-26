from flask import render_template

from app.complaint_tracker import complaint_tracker


@complaint_tracker.route('/')
def index():
    return render_template('complaint_tracker/index.html')