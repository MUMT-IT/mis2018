# -*- coding:utf-8 -*-
import datetime

from . import data_bp
from app.main import db, csrf
from app.data_blueprint.forms import *
from flask import url_for, render_template, redirect, flash, request, jsonify
from flask_login import current_user, login_required
from pytz import timezone
import arrow

from app.models import DataFile, DataTag
from app.staff.models import StaffAccount, StaffPersonalInfo

tz = timezone('Asia/Bangkok')


@data_bp.route('/orgs')
@login_required
def orgs():
    orgs = Org.query.filter(Org.name != 'ทีมบริหารและหัวหน้า').all()
    return render_template('data_blueprint/orgs.html', orgs=orgs)


@data_bp.route('/orgs/<int:org_id>/kpis')
@login_required
def list_org_kpis(org_id):
    kpis = Process.query.filter_by(org_id=org_id).all()
    org = Org.query.filter_by(id=org_id).first()

    grouped_processes = {}
    for process in kpis:
        if process.parent_id not in grouped_processes:
            grouped_processes[process.parent_id] = []
        grouped_processes[process.parent_id].append(process)

    sorted_processes = []
    def add_process_and_children(parent_id):
        if parent_id in grouped_processes:
            for process in grouped_processes[parent_id]:
                sorted_processes.append(process)
                add_process_and_children(process.id)
    add_process_and_children(None)
    return render_template('data_blueprint/org_kpis.html', kpis=sorted_processes, org=org)


@data_bp.route('/orgs/<int:org_id>/kpis/<int:process_id>/expired')
@login_required
def make_expired_org_process(org_id, process_id):
    process = Process.query.filter_by(id=process_id).first()
    process.is_expired = True
    process.expired_at = arrow.now('Asia/Bangkok').datetime
    process.expired_by_account_id = current_user.id
    db.session.add(process)
    db.session.commit()
    flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('data_bp.list_org_kpis', org_id=org_id))


@data_bp.route('/orgs/<int:org_id>/process/new', methods=['GET', 'POST'])
@data_bp.route('/orgs/<int:org_id>/process/<int:process_id>/edit', methods=['GET', 'POST'])
@login_required
def process_org_form(org_id, process_id=None):
    if process_id:
        data_ = Process.query.get(process_id)
        form = ProcessForm(obj=data_)
    else:
        form = ProcessForm()
        data_ = None
    if request.method == 'POST':
        if form.validate_on_submit():
            if not process_id:
                new_data = Process()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                new_data.staff = staff_list
            else:
                form.populate_obj(data_)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                data_.staff = staff_list
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.list_org_kpis', org_id=org_id))
    if data_:
        staff_list = data_.staff
    else:
        staff_list = []
    return render_template('data_blueprint/process_org_form.html', form=form, staff_list=staff_list, org_id=org_id)


@data_bp.route('/')
def index():
    data = Data.query.all()
    core_services = CoreService.query.all()
    back_office_processes = Process.query.filter_by(category='back_office', parent_id=None).all()
    crm_processes = Process.query.filter_by(category='crm', parent_id=None).all()
    performance_processes = Process.query.filter_by(category='performance', parent_id=None).all()
    regulation_processes = Process.query.filter_by(category='regulation', parent_id=None).all()
    return render_template('data_blueprint/index.html',
                           core_services=core_services,
                           data=data,
                           back_office_processes=back_office_processes,
                           crm_processes=crm_processes,
                           performance_processes=performance_processes,
                           regulation_processes=regulation_processes,
                           )


