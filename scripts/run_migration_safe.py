import os
import sys
import types
from dotenv import load_dotenv

# Load .env so DATABASE_URL is available
load_dotenv()

# Build a minimal Flask app and SQLAlchemy/Migrate objects
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, migrate as fmigrate

app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError('DATABASE_URL not set in environment or .env')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace('://', 'ql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Create DB and Migrate instances
db = SQLAlchemy()
migrate = Migrate()

# Insert a fake module for app.main so model modules that do `from app.main import db` get our db
fake_main = types.ModuleType('app.main')
fake_main.db = db
fake_main.migrate = migrate
sys.modules['app.main'] = fake_main

# Now import the models (they will import db from app.main)
import importlib
import app.continuing_edu.models as _models  # noqa: F401

# Initialize extensions with our Flask app
db.init_app(app)
migrate.init_app(app, db)

if __name__ == '__main__':
    with app.app_context():
        fmigrate(message='autogen: update models')
        print('Autogenerate migration attempted')
