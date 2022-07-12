from flask_principal import Permission
from app.staff.models import Role
from app.main import app

with app.app_context():
    admin_role = Role.query.filter_by(role_need='admin',
                                      action_need=None,
                                      resource_id=None).first()

    hr_role = Role.query.filter_by(role_need='hr',
                                   action_need=None, resource_id=None).first()

    finance_role = Role.query.filter_by(role_need='finance',
                                        action_need=None, resource_id=None).first()

    procurement_role = Role.query.filter_by(role_need='procurement',
                                            action_need=None, resource_id=None).first()

if admin_role:
    admin_permission = Permission(admin_role.to_tuple())

if hr_role:
    hr_permission = Permission(hr_role.to_tuple())


if finance_role:
    finance_permission = Permission(finance_role.to_tuple())

if procurement_role:
    procurement_permission = Permission(procurement_role.to_tuple())

if finance_role and procurement_role:
    finance_procurement_permission = finance_permission.union(procurement_permission)


