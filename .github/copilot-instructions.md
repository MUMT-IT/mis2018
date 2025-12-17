# GitHub Copilot Instructions for MIS2018

## Project Overview
**MIS2018** is a comprehensive Flask-based Management Information System for Mahidol University Faculty of Medical Technology. It's a **multi-tenant, modular monolith** with 30+ distinct service modules handling everything from staff management and KPIs to procurement, academic services, and continuing education.

## Architecture & Structure

### Modular Blueprint System
- **Main app**: `app/main.py` - central Flask app factory and blueprint registration
- **Modules**: Each directory under `app/` is an independent service module (e.g., `staff/`, `procurement/`, `continuing_edu/`, `alumni/`)
- **Blueprint pattern**: Each module has `__init__.py` (blueprint definition), `views.py` (routes), `models.py` (SQLAlchemy models), `forms.py` (Flask-WTF forms)
- **URL structure**: All modules registered with prefix, e.g., `/staff/*`, `/procurement/*`, `/continuing_edu/*`

Example from `app/main.py`:
```python
from app.staff import staffbp as staff_blueprint
app.register_blueprint(staff_blueprint, url_prefix='/staff')
```

### Database Architecture
- **ORM**: SQLAlchemy with Flask-SQLAlchemy extension
- **Migrations**: Alembic via Flask-Migrate (commands: `flask db migrate`, `flask db upgrade`)
- **Database**: PostgreSQL in production (see docker-compose.yml), configured via `DATABASE_URL` env var
- **Key pattern**: URL fix in main.py converts `postgres://` to `postgresql://` for SQLAlchemy compatibility
```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('://', 'ql://', 1)
```

### Authentication & Authorization
- **Flask-Login**: Main authentication system using `StaffAccount` model
- **Multiple login contexts**: Some blueprints (e.g., `academic_services`) use separate customer accounts
- **User loader**: Blueprint-aware user loading in `app/main.py`:
```python
@login.user_loader
def load_user(user_id):
    if request.blueprint == 'academic_services':
        return ServiceCustomerAccount.query.get(int(user_id))
    else:
        return StaffAccount.query.get(int(user_id))
```
- **Flask-Principal**: Role-based permissions defined in `app/roles.py`
- **Permission checking**: Use `admin_permission.require()` or `.can()` methods from `app.roles`
- **Decorator**: `@login_required` for authenticated routes

## Code Conventions

### Python Style
- **Standard**: PEP 8, snake_case for functions/variables, PascalCase for classes
- **Imports**: Group by standard lib → third-party → local, UTF-8 encoding header for Thai support
```python
# -*- coding:utf-8 -*-
```
- **Timezone**: Always use Asia/Bangkok timezone from pytz
```python
from pytz import timezone
tz = timezone('Asia/Bangkok')
```

### Models (SQLAlchemy)
- Inherit from `db.Model` (imported from `app.main`)
- Use `server_default=func.now()` for timestamps (not `default=datetime.now()`)
- Define relationships with `back_populates` for bidirectional clarity
- Add `__repr__` and `__str__` methods for debugging
- Association tables use `db.Table()` for many-to-many relationships

Example pattern:
```python
from app.main import db
from sqlalchemy.sql import func

class ModelName(db.Model):
    __tablename__ = 'table_name'
    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime(), server_default=func.now())
    org_id = db.Column(db.Integer(), db.ForeignKey('orgs.id'))
    org = db.relationship('Org', backref=db.backref('related_items', cascade='all, delete-orphan'))
```

### Forms (Flask-WTF)
- Inherit from `FlaskForm`
- Define validators inline: `validators=[DataRequired(), Email()]`
- CSRF protection enabled by default
- Forms live in `forms.py` within each module

### Views (Flask Blueprints)
- Blueprint naming: `<module>bp` or `<module>_bp`, e.g., `staffbp`, `procurement_blueprint`
- Import from module's `__init__.py`
- Route decorators: Use explicit `methods=['GET', 'POST']`
- **POST-Redirect-GET**: Always redirect after POST to prevent double submissions
- Flash messages: Use `flash()` for user feedback (categories: success, warning, error, info)
- Template context: Pass data as explicit keyword arguments to `render_template()`

### Templates (Jinja2)
- **CSS Framework**: Uses **Bulma CSS exclusively** (not Bootstrap/Tailwind)
- Base template: `app/templates/base.html` - includes Bulma, FontAwesome, DataTables, SweetAlert2
- Template structure: Modules have templates in `app/templates/<module_name>/`
- **Blocks**: `{% block title %}`, `{% block content %}`, `{% block scripts %}`
- **Icons**: FontAwesome classes: `<i class="fas fa-icon-name"></i>`
- **Thai/English support**: Many templates support multilingual content via context variables

