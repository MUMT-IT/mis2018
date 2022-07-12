from flask_principal import Permission
from app.staff.models import Role
from app.main import app

with app.app_context():
    admin_role = Role.query.filter_by(role_need='admin',
                                      action_need=None,
                                      resource_id=None).first()

    hr_role = Role.query.filter_by(role_need='hr',
                                   action_need=None,
                                   resource_id=None).first()

if admin_role:
    admin_permission = Permission(admin_role.to_tuple())

if hr_role:
    hr_permission = Permission(hr_role.to_tuple())


