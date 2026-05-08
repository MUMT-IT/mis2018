import os
import tempfile
import json

import requests
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from werkzeug.utils import secure_filename

from . import docs_query

FOLDER_ID = '1PI7ZN5V1W_NxUGRteg8cXvnJMzF2nHOd'
ALLOWED_EXTENSIONS = {'pdf'}


def _load_google_keyfile():
    try:
        from app.main import get_json_keyfile
        return get_json_keyfile()
    except Exception:
        credentials_value = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_value:
            raise RuntimeError('Google credentials are not configured')

        if credentials_value.startswith('{'):
            return json.loads(credentials_value)

        if credentials_value.startswith('http://') or credentials_value.startswith('https://'):
            return requests.get(credentials_value, timeout=10).json()

        if os.path.exists(credentials_value):
            with open(credentials_value) as credential_file:
                return json.load(credential_file)

        raise RuntimeError('GOOGLE_APPLICATION_CREDENTIALS must be a URL, JSON string, or file path')


def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(_load_google_keyfile(), scopes)
    return GoogleDrive(gauth)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _build_document_metadata(form_data):
    return {
        'document_title': (form_data.get('document_title') or '').strip(),
        'document_type': (form_data.get('document_type') or '').strip(),
        'description': (form_data.get('description') or '').strip(),
    }


def _to_drive_properties(metadata):
    properties = []
    value = metadata.get('document_type')
    if value:
        properties.append({
            'key': 'document_type',
            'value': value,
            'visibility': 'PRIVATE',
        })
    return properties


def _read_drive_properties(file_item):
    property_map = {}
    app_properties = file_item.get('appProperties') or {}
    property_map.update(app_properties)
    for prop in file_item.get('properties') or []:
        key = prop.get('key')
        if key:
            property_map[key] = prop.get('value')
    return property_map


def upload_pdf_file(upload_file, metadata):
    original_filename = secure_filename(upload_file.filename)
    temp_path = None
    try:
        drive = initialize_gdrive()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            upload_file.save(temp_file.name)
            temp_path = temp_file.name

        file_drive = drive.CreateFile({
            'title': metadata['document_title'],
            'description': metadata['description'],
            'properties': _to_drive_properties(metadata),
            'parents': [{'id': FOLDER_ID, 'kind': 'drive#fileLink'}],
        })
        file_drive.SetContentFile(temp_path)
        file_drive.Upload()
        file_drive['originalFilename'] = original_filename
        return file_drive
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def list_pdf_files():
    drive = initialize_gdrive()
    query = "'{}' in parents and trashed=false".format(FOLDER_ID)
    files = drive.ListFile({'q': query}).GetList()
    pdf_files = []
    for file_item in files:
        mime_type = file_item.get('mimeType')
        filename = file_item.get('title')
        properties = _read_drive_properties(file_item)
        if mime_type != 'application/pdf' and not (filename and filename.lower().endswith('.pdf')):
            continue
        pdf_files.append({
            'id': file_item.get('id'),
            'name': filename,
            'document_title': filename,
            'document_type': properties.get('document_type'),
            'mime_type': mime_type,
            'modified_time': file_item.get('modifiedDate'),
            'web_view_link': file_item.get('webViewLink') or file_item.get('alternateLink'),
        })
    return sorted(pdf_files, key=lambda item: item.get('modified_time') or '', reverse=True)


@docs_query.route('/', methods=['GET', 'POST'])
@login_required
def index():
    query = None
    pdf_files = []
    if request.method == 'POST':
        query = (request.form.get('query') or '').strip()
        if not query:
            flash('Please enter a search query.', 'warning')
        else:
            flash('Query submitted.', 'success')
    try:
        pdf_files = list_pdf_files()
    except Exception:
        flash('Failed to load PDF files from Google Drive.', 'danger')
    return render_template('docs_query/index.html', query=query, pdf_files=pdf_files)


@docs_query.route('/upload', methods=['POST'])
@login_required
def upload():
    upload_file = request.files.get('file')
    metadata = _build_document_metadata(request.form)
    if not metadata['document_title']:
        flash('Document title is required.', 'danger')
        return redirect(url_for('docs_query.index'))

    if not upload_file or not upload_file.filename:
        flash('Please select a PDF file to upload.', 'danger')
        return redirect(url_for('docs_query.index'))

    filename = secure_filename(upload_file.filename)
    if not allowed_file(filename):
        flash('Only PDF files are allowed.', 'danger')
        return redirect(url_for('docs_query.index'))

    try:
        file_drive = upload_pdf_file(upload_file, metadata)
        try:
            file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
        except Exception as exc:
            flash('PDF uploaded, but failed to set sharing permission: {}'.format(exc), 'warning')
        else:
            flash('PDF uploaded to Google Drive successfully.', 'success')
    except Exception as exc:
        flash('Failed to upload the PDF to Google Drive: {}'.format(exc), 'danger')
    else:
        pass

    return redirect(url_for('docs_query.index'))
