from flask_principal import Permission
from sqlalchemy.exc import ProgrammingError

from app.main import app
from app.staff.models import Role


# The roles need to be loaded for the admin index view.
with app.app_context():
    # The app failed if the database table does not exist yet.
    try:
        education_role = Role.query.filter_by(role_need='education', action_need=None, resource_id=None).first()
        admin_role = Role.query.filter_by(role_need='admin', action_need=None, resource_id=None).first()
        hr_role = Role.query.filter_by(role_need='hr', action_need=None, resource_id=None).first()
        finance_role = Role.query.filter_by(role_need='finance', action_need=None, resource_id=None).first()
        procurement_role = Role.query.filter_by(role_need='procurement', action_need=None, resource_id=None).first()
        # ot_secretary = Role.query.filter_by(role_need='secretary', action_need='ot', resource_id=None).first()
        procurement_committee_role = Role.query.filter_by(role_need='procurement_committee',
                                                          action_need=None,
                                                          resource_id=None).first()
        head_finance_role = Role.query.filter_by(role_need='head_finance', action_need=None, resource_id=None).first()
        manager_role = Role.query.filter_by(role_need='manager', action_need=None, resource_id=None).first()
        secretary_role = Role.query.filter_by(role_need='secretary', action_need=None, resource_id=None).first()
        center_standardization_product_validation_role = Role.query.filter_by(role_need='center_standardization_product_validation',
                                                                              action_need=None, resource_id=None).first()
    except ProgrammingError:
        education_role = None
        admin_role = None
        hr_role = None
        finance_role = None
        procurement_role = None
        # ot_secretary = Role.query.filter_by(role_need='secretary', action_need='ot', resource_id=None).first()
        procurement_committee_role = None
        head_finance_role = None
        manager_role = None
        secretary_role = None
        center_standardization_product_validation_role = None

    admin_permission = Permission() if not admin_role else Permission(admin_role.to_tuple())
    hr_permission = Permission() if not hr_role else Permission(hr_role.to_tuple())
    finance_permission = Permission() if not finance_role else Permission(finance_role.to_tuple())
    procurement_permission = Permission() if not procurement_role else Permission(procurement_role.to_tuple())
    # ot_secretary_permission = Permission()
    finance_procurement_permission = finance_permission.union(procurement_permission)
    procurement_committee_permission = Permission() if not procurement_committee_role else \
        Permission(procurement_committee_role.to_tuple())
    finance_head_permission = Permission() if not head_finance_role else Permission(head_finance_role.to_tuple())
    manager_permission = Permission() if not manager_role else Permission(manager_role.to_tuple())
    secretary_permission = Permission() if not secretary_role else Permission(secretary_role.to_tuple())
    center_standardization_product_validation_permission = Permission() if not \
        center_standardization_product_validation_role else \
        Permission(center_standardization_product_validation_role.to_tuple())
    education_permission = Permission() if not education_role else Permission(education_role.to_tuple())
