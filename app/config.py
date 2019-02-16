import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.urandom(16)
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'postgres+psycopg2://postgres:genius01@pg/mumtmis_dev'


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'postgres+psycopg2://postgres:genius01@pg/mumtmis_dev'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

