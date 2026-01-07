# GitHub Copilot Instructions for MIS2018

## Project Overview
**MIS2018** is a comprehensive Flask-based Management Information System for Mahidol University Faculty of Medical Technology. It's a **multi-tenant, modular monolith** with 30+ distinct service modules handling everything from staff management and KPIs to procurement, academic services, and continuing education.

## Architecture & Structure

### Modular Blueprint System
- **Main app**: `app/main.py` - central Flask app factory and blueprint registration (1877 lines)
- **Modules**: Each directory under `app/` is an independent service module (e.g., `staff/`, `procurement/`, `continuing_edu/`, `alumni/`)
- **Blueprint pattern**: Each module has `__init__.py` (blueprint definition), `views.py` (routes), `models.py` (SQLAlchemy models), `forms.py` (Flask-WTF forms)
- **URL structure**: All modules registered with prefix, e.g., `/staff/*`, `/procurement/*`, `/continuing_edu/*`
- **Critical**: Blueprints are registered AFTER models are imported in `app/main.py` to ensure Flask-Admin views work correctly

Example from `app/main.py`:
```python
from app.staff import staffbp as staff_blueprint
app.register_blueprint(staff_blueprint, url_prefix='/staff')
```

### Database Architecture
- **ORM**: SQLAlchemy with Flask-SQLAlchemy extension
- **Migrations**: Alembic via Flask-Migrate (commands: `flask db migrate`, `flask db upgrade`)
- **Database**: PostgreSQL in production (see `docker-compose.yml`), configured via `DATABASE_URL` env var
- **CRITICAL URL FIX**: Heroku-style `postgres://` URLs must be converted to `postgresql://` for SQLAlchemy:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('://', 'ql://', 1)
```
- **Shared models**: Core models (`Org`, `Strategy`, `StrategyTactic`, `StrategyTheme`, `StrategyActivity`) live in `app/models.py` and are shared across modules
- **Hierarchical org structure**: `Org` model uses self-referential foreign key (`parent_id`) for organizational hierarchy

### Authentication & Authorization
- **Flask-Login**: Main authentication system using `StaffAccount` model
- **Multiple login contexts**: Blueprint-aware authentication - different blueprints use different user models
- **User loader**: Context-aware user loading in `app/main.py`:
```python
@login.user_loader
def load_user(user_id):
    if request.blueprint == 'academic_services':
        return ServiceCustomerAccount.query.get(int(user_id))
    else:
        return StaffAccount.query.get(int(user_id))
```
- **Login view mapping**: Different blueprints have different login pages via `login.blueprint_login_views`
- **Flask-Principal**: Role-based permissions defined in `app/roles.py`
- **Permissions**: Loaded from database `Role` model at app startup with error handling for missing tables
- **Permission checking**: Use `admin_permission.require()` decorator or `.can()` method from `app.roles`
- **Permission types**: `admin_permission`, `hr_permission`, `finance_permission`, `procurement_permission`, `secretary_permission`, etc.

## Code Conventions

### Python Style
- **Standard**: PEP 8, snake_case for functions/variables, PascalCase for classes
- **Encoding**: ALWAYS include UTF-8 encoding header for Thai language support:
```python
# -*- coding:utf-8 -*-
```
- **Imports**: Group by standard lib → third-party → local
- **Timezone**: ALWAYS use Asia/Bangkok timezone from pytz (NEVER use naive datetimes):
```python
from pytz import timezone
tz = timezone('Asia/Bangkok')
# Localize naive datetime
aware_dt = tz.localize(datetime.now())
```

### Models (SQLAlchemy)
- Inherit from `db.Model` (imported from `app.main`)
- Use `server_default=func.now()` for timestamps (NOT `default=datetime.now()`)
- **Relationship pattern**: Use `back_populates` for bidirectional clarity OR `backref` for cascade deletion:
```python
org = db.relationship('Org', backref=db.backref('strategies', cascade='all, delete-orphan'))
```
- Add `__repr__` and `__str__` methods for debugging and Flask-Admin display
- Association tables use `db.Table()` for many-to-many relationships
- **Column naming**: Use descriptive names with underscore separators

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
    
    def __str__(self):
        return self.name
```

