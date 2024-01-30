from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from . import audio_visual_unit_bp as audio_visual
from .forms import CreateRecordForm, AddedLenderForm
from .models import AVUBorrowReturnServiceDetail
from ..main import db
from ..procurement.models import ProcurementDetail
from pytz import timezone
from datetime import datetime
import arrow

bangkok = timezone('Asia/Bangkok')


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
    # if request.method == 'GET':
    #     procurement_detail = ProcurementDetail.query.filter_by(is_audio_visual_equipment=True)
    # else:
    #     erp_code = request.form.get('erp_code', None)
    #     if erp_code:
    #         procurement_detail = (ProcurementDetail.query.filter_by(is_audio_visual_equipment=True) and
    #                               ProcurementDetail.query.filter(ProcurementDetail.erp_code.like('%{}%'.format(erp_code))))
    #     else:
    #         procurement_detail = []
    #     if request.headers.get('HX-Request') == 'true':
    #         return render_template('audio_visual_unit/partials/procurement_list.html', procurement_detail=procurement_detail)

    return render_template('audio_visual_unit/procurement_list.html', procurement_detail=procurement_detail)


@audio_visual.route('/record/add/<string:procurement_no>', methods=['GET', 'POST'])
def add_borrow_return_audio_visual_record(procurement_no):
    procurement_detail = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = CreateRecordForm()
    if form.validate_on_submit():
        if form.request_date.data:
            startdatetime = arrow.get(form.start.data, 'Asia/Bangkok').datetime
        else:
            startdatetime = None
        if form.received_date.data:
            enddatetime = arrow.get(form.end.data, 'Asia/Bangkok').datetime
        else:
            enddatetime = None
        borrow_return_audio_visual = AVUBorrowReturnServiceDetail()
        form.populate_obj(borrow_return_audio_visual)
        borrow_return_audio_visual.request_date = startdatetime
        borrow_return_audio_visual.received_date = enddatetime
        borrow_return_audio_visual.staff = current_user
        borrow_return_audio_visual.created_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(borrow_return_audio_visual)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('audio_visual_unit.index', procurement_id=procurement_detail.id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('audio_visual_unit/new_audio_visual_record.html', procurement_detail=procurement_detail, form=form)


@audio_visual.route('/item/view')
def view_audio_visual_items():
    return render_template('audio_visual_unit/view_audio_visual_items.html')


@audio_visual.route('/api/data/audio_visual/view')
def get_audio_visual_items_data():
    query = ProcurementDetail.query
    search = request.args.get('search[value]')
    query = query.filter(db.or_(
        ProcurementDetail.procurement_no.like(u'%{}%'.format(search)),
        ProcurementDetail.name.like(u'%{}%'.format(search)),
        ProcurementDetail.erp_code.like(u'%{}%'.format(search)),
    ))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        item_data['borrow'] = '<a href="{}"><i class="fas fa-check-circle">ยืม</i></a>'.format(
            url_for('audio_visual.add_borrow_return_audio_visual_record', procurement_no=item.procurement_no))
        item_data['borrow_computer'] = '<a href="{}"><i class="fas fa-check-circle">ยืม</i></a>'.format(
            url_for('procurement.add_borrow_detail', procurement_no=item.procurement_no))
        data.append(item_data)
    return jsonify({'data': data,
                    'recordsFiltered': total_filtered,
                    'recordsTotal': ProcurementDetail.query.count(),
                    'draw': request.args.get('draw', type=int),
                    })


@audio_visual.route('/lender/detail/add/<string:procurement_no>', methods=['GET', 'POST'])
def add_lender_detail(procurement_no):
    procurement = ProcurementDetail.query.filter_by(procurement_no=procurement_no).first()
    form = AddedLenderForm(obj=procurement)
    if form.validate_on_submit():
        form.populate_obj(procurement)
        db.session.add(procurement)
        db.session.commit()
        flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
        return redirect(url_for('procurement.view_desc_procurement_for_audio_visual_equipment', procurement_id=procurement.id))
    else:
        for er in form.errors:
            flash("{} {}".format(er, form.errors[er]), 'danger')
    return render_template('audio_visual_unit/add_lender_detail.html',
                           form=form, url_callback=request.referrer,
                           procurement_no=procurement_no,
                           procurement=procurement)


