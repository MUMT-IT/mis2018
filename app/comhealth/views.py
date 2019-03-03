from . import comhealth

@comhealth.route('/')
def index():
    return 'Com Health Index Page'