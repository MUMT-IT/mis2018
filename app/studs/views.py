from ..models import Student
from . import studbp as stud


@stud.route('/')
def index():
    stud = Student.query.first()
    print(stud.th_first_name)
    return '<h2>Welcome to Students Index Page.</h2>'
