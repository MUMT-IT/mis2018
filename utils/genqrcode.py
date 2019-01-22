import sys
import pyqrcode
from jinja2 import Environment, FileSystemLoader
from pandas import read_excel

data = read_excel(sys.argv[1], header=None,
            names=['refno', 'uid', 'title', 'firstname', 'lastname'])

students = []
for _, student in data.iterrows():
    qrcode = pyqrcode.create(student['uid'])
    qrcode.png('qrimages/{}.png'.format(student['uid']), scale=5)
    students.append(student)

env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('qrcode-template.html')
output = open('qrcode.html', 'w')
output.write(template.render(students=students).encode('utf-8'))
output.close()