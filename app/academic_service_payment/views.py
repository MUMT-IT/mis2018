import arrow
from io import BytesIO
from flask import request, render_template, url_for, jsonify, send_file, flash
from flask_login import login_required, current_user
from app.academic_service_payment import academic_service_payment
from app.academic_services.models import *


def get_status(s_id):
    statuses = ServiceStatus.query.filter_by(status_id=s_id).first()
    status_id = statuses.id
    return status_id


def generate_url(file_url):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': S3_BUCKET_NAME, 'Key': file_url},
                                    ExpiresIn=3600)
    return url


@academic_service_payment.route('/aws-s3/download/<key>', methods=['GET'])
def download_file(key):
    download_filename = request.args.get('download_filename')
    s3_client = boto3.client(
        's3',
        region_name=os.getenv('BUCKETEER_AWS_REGION'),
        aws_access_key_id=os.getenv('BUCKETEER_AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('BUCKETEER_AWS_SECRET_ACCESS_KEY')
    )
    outfile = BytesIO()
    s3_client.download_fileobj(os.getenv('BUCKETEER_BUCKET_NAME'), key, outfile)
    outfile.seek(0)
    return send_file(outfile, download_name=download_filename, as_attachment=True)


@academic_service_payment.route('/invoice/payment/index')
@login_required
def invoice_payment_index():
    menu = request.args.get('menu')
    return render_template('academic_service_payment/invoice_payment_index.html', menu=menu)


@academic_service_payment.route('/api/invoice/payment/index')
def get_invoices():
    query = ServiceInvoice.query.filter(ServiceInvoice.file_attached_at!=None)
    records_total = query.count()
    search = request.args.get('search[value]')
    if search:
        query = query.filter(ServiceInvoice.invoice_no.contains(search))
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)
    data = []
    for item in query:
        item_data = item.to_dict()
        download_file = url_for('academic_services.download_file', key=item.file, download_filename=f"{item.invoice_no}.pdf")
        item_data['file'] = f'''<div class="field has-addons">
                        <div class="control">
                            <a class="button is-small is-light is-link is-rounded" href="{download_file}">
                                <span class="icon is-small"><i class="fas fa-file-invoice-dollar"></i></span>
                                <span>ใบแจ้งหนี้</span>
                            </a>
                        </div>
                    </div>
                '''
        if item.payments:
            for payment in item.payments:
                if payment.slip:
                    item_data['slip'] = generate_url(payment.slip)
                else:
                    item_data['slip'] = None
        data.append(item_data)
    return jsonify({'data': data,
                    'recordFiltered': total_filtered,
                    'recordTotal': records_total,
                    'draw': request.args.get('draw', type=int)
                    })


@academic_service_payment.route('/invoice/payment/confirm/<int:invoice_id>', methods=['GET', 'POST'])
def confirm_payment(invoice_id):
    status_id = get_status(20)
    invoice = ServiceInvoice.query.get(invoice_id)
    invoice.is_paid = True
    invoice.verify_at = arrow.now('Asia/Bangkok').datetime
    invoice.verify_id = current_user.id
    invoice.quotation.request.status_id = status_id
    if not invoice.paid_at:
        payment = ServicePayment(invoice_id=invoice_id, payment_type='เช็คเงินสด',amount_paid=invoice.grand_total(),
                                 paid_at=arrow.now('Asia/Bangkok').datetime, customer_id=invoice.quotation.request.customer_id,
                                 created_at=arrow.now('Asia/Bangkok').datetime)
        invoice.paid_at = arrow.now('Asia/Bangkok').datetime
        db.session.add(invoice)
        db.session.add(payment)
    db.session.add(invoice)
    db.session.commit()
    flash('อัพเดตการชำระเงินสำเร็จ', 'success')
    return render_template('academic_service_payment/invoice_payment_index.html')