### Frontend Stack
- **Bulma CSS**: Primary styling framework (v0.9.23+ with Buefy components)
- **JavaScript libraries**: Vue.js (Buefy), jQuery, DataTables, SweetAlert2, HTMX, Shepherd.js
- **HTMX**: Used for dynamic updates without page reload
- **DataTables**: Standard for table listings with Bulma theme

## Development Workflow

### Running Locally
1. **Environment setup**: Copy `.env.example` (or check `web_variables.env` for required vars)
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Database setup**: Ensure PostgreSQL running, then `flask db upgrade`
4. **Run app**: `python app/main.py` or `gunicorn app.main:app`

### Docker Development
- **Compose file**: `docker-compose.yml` defines `web`, `pg`, `nginx`, `traefik` services
- **Build**: `docker-compose build`
- **Run**: `docker-compose up`
- **Ports**: 
  - 3330: Flask app direct
  - 3331: Nginx proxy
  - 3332/3333: Traefik HTTP/HTTPS
  - 3335: PostgreSQL

### Database Migrations
```bash
# Create migration
flask db migrate -m "Description of changes"

# Review migration file in migrations/versions/
# Apply migration
flask db upgrade
```

### Admin Interface
- **Flask-Admin**: Available at `/admin` (requires admin permission)
- **Model registration**: See examples in `app/main.py` after blueprint imports
```python
admin.add_views(ModelView(ModelName, db.session, category='CategoryName'))
```

## Integration Points

### External Services
- **Email**: Flask-Mail with SMTP Gmail (configure `MAIL_USERNAME`, `MAIL_PASSWORD`)
- **LINE Bot**: LINE messaging API for notifications (`LINE_CLIENT_ID`, `LINE_CLIENT_SECRET`, `LINE_MESSAGE_API_ACCESS_TOKEN`)
- **Google Drive**: PyDrive for file uploads (requires `JSON_KEYFILE` env var with credentials URL)
- **S3-compatible storage**: Boto3 for file storage (certificates, documents)
- **Payment**: SCB payment service integration in `app/scb_payment_service/`

### Google Sheets Integration
- Uses gspread with service account credentials
- Pattern in `app/main.py`:
```python
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
gc = gspread.authorize(credentials)
```

## Module-Specific Notes

### Staff Module (`app/staff/`)
- Core user management with `StaffAccount` model
- Handles leave requests, seminars, performance evaluations
- Extensive views file (3000+ lines) - consider context before editing

### Continuing Education (`app/continuing_edu/`)
- Has its own detailed instructions at `app/continuing_edu/.github/copilot-instructions.md`
- Separate member authentication system
- Admin area with tabbed event management interface

### Procurement (`app/procurement/`)
- Equipment tracking with QR codes
- Committee approvals workflow
- Borrow/return system

### KPI Module (`app/kpi/`)
- Strategic planning hierarchy: Strategy → Tactic → Theme → Activity
- Cascading KPIs linked to organizational structure (`Org` model)

## Common Patterns

### Querying Database
```python
# Single result
item = Model.query.filter_by(id=1).first()  # Returns None if not found
item = Model.query.get(1)  # By primary key
item = Model.query.get_or_404(1)  # 404 if not found

# Multiple results
items = Model.query.filter_by(active=True).all()
items = Model.query.filter(Model.created_at >= start_date).all()

# Relationships
org = Org.query.get(1)
staff_members = org.staff  # Via relationship
```

### Error Handling
- Custom error handlers in `app/main.py` for 404, 500, 403 (PermissionDenied)
- Use try/except around `db.session.commit()` for database operations

### Session Management
```python
db.session.add(new_object)
db.session.commit()  # Commit after changes
db.session.rollback()  # On error
```

## Testing & Debugging
- Test scripts exist (e.g., `test_registration.sh`, `test_registration_flow.md`)
- Manual test HTML files for specific features
- Flask debug mode: Set `FLASK_ENV=development`
- Logs: Check `flask.log` in project root

## Important Files
- `app/main.py`: Application factory, blueprint registration, extensions initialization
- `app/models.py`: Shared models (Org, Strategy hierarchy, Risk models)
- `app/roles.py`: Permission definitions
- `requirements.txt`: Python dependencies (Flask 2.2.5, SQLAlchemy, many extensions)
- `docker-compose.yml`: Multi-container setup
- `migrations/`: Alembic migrations directory

## Notes
- **Legacy code**: Some modules have commented-out code (e.g., food module) - check before uncommenting
- **Thai language**: Many strings and comments in Thai - maintain bilingual support where present
- **Large views files**: Some views.py files exceed 1000 lines - be cautious with large edits
- **URL prefix consistency**: All module URLs follow `/module_name/` pattern