@data_bp.route('/core-services/new', methods=['GET', 'POST'])
@data_bp.route('/core-services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def core_service_form(service_id=None):
    if service_id:
        service_ = CoreService.query.get(service_id)
        form = CoreServiceForm(obj=service_)
        staff_list = service_.staff
    else:
        form = CoreServiceForm()
        staff_list = []
    if request.method == 'POST':
        if form.validate_on_submit():
            if not service_id:
                new_service = CoreService()
                form.populate_obj(new_service)
                new_service.creator_id = current_user.id
                db.session.add(new_service)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                new_service.staff = staff_list
            else:
                form.populate_obj(service_)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                service_.staff = staff_list
                db.session.add(service_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/core_services.html',
                           form=form, service_id=service_id, staff_list=staff_list)


@data_bp.route('/data/new', methods=['GET', 'POST'])
@data_bp.route('/data/<int:data_id>/edit', methods=['GET', 'POST'])
@login_required
def data_form(data_id=None):
    if data_id:
        data_ = Data.query.get(data_id)
        form = DataForm(obj=data_)
    else:
        form = DataForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if not data_id:
                new_data = Data()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
            else:
                form.populate_obj(data_)
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    return render_template('data_blueprint/data_form.html', form=form)


@data_bp.route('/process/new', methods=['GET', 'POST'])
@data_bp.route('/process/<int:process_id>/edit', methods=['GET', 'POST'])
@login_required
def process_form(process_id=None):
    if process_id:
        data_ = Process.query.get(process_id)
        form = ProcessForm(obj=data_)
    else:
        form = ProcessForm()
        data_ = None
    if request.method == 'POST':
        if form.validate_on_submit():
            if not process_id:
                new_data = Process()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                db.session.add(new_data)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                new_data.staff = staff_list
            else:
                form.populate_obj(data_)
                staff_list = []
                for p_id in request.form.getlist('staff'):
                    staff_info = StaffPersonalInfo.query.get(int(p_id))
                    staff_list.append(staff_info.staff_account)
                data_.staff = staff_list
                db.session.add(data_)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.index'))
    if data_:
        staff_list = data_.staff
    else:
        staff_list = []
    return render_template('data_blueprint/process_form.html', form=form, staff_list=staff_list)


@data_bp.route('/kpi/new', methods=['GET', 'POST'])
@data_bp.route('/kpi/<int:kpi_id>/edit', methods=['GET', 'POST'])
@login_required
def kpi_form(kpi_id=None):
    accounts = [("", "โปรดระบุชื่อ")] + [(u.email, u.fullname)
                                          for u in StaffAccount.query.all() if not u.is_retired]
    section = request.args.get('section', 'general')
    process_id = request.args.get('process_id', type=int)
    service_id = request.args.get('service_id', type=int)
    if section == 'general':
        Form = KPIForm
    elif section == 'target':
        Form = KPITargetForm
    else:
        Form = KPIReportForm
    if service_id:
        service = CoreService.query.get(service_id)
    if process_id:
        proc = Process.query.get(process_id)
    if kpi_id:
        data_ = KPI.query.get(kpi_id)
        form = Form(obj=data_)
    else:
        form = Form()
    if section == 'general':
        form.keeper.choices = accounts
    elif section == 'target':
        form.target_account.choices = accounts
        form.target_reporter.choices = accounts
        form.target_setter.choices = accounts
    elif section == 'report':
        form.account.choices = accounts
        form.pfm_account.choices = accounts
        form.pfm_responsible.choices = accounts
        form.pfm_consult.choices = accounts
        form.pfm_informed.choices = accounts
        form.reporter.choices = accounts
        form.consult.choices = accounts
        form.informed.choices = accounts
    if request.method == 'POST':
        if form.validate_on_submit():
            if not kpi_id:
                new_data = KPI()
                form.populate_obj(new_data)
                new_data.creator_id = current_user.id
                if service_id:
                    new_data.core_services.append(service)
                if process_id:
                    new_data.processes.append(proc)
                db.session.add(new_data)
            else:
                form.populate_obj(data_)
                db.session.add(data_)
            db.session.commit()
            flash('บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
            return redirect(url_for('data_bp.process_detail', process_id=process_id))
        else:
            flash(form.errors, 'danger')
    if section == 'general':
        return render_template('data_blueprint/kpi_form.html',
                               form=form, process_id=process_id, kpi_id=kpi_id)
    elif section == 'target':
        return render_template('data_blueprint/kpi_form_target.html',
                               form=form, process_id=process_id, kpi_id=kpi_id)
    else:
        return render_template('data_blueprint/kpi_form_report.html',
                               form=form, process_id=process_id, kpi_id=kpi_id)


@data_bp.route('/datasets/<int:dataset_id>/kpis/add', methods=['POST'])
@login_required
def add_kpi_to_dataset(dataset_id):
    ds = Dataset.query.get(dataset_id)
    kpi = KPI.query.filter_by(refno=request.form['refno']).first()
    if kpi:
        ds.kpis.append(kpi)
        db.session.add(ds)
        db.session.commit()
        flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
    else:
        flash(u'ไม่พบตัวชี้วัดดังกล่าว', 'warning')
    return redirect(url_for('data_bp.dataset_detail', dataset_id=dataset_id))


@data_bp.route('/datasets/<int:dataset_id>/kpis/<int:kpi_id>/remove', methods=['GET'])
@login_required
def remove_kpi_from_dataset(dataset_id, kpi_id):
    ds = Dataset.query.get(dataset_id)
    kpi = KPI.query.get(kpi_id)
    ds.kpis.remove(kpi)
    db.session.add(ds)
    db.session.commit()
    flash(u'ลบตัวชี้วัดออกจากชุดข้อมูลเรียบร้อย', 'success')
    return redirect(url_for('data_bp.dataset_detail', dataset_id=dataset_id))


@data_bp.route('/data/<int:data_id>', methods=['GET'])
@login_required
def data_detail(data_id):
    data = Data.query.get(data_id)
    return render_template('data_blueprint/data_detail.html', data=data)


@data_bp.route('/data/<int:data_id>/datasets/<int:dataset_id>/edit', methods=['GET', 'POST'])
@data_bp.route('/data/<int:data_id>/datasets/form', methods=['GET', 'POST'])
@login_required
def dataset_form(data_id, dataset_id=None):
    if dataset_id:
        dataset = Dataset.query.get(dataset_id)
        form = createDatasetForm(data_id=data_id)(obj=dataset)
    else:
        form = createDatasetForm(data_id=data_id)()
        dataset = None
    if request.method == 'POST':
        if form.validate_on_submit():
            if not dataset_id:
                new_dataset = Dataset()
                form.populate_obj(new_dataset)
                new_dataset.creator_id = current_user.id
                new_dataset.data_id = data_id
                db.session.add(new_dataset)
                db.session.commit()
                flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
                return redirect(url_for('data_bp.data_detail', data_id=data_id))
            else:
                form.populate_obj(dataset)
                new_tags = []
                for text in request.form.getlist('tags'):
                    tag = DataTag.query.filter_by(tag=text).first()
                    if tag is None:
                        tag = DataTag(tag=text)
                    new_tags.append(tag)

                dataset.tags = new_tags
                db.session.add(dataset)
                db.session.commit()
                flash(u'บันทึกข้อมูลเรียบร้อยแล้ว', 'success')
                return render_template('data_blueprint/dataset_detail.html', dataset=dataset)
    return render_template('data_blueprint/dataset_form.html', form=form, dataset=dataset)


@data_bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@login_required
def dataset_detail(dataset_id):
    ds = Dataset.query.get(dataset_id)
    return render_template('data_blueprint/dataset_detail.html', dataset=ds)


@data_bp.route('/core_services/<int:service_id>/delete')
@login_required
def delete_core_service(service_id):
    sv = CoreService.query.get(service_id)
    db.session.delete(sv)
    db.session.commit()
    flash(u'ลบข้อมูลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('data_bp.index'))


@data_bp.route('/core_services/<int:service_id>')
@login_required
def core_service_detail(service_id):
    cs = CoreService.query.get(service_id)
    data = []
    for d in cs.data:
        data.append([cs.service, d.name + '(data)', 1])
        kpis_from_datasets = set()
        for ds in d.datasets:
            if cs in ds.core_services:
                data.append([d.name + '(data)', (ds.name or ds.reference) + '(ds)', 1])
                for kpi in ds.kpis:
                    if kpi in cs.kpis:
                        data.append([ds.name + '(ds)', kpi.name + '(kpi)', 1])
                        kpis_from_datasets.add(kpi)
                if not ds.kpis:
                    data.append([(ds.name or ds.reference) + '(ds)', u'ไม่มีตัวชี้วัด', 1])
    for kpi in cs.kpis:
        if kpi not in kpis_from_datasets:
            data.append([cs.service, kpi.name + '(kpi)', 1])

    return render_template('data_blueprint/core_service_detail.html', core_service=cs, data=data)


@data_bp.route('/processes/<int:process_id>')
@data_bp.route('/processes/from-org/<int:org_id>')
@data_bp.route('/processes/<int:process_id>/kpis/all')
@data_bp.route('/processes/<int:process_id>/kpis/<int:kpi_id>')
@login_required
def process_detail(process_id, kpi_id=None, org_id=None):
    proc = Process.query.get(process_id)
    data = []
    if kpi_id:
        kpi = KPI.query.get(kpi_id)
        all_kpis = [kpi]
    else:
        all_kpis = proc.kpis

    dataset_data_pairs = set()
    data_list = []
    for k in all_kpis:
        data.append([proc.name, k.name + '(kpi)', 1])
        for ds in k.datasets:
            data.append([k.name + '(kpi)', (ds.name or ds.reference) + '(ds)', 1])
            ds_dt_pair = ((ds.name or ds.reference), ds.data.name)
            if ds_dt_pair not in dataset_data_pairs:
                data.append([(ds.name or ds.reference) + '(ds)', ds.data.name + '(data)', 1])
                dataset_data_pairs.add(ds_dt_pair)
                data_list.append(ds.data.name)

    return render_template('data_blueprint/process_detail.html', process=proc, data=data, kpi_id=kpi_id, org_id=org_id)


@data_bp.route('/datasets/<int:dataset_id>/ropas')
def get_ropa_detail(dataset_id):
    ds = Dataset.query.get(dataset_id)
    if not ds.ropa:
        r = ROPA(dataset=ds, updater=current_user)
        form = ROPAForm(obj=r)
        db.session.add(r)
        db.session.commit()
        flash(u'เพิ่มรายการ ROPA เรียบร้อย', 'success')
        return render_template('data_blueprint/ropa_form.html', dataset=ds, form=form)
    return render_template('data_blueprint/ropa_detail.html', dataset=ds)


@data_bp.route('/datasets/<int:dataset_id>/ropas/<int:ropa_id>', methods=['GET', 'POST'])
def edit_ropa(dataset_id, ropa_id):
    ropa = ROPA.query.get(ropa_id)
    form = ROPAForm(obj=ropa)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(ropa)
            ropa.updated_at = datetime.datetime.now(tz)
            db.session.add(ropa)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('data_bp.get_ropa_detail', dataset_id=dataset_id))
        else:
            flash(u'{}'.format(form.errors), 'danger')
    return render_template('data_blueprint/ropa_form.html', dataset=ropa.dataset, form=form)


@data_bp.route('/ropas/<int:ropa_id>/data-subjects/add', methods=['GET', 'POST'])
def add_subject(ropa_id):
    ropa = ROPA.query.get(ropa_id)
    form = DataSubjectForm()
    if form.validate_on_submit():
        subject = DataSubject()
        form.populate_obj(subject)
        db.session.add(subject)
        db.session.commit()
        flash(u'เพิ่มรายการเรียบร้อยแล้ว', 'success')
        return redirect(url_for('data_bp.edit_ropa', ropa_id=ropa.id, dataset_id=ropa.dataset.id))
    return render_template('data_blueprint/data_subject_form.html', form=form, ropa_id=ropa_id)


@data_bp.route('api/v1.0/data-file', methods=['POST'])
@csrf.exempt
def add_datafile():
    data_file = request.get_json()
    dataset_ref = data_file['dataset_ref']
    dataset = Dataset.query.filter_by(reference=dataset_ref).first()
    update_datetime = datetime.datetime.fromtimestamp(data_file['update_datetime'])
    create_datetime = datetime.datetime.fromtimestamp(data_file['create_datetime'])
    _file = DataFile.query.filter_by(url=data_file['url']).first()
    if not _file:
        new_file = DataFile(name=data_file['name'],
                            dataset=dataset,
                            url=data_file['url'],
                            created_at=create_datetime,
                            updated_at=update_datetime)
        db.session.add(new_file)
    else:
        _file.updated_at = update_datetime
        db.session.add(_file)
    db.session.commit()
    return jsonify({'message': 'success'}), 201


@data_bp.route('api/v1.0/tags', methods=['GET'])
@csrf.exempt
def get_all_tags():
    tags = [tag.to_dict() for tag in DataTag.query.all()]
    return jsonify({'results': tags})


@data_bp.route('/datasets/datacatalog')
def datacatalog():
    tags = DataTag.query.all()
    all_data = Data.query.all()
    tag_id = request.args.get('tag_id')
    data_id = request.args.get('data_id')
    data = Data.query.get(data_id)
    datatag = DataTag.query.get(tag_id)
    datasets = []
    for dataset in Dataset.query.all():
        if tag_id:
            for tag in dataset.tags:
                if tag == datatag:
                    datasets.append(dataset)
        elif data_id:
            if data == dataset.data:
                datasets.append(dataset)
        else:
            datasets.append(dataset)
    return render_template('data_blueprint/datacatalog.html', tags=tags, all_data=all_data, datasets=datasets, tag_id=tag_id)


@data_bp.route('/datasets/datacatalog/<int:set_id>')
def datacatalog_dataset_detail(set_id):
    dataset = Dataset.query.get(set_id)
    file_id = request.args.get('file_id')
    file_detail = DataFile.query.filter_by(id=file_id).first()
    return render_template('data_blueprint/datacatalog_dataset_detail.html', dataset=dataset, file_detail=file_detail)
