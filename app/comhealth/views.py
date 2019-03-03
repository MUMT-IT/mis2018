from flask import render_template
from . import comhealth
from .models import ComHealthService, ComHealthRecord

@comhealth.route('/')
def index():
    services = ComHealthService.query.order_by('date desc').all()
    return render_template('comhealth/index.html',
                           services=services)


@comhealth.route('/services/<int:service_id>')
def display_service_customers(service_id):
    service = ComHealthService.query.get(service_id)
    return render_template('comhealth/service_customers.html',
                           service=service)


@comhealth.route('/records/<int:record_id>')
def edit_record(record_id):
    record = ComHealthRecord.query.get(record_id)
    return str(record.date)
