from flask import render_template, request
from flask_login import login_required

from . import audio_visual_unit_bp as audio_visual
from ..procurement.models import ProcurementDetail


@audio_visual.route('/')
def index():
    return render_template('audio_visual_unit/audio_visual_main.html')


@audio_visual.route('/erp_code/search')
@login_required
def procurement_search_by_erp_code():
    return render_template('audio_visual_unit/procurement_search_by_erp_code.html')


@audio_visual.route('/list', methods=['POST', 'GET'])
@login_required
def procurement_list():
    if request.method == 'GET':
        procurement_detail = ProcurementDetail.query.filter_by(is_audio_visual_equipment=True)
    else:
        erp_code = request.form.get('erp_code', None)
        if erp_code:
            procurement_detail = (ProcurementDetail.query.filter_by(is_audio_visual_equipment=True) and
                                  ProcurementDetail.query.filter(ProcurementDetail.erp_code.like('%{}%'.format(erp_code))))
        else:
            procurement_detail = []
        if request.headers.get('HX-Request') == 'true':
            return render_template('audio_visual_unit/partials/procurement_list.html', procurement_detail=procurement_detail)

    return render_template('audio_visual_unit/procurement_list.html', procurement_detail=procurement_detail)

