# -*- coding:utf-8 -*-

import requests
import os
import dateutil.parser
import pytz
from werkzeug.utils import secure_filename

from .forms import EventForm
from . import event_bp as event
from flask import jsonify, render_template, request, flash
from googleapiclient.discovery import build
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from google.oauth2.service_account import Credentials
from pydrive.drive import GoogleDrive
from pytz import timezone

localtz = timezone('Asia/Bangkok')
CALENDAR_ID = 'mumtpr@mahidol.edu'
FOLDER_ID = '14D9JDuAx2Tr9tKWECQahx6gloaqY5U9I'

json_keyfile = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
service_account_info = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
credentials = Credentials.from_service_account_info(service_account_info)

def initialize_gdrive():
    gauth = GoogleAuth()
    scopes = ['https://www.googleapis.com/auth/drive']
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scopes)
    return GoogleDrive(gauth)


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


@event.route('/api/global')
def fetch_global_events():
    """List global events for everybody.
    :return:
    """
    tz = pytz.timezone('Asia/Bangkok')
    # credentials, project_id = google.auth.default()
    scoped_credentials = credentials.with_scopes([
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ])
    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
    request = calendar_service.events().list(
        calendarId='{}'.format(CALENDAR_ID))
    # Loop until all pages have been processed.
    all_events = []
    while request != None:
        # Get the next page.
        response = request.execute()
        # returns a list of item objects (events).
        for event in response.get('items', []):
            # The event object is a dict object with a 'summary' key.
            start = event.get('start')
            end = event.get('end')
            try:
                start = dateutil.parser.parse(start.get('dateTime')).strftime('%Y-%m-%d %H:%M')
                end = dateutil.parser.parse(end.get('dateTime')).strftime('%Y-%m-%d %H:%M')
            except:
                start = start.get('date')
                end = end.get('date')
            evt = {
                'location': event.get('location', None),
                'title': event.get('summary', 'NO SUMMARY'),
                'description': event.get('description', ''),
                'start': start,
                'end': end,
            }
            all_events.append(evt)
        # Get the next request object by passing the previous request object to
        # the list_next method.
        request = calendar_service.events().list_next(request, response)
    return jsonify(all_events)


@event.route('/global')
def list_global_events():
    return render_template('events/global.html')


@event.route('/new', methods=['GET', 'POST'])
def add_event():
    form = EventForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            start = localtz.localize(form.data.get('start'))
            end = localtz.localize(form.data.get('end'))

            if start and end:
                timedelta = end - start
                if timedelta.days < 0 or timedelta.seconds == 0:
                    flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'warning')
                else:
                    if form.upload.data:
                        upfile = form.upload.data
                        drive = initialize_gdrive()
                        filename = upfile.filename
                        upfile.save(filename)
                        file_drive = drive.CreateFile({'title': filename,
                                                       'parents': [{'id': FOLDER_ID, "kind": "drive#fileLink"}]})
                        file_drive.SetContentFile(filename)
                        try:
                            file_drive.Upload()
                            permission = file_drive.InsertPermission({'type': 'anyone',
                                                                      'value': 'anyone',
                                                                      'role': 'reader'})
                        except:
                            flash('Failed to upload the attached file to the Google drive.', 'danger')
                        file_name = filename
                        file_url = file_drive['id']
                        event = {
                            'summary': form.title.data,
                            'location': form.location.data,
                            'sendUpdates': 'all',
                            'status': 'tentative',
                            'description': form.desc.data,
                            'start': {
                                'dateTime': start.isoformat(),
                                'timeZone': 'Asia/Bangkok',
                            },
                            'end': {
                                'dateTime': end.isoformat(),
                                'timeZone': 'Asia/Bangkok',
                            },
                            'extendedProperties': {
                                'private': {
                                    'organiser': form.organiser.data.id,
                                    'registration': form.registration.data,
                                    'event_type': form.event_type.data,
                                    'file_id': file_url,
                                    'file_name': file_name
                                }
                            }
                        }
                    scoped_credentials = credentials.with_scopes([
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events'
                    ])
                    calendar_service = build('calendar', 'v3', credentials=scoped_credentials)
                    event = calendar_service.events().insert(
                        calendarId=CALENDAR_ID,
                        body=event).execute()
                    flash(u'บันทึกข้อมูลสำเร็จ.', 'success')
                    return render_template('events/global.html')

    return render_template('events/edit_form.html', form=form)
