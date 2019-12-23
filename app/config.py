"""
    Config file for the web app.
"""

import os


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LINE_CLIENT_ID = os.environ.get('LINE_CLIENT_ID')
    LINE_CLIENT_SECRET = os.environ.get('LINE_CLIENT_SECRET')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')


class DevelopmentConfig(Config):
    DEV_DATABASE = os.environ.get('DEV_DATABASE')
    DEV_DATABASE_HOST = os.environ.get('DEV_DATABASE_HOST', 'pg')
    DEV_DATABASE_PORT = os.environ.get('DEV_DATABASE_PORT', 5432)
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    SQLALCHEMY_DATABASE_URI = \
        'postgres+psycopg2://postgres:{}@{}:{}/{}'.format(POSTGRES_PASSWORD,
                                                          DEV_DATABASE_HOST,
                                                          DEV_DATABASE_PORT,
                                                          DEV_DATABASE)


class ProductionConfig(Config):
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    DATABASE = os.environ.get('DATABASE')
    SQLALCHEMY_DATABASE_URI = \
        'postgres+psycopg2://postgres:{}@pg/{}'.format(POSTGRES_PASSWORD, DATABASE)


SETTINGS = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}
