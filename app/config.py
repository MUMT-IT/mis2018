"""
    Config file for the web app.
"""

import os

POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
DEV_DATABASE = os.environ.get('DEV_DATABASE')
DATABASE = os.environ.get('DATABASE')

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class SQLiteDevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///mumtmis.db'


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = \
    'postgres+psycopg2://postgres:{}@pg/{}'.format(POSTGRES_PASSWORD, DEV_DATABASE)


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = \
        'postgres+psycopg2://postgres:{}@pg/{}'.format(POSTGRES_PASSWORD, DATABASE)


SETTINGS = {
    'sqlite': SQLiteDevelopmentConfig,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
