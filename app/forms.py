# -*- coding:utf-8 -*-
from datetime import datetime

from wtforms import Field
from wtforms.widgets import TextInput
from pytz import timezone

tz = timezone('Asia/Bangkok')


class MyDateTimePickerField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data
        else:
            return ''

    def process_data(self, value):
        if value:
            self.data = value.astimezone(tz).isoformat()
        else:
            self.data = ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = tz.localize(datetime.strptime(valuelist[0], '%Y-%m-%d %H:%M:%S'))
        else:
            self.data = None
