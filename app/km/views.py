from . import km_bp as km


@km.route('/')
def index():
    return 'Recently Added Topics'