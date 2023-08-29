from flask import render_template, flash, url_for, redirect, send_file
from flask_login import login_required, current_user
from pyhanko import stamp

from app.e_sign_api import esign
from app.e_sign_api.forms import CertificateFileForm, TestPdfSignForm
from app.e_sign_api.models import CertificateFile
from app.main import db
from pyhanko.pdf_utils import images, text
from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec, append_signature_field
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter


@esign.route('/test', methods=['GET', 'POST'])
@login_required
def test_file():
    form = TestPdfSignForm()
    if form.validate_on_submit():
        with open(f'{current_user.email}_cert.pfx', 'wb') as certfile:
            certfile.write(current_user.digital_cert_file.file)
        if current_user.digital_cert_file.image:
            with open(f'{current_user.email}_sig.png', 'wb') as imgfile:
                imgfile.write(current_user.digital_cert_file.image)

        w = IncrementalPdfFileWriter(form.doc.data)
        append_signature_field(w, SigFieldSpec(sig_field_name='Signature', on_page=0, box=(20, 100, 400, 200)))
        meta = signers.PdfSignatureMetadata(field_name='Signature')
        signer = signers.SimpleSigner.load_pkcs12(pfx_file=f'{current_user.email}_cert.pfx',
                                                  passphrase=form.passphrase.data.encode('utf-8'))
        pdf_signer = signers.PdfSigner(signer=signer,
                                       signature_meta=meta,
                                       stamp_style=stamp.TextStampStyle(
                                           stamp_text='This is a demo.\nSigned by %(signer)s\nTime: %(ts)s',
                                           text_box_style=text.TextBoxStyle(border_width=0),
                                           background=images.PdfImage(f'{current_user.email}_sig.png')
                                           )
                                       )
        out = pdf_signer.sign_pdf(w)
        return send_file(out, as_attachment=True, download_name='signed_document.pdf')
    return render_template('e_sign_api/test.html', form=form)


@esign.route('/', methods=['GET', 'POST'])
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
            dc.image = form.image_upload.data.read()
            db.session.add(dc)
            db.session.commit()
            flash('File uploaded successfully', 'success')
            return redirect(url_for('staff.index'))
    return render_template('e_sign_api/upload.html', form=form)