### Forms (Flask-WTF)
- Inherit from `FlaskForm`
- Define validators inline: `validators=[DataRequired(), Email()]`
- CSRF protection enabled by default (configured in `app/main.py`)
- Forms live in `forms.py` within each module

### Views (Flask Blueprints)
- Blueprint naming: `<module>bp` or `<module>_bp`, e.g., `staffbp`, `procurement_blueprint`
- Import from module's `__init__.py`
- Route decorators: Use explicit `methods=['GET', 'POST']`
- **POST-Redirect-GET pattern**: Always redirect after POST to prevent double submissions
- Flash messages: Use `flash()` for user feedback with Thai messages
- Template context: Pass data as explicit keyword arguments to `render_template()`
- **Large view files**: Some modules (e.g., `staff/views.py` ~4880 lines, `continuing_edu/views.py` ~2000 lines) - be cautious with large edits

### Templates (Jinja2)
- **CSS Framework**: Uses **Bulma CSS exclusively** (not Bootstrap/Tailwind)
- Base template: `app/templates/base.html` - includes Bulma, FontAwesome, DataTables, SweetAlert2
- Template structure: Modules have templates in `app/templates/<module_name>/`
- **Blocks**: `{% block title %}`, `{% block content %}`, `{% block scripts %}`
- **Icons**: FontAwesome classes: `<i class="fas fa-icon-name"></i>`
- **Thai/English support**: Many templates support bilingual content via context variables or translations dictionaries (see `continuing_edu/__init__.py`)

### Frontend Stack
- **Bulma CSS**: Primary styling framework (v0.9.23+ with Buefy components)
- **JavaScript libraries**: Vue.js (Buefy), jQuery, DataTables, SweetAlert2, HTMX, Shepherd.js, FullCalendar Scheduler
- **HTMX**: Used for dynamic updates without page reload
- **DataTables**: Standard for table listings with Bulma theme
- **Template filters**: Custom Jinja2 filters in `app/main.py` for date formatting (`localdate`, `localdatetime`, `humanizedt`), money formatting, Thai language support

## Development Workflow

### Running Locally
1. **Environment setup**: Check `web_variables.env` for required environment variables (no `.env.example` exists)
2. **Install dependencies**: `pip install -r requirements.txt` (Python 3.9)
3. **Database setup**: Ensure PostgreSQL running, then `flask db upgrade`
4. **Run app**: `python app/main.py` or `gunicorn app.main:app`
5. **Worker process**: `python app/jobs.py` for scheduled tasks (APScheduler)

### Docker Development
- **Compose file**: `docker-compose.yml` defines `web`, `pg`, `nginx`, `traefik` services
- **Build**: `docker-compose build`
- **Run**: `docker-compose up`
- **Ports**: 
  - 3330: Flask app direct (mapped to container port 5000)
  - 3331: Nginx proxy
  - 3332/3333: Traefik HTTP/HTTPS
  - 3334: Traefik dashboard
  - 3335: PostgreSQL
- **Volumes**: Source code mounted for development (`./app:/mis2018/app`)
- **Dockerfile**: Uses Python 3.9 base, gunicorn with 5 workers and 12 threads

### Production Deployment
- **Heroku**: Uses `Procfile` with two processes:
  - `web`: gunicorn app.main:app --max-requests 1000
  - `clock`: python app/jobs.py (APScheduler for notifications)
- **Max requests**: Configured to restart workers after 1000 requests to prevent memory leaks

### Database Migrations
```bash
# Create migration
flask db migrate -m "Description of changes"

# Review migration file in migrations/versions/
# Apply migration
flask db upgrade
```

### Custom CLI Commands
- **Database utilities**: `flask dbutils <command>` - extensive custom commands in `app/main.py`
  - `import-leave-data`, `import-procurement-data`, `calculate-leave-quota`, `update-staff-leave-info`
  - `add-update-staff-gsheet` - Google Sheets integration
  - Many data import/migration commands for historical data
