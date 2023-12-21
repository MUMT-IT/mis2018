import arrow
from flask import render_template, flash, url_for, redirect, send_file
from flask_login import login_required, current_user
from pyhanko import stamp
from pyhanko.pdf_utils.font import opentype

from app.e_sign_api import esign
from app.e_sign_api.forms import CertificateFileForm, TestPdfSignForm
from app.e_sign_api.models import CertificateFile
from app.main import db
from pyhanko.pdf_utils import images, text
from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec, append_signature_field
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter


@esign.route('/')
@login_required
def index():
    return render_template('e_sign_api/index.html')


@esign.route('/test', methods=['GET', 'POST'])
@login_required
def test_file():
    form = TestPdfSignForm()
    if form.validate_on_submit():
        with open(f'{current_user.email}_cert.pfx', 'wb') or open(f'TUC_{current_user.email}.p12') as certfile:
            certfile.write(current_user.digital_cert_file.file)
        if current_user.digital_cert_file.image:
            with open(f'{current_user.email}_sig.png', 'wb') as imgfile:
                imgfile.write(current_user.digital_cert_file.image)

        w = IncrementalPdfFileWriter(form.doc.data)
        append_signature_field(w, SigFieldSpec(sig_field_name='Signature', on_page=0, box=(20, 100, 400, 200)))
        meta = signers.PdfSignatureMetadata(field_name='Signature')
        signer = signers.SimpleSigner.load_pkcs12(pfx_file=f'{current_user.email}_cert.pfx' or f'TUC_{current_user.email}.p12',
                                                  passphrase=form.passphrase.data.encode('utf-8'))
        pdf_signer = signers.PdfSigner(signer=signer,
                                       signature_meta=meta
                                       )
        out = pdf_signer.sign_pdf(w)
        return send_file(out, as_attachment=True, download_name='signed_document.pdf')
    return render_template('e_sign_api/test.html', form=form)


@esign.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = CertificateFileForm()
    if form.validate_on_submit():
        if not form.file_upload.data:
            flash('File not found.', 'danger')
        else:
            dc = CertificateFile.query.filter_by(staff=current_user).first()
            if dc is None:
                dc = CertificateFile(staff=current_user)
            dc.file = form.file_upload.data.read()
            if form.image_upload.data:
                dc.image = form.image_upload.data.read()
            else:
                dc.image = None
            dc.created_at = arrow.now('Asia/Bangkok').datetime
            db.session.add(dc)
            db.session.commit()
            flash('File uploaded successfully', 'success')
            return redirect(url_for('e_sign.index'))
    return render_template('e_sign_api/upload.html', form=form)


def e_sign(doc, passphrase, x1=100, y1=100, x2=100, y2=100, include_image=True, sig_field_name='Signature', message=None):
    with open(f'{current_user.email}_cert.pfx', 'wb') or open(f'TUC_{current_user.email}.p12') as certfile:
        certfile.write(current_user.digital_cert_file.file)
    if current_user.digital_cert_file.image and include_image:
        with open(f'{current_user.email}_sig.png', 'wb') as imgfile:
            imgfile.write(current_user.digital_cert_file.image)

    w = IncrementalPdfFileWriter(doc)
    append_signature_field(w, SigFieldSpec(sig_field_name=sig_field_name, on_page=0, box=(x1, y1, x2, y2)))
    meta = signers.PdfSignatureMetadata(field_name=sig_field_name)
    signer = signers.SimpleSigner.load_pkcs12(pfx_file=f'{current_user.email}_cert.pfx' or f'TUC_{current_user.email}.p12',
                                              passphrase=passphrase.encode('utf-8'))
    pdf_signer = signers.PdfSigner(signer=signer,
                                   signature_meta=meta,
                                   stamp_style=stamp.TextStampStyle(stamp_text=message,
                                   text_box_style=text.TextBoxStyle(
                                       font=opentype.GlyphAccumulatorFactory('app/static/fonts/THSarabunNew.ttf'),
                                       font_size= 16
                                   ))
                                   )
    if include_image:
        pdf_signer.background = images.PdfImage(f'{current_user.email}_sig.png')
    out = pdf_signer.sign_pdf(w)
    return out
