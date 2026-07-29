from migrate_app import alembic_app
from flask_migrate import migrate

if __name__ == '__main__':
    with alembic_app.app_context():
        # autogenerate a new migration
        migrate(message='autogen: update models')
        print('migrate() completed')