- **Population commands**: `flask populate-provinces`, `flask populate-districts`, `flask populate-subdistricts`

### Admin Interface
- **Flask-Admin**: Available at `/admin` (requires `admin_permission` from `app.roles`)
- **Custom index view**: `MyAdminIndexView` checks authentication and admin permission
- **Model registration**: Extensive model registration in `app/main.py` after blueprint imports (grouped by category)
- **Custom model views**: Many modules define custom `ModelView` subclasses for form customization
```python
class MyProcurementModelView(ModelView):
    form_excluded_columns = ('qrcode', 'records', 'repair_records')

admin.add_views(MyProcurementModelView(ProcurementDetail, db.session, category='Procurement'))
```

## Integration Points

### External Services
- **Email**: Flask-Mail with SMTP Gmail (configure `MAIL_USERNAME`, `MAIL_PASSWORD`)
  - Default sender: `('MUMT-MIS', MAIL_USERNAME)`
  - Used for notifications, password resets, approvals
- **LINE Bot**: LINE messaging API for notifications and authentication
  - Config: `LINE_CLIENT_ID`, `LINE_CLIENT_SECRET`, `LINE_MESSAGE_API_ACCESS_TOKEN`, `LINE_MESSAGE_API_CLIENT_SECRET`
  - Used in staff module for leave approval notifications
  - Error handling: Catches `LineBotApiError` and shows warning flash message
- **Google Drive**: PyDrive for file uploads (requires `JSON_KEYFILE` env var pointing to credentials JSON URL)
  - Service account authentication pattern used throughout
  - Used in staff module for document storage
- **S3-compatible storage**: Boto3 for file storage
  - Config: `S3_BUCKET_NAME`, AWS credentials
  - Used in `continuing_edu` for payment proofs and certificates
  - Pattern: `s3.put_object(Bucket=S3_BUCKET_NAME, Key=key, Body=data, ContentType=content_type)`
- **Payment**: SCB payment service integration in `app/scb_payment_service/`
  - JWT-based API authentication
  - Custom user lookup callback for API clients

### Google Sheets Integration
- Uses gspread with service account credentials
- Credentials fetched from URL at startup: `requests.get(os.environ.get('JSON_KEYFILE')).json()`
- Pattern in `app/main.py`:
```python
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(json_keyfile, scope)
gc = gspread.authorize(credentials)
```
- Used extensively in CLI commands for data import/export

### Scheduled Jobs (APScheduler)
- **Worker process**: `app/jobs.py` runs as separate Heroku clock process
- **Jobs configured**:
  - Event notifications: Mon-Fri 8:00 AM
  - Room booking notifications: Today at 7:00 AM, tomorrow at 3:00 PM
- **Pattern**: Uses `BlockingScheduler` with cron triggers

## Module-Specific Notes

### Staff Module (`app/staff/`)
- **Core user management**: `StaffAccount` and `StaffPersonalInfo` models
- **Features**: Leave requests, work-from-home, seminars, performance evaluations, shift schedules
- **Leave system**: Complex quota calculation with fiscal year logic (Oct 1 - Sep 30)
  - `StaffLeaveUsedQuota` tracks usage per fiscal year
  - `StaffLeaveRemainQuota` for historical carryover
  - CLI commands for quota calculation and updates
- **Approver hierarchy**: Multi-level approval system (`StaffLeaveApprover`, `StaffLeaveApproval`)
- **Views file**: ~4880 lines - use targeted searches before editing
- **Flash messages**: Extensive Thai language validation messages
- **Google Drive**: Integration for document uploads

### Continuing Education (`app/continuing_edu/`)
- **Separate documentation**: See `app/continuing_edu/.github/copilot-instructions.md` (595 lines)
- **Dual authentication**: Member accounts separate from StaffAccount
- **Admin structure**: Separate admin blueprint under `continuing_edu/admin/`
- **Payment workflow**: Registration → Payment → Receipt → Certificate
- **S3 storage**: Payment proofs and certificates
- **Multilingual**: Translation dictionaries in `__init__.py`

