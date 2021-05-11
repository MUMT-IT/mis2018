import requests
import os
import dateutil.parser
import pytz
from . import event_bp as event
from flask import jsonify, render_template
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

CALENDAR_ID = 'mumtpr@mahidol.edu'

service_account_info = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
credentials = Credentials.from_service_account_info(service_account_info)


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
                start =  dateutil.parser.parse(start.get('dateTime')).date().strftime('%Y-%m-%d')
                end = dateutil.parser.parse(end.get('dateTime')).date().strftime('%Y-%m-%d')
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
