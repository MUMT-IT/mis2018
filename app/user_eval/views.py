import json
from datetime import timedelta

import arrow
from flask import render_template, request, make_response, jsonify
from flask_login import current_user

from app.main import db
from app.user_eval import user_eval
from app.user_eval.forms import EvaluationRecordForm
from app.user_eval.models import EvaluationRecord


@user_eval.route('/check', methods=['GET', 'POST'])
def check_evaluate():
    blueprint = request.args.get('blueprint')
    if current_user.is_authenticated:
        latest_record = (
            EvaluationRecord.query
            .filter_by(staff_id=current_user.id, blueprint=blueprint)
            .order_by(EvaluationRecord.created_at.desc(), EvaluationRecord.id.desc())
            .first()
        )
        form = EvaluationRecordForm()
        if request.method == 'GET':
            if not latest_record:
                return render_template('user_eval/modals/evaluation_form.html',
                                       form=form, blueprint=blueprint)

            elapsed = arrow.now('Asia/Bangkok').datetime - latest_record.created_at
            if elapsed >= timedelta(days=365):
                return render_template('user_eval/modals/evaluation_form.html',
                                       form=form, blueprint=blueprint)
            else:
                resp = make_response()
                return resp
        if request.method == 'POST':
            if form.validate_on_submit():
                new_record = EvaluationRecord(staff_id=current_user.id)
                form.populate_obj(new_record)
                new_record.blueprint = blueprint
                new_record.created_at = arrow.now('Asia/Bangkok').datetime
                db.session.add(new_record)
                db.session.commit()
                resp = make_response()
                resp.headers['HX-Trigger'] = json.dumps({'successAlert': 'ได้รับผลประเมินแล้ว', 'closeModal': ''})
                return resp
            else:
                print(form.errors)
