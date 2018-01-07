from . import studbp as stud


@stud.route('/')
def index():
    return '<h2>Welcome to Students Index Page.</h2>'