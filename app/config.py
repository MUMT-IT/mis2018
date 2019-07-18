"""
    Config file for the web app.
"""

import os

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class SQLiteDevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///mumtmis.db'


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = \
    'postgres+psycopg2://postgres:genius01@pg/mumtmis_test'


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'postgres+psycopg2://postgres:genius01@pg/mumtmis_dev'


SETTINGS = {
    'sqlite': SQLiteDevelopmentConfig,
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
