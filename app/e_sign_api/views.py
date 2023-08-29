from flask import render_template, flash, url_for, redirect
from flask_login import login_required, current_user

from app.e_sign_api import esign
from app.e_sign_api.forms import CertificateFileForm
from app.e_sign_api.models import CertificateFile
from app.main import db


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