from . import foodbp as food
from models import Person, Farm


@food.route('/')
def index():
    return '<h1>Foodly</h1>'