#### Module continue_edu — สรุปสิ่งที่สร้างแล้ว
- 1. แก้ไข `confirm_registration` route ใน `views.py`:
  - เพิ่มการรับค่า `payment_method` และ `terms_accepted` จากฟอร์ม
  - ตรวจสอบว่าผู้ใช้ยอมรับข้อตกลงหรือไม่
  - Redirect ไปยัง `payment_process` พร้อมส่ง `payment_method` ผ่าน query parameter
- 2. สร้าง route `payment_process`:
  - แสดงหน้าขั้นตอนการชำระเงินตาม `payment_method` ที่เลือก
  - รองรับ 4 วิธี: PromptPay, Bank Transfer, Credit Card, Counter Service
- 3. สร้าง route `upload_payment_slip`:
  - รับไฟล์สลิปการโอนเงิน
  - อัปเดตสถานะเป็น "รอตรวจสอบ" (verifying)
- 4. สร้าง route `process_credit_card`:
  - รับข้อมูลบัตรเครดิต
  - จำลองการชำระเงิน (TODO: ต่อกับ payment gateway จริง)
  - อัปเดตสถานะเป็น "ชำระแล้ว" (paid)
- 5. สร้างเทมเพลต `payment_process.html`:
  - PromptPay:
    - แสดง QR Code สำหรับสแกน
    - แสดงหมายเลข PromptPay ID
    - 4 ขั้นตอน: เปิดแอป → สแกน → ยืนยัน → รอตรวจสอบ
  - Bank Transfer:
    - แสดงรายละเอียดบัญชีธนาคาร
    - ปุ่มคัดลอกข้อมูล
    - ฟอร์มอัพโหลดสลิป
    - 3 ขั้นตอน: โอนเงิน → อัพโหลด → รอตรวจสอบ
  - Credit Card:
    - ฟอร์มกรอกข้อมูลบัตร (หมายเลข, ชื่อ, วันหมดอายุ, CVV)
    - Auto-format หมายเลขบัตรและวันหมดอายุ
    - 4 ขั้นตอน: กรอกข้อมูล → ยืนยัน OTP → ประมวลผล → รับใบเสร็จ
  - Counter Service:
    - แสดงรหัสชำระเงิน (Payment Code)
    - ปุ่มพิมพ์รหัส
    - ฟอร์มอัพโหลดใบเสร็จ
    - 4 ขั้นตอน: พิมพ์รหัส → ชำระที่เคาน์เตอร์ → รับใบเสร็จ → อัพโหลด

### Procurement (`app/procurement/`)
- **Equipment tracking**: QR code generation and scanning
- **Committee approvals**: Multi-stakeholder approval workflow
- **Borrow/return system**: `ProcurementBorrowDetail` and `ProcurementBorrowItem`
- **Computer inventory**: Detailed IT asset tracking with specs
- **Image storage**: Base64-encoded images in database (historical pattern)
- **Data import**: CLI commands for bulk import from Google Sheets

### KPI Module (`app/kpi/`)
- **Strategic hierarchy**: Strategy → Tactic → Theme → Activity (all in `app/models.py`)
- **Organizational linkage**: Each strategy linked to `Org` model
- **Cascading structure**: Parent-child relationships throughout hierarchy
- **Active flag**: All hierarchy models have `active` field for soft deletion
- **Reference numbers**: Each level has `refno` field for structured identification

### Academic Services (`app/academic_services/`)
- **Customer authentication**: Uses `ServiceCustomerAccount` instead of `StaffAccount`
- **Service workflow**: Request → Quotation → Invoice → Payment → Receipt
- **Lab structure**: `ServiceLab` → `ServiceSubLab` → `ServiceItem`
- **Admin roles**: `ServiceAdmin` model for access control

### Common Health (`app/comhealth/`)
- **Test profiles**: Hierarchical test organization (`ComHealthTestProfile`, `ComHealthTestItem`)
- **Customer management**: Organizations, employment types, groups
- **Specimen workflow**: Check-in, testing, results
- **Consent management**: PDPA compliance tracking
- **Finance tracking**: Invoice, receipt, contact reasons

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
