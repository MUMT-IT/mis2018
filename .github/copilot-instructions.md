## GitHub Copilot instructions (MIS2018)

### Big picture
- Flask “modular monolith”: each folder under `app/` is a service-style module (e.g. `app/staff/`, `app/procurement/`, `app/continuing_edu/`) with its own `models.py`/`views.py`/`forms.py` patterns.
- Main entrypoint is `app/main.py`: creates the app (`create_app()`), initializes extensions (SQLAlchemy/Migrate/Login/JWT/Admin/CSRF/etc), then registers many blueprints and Flask-Admin views.

### Local run / Docker
- Docker is the intended dev workflow: `docker-compose.yml` runs `web` + Postgres (`pg`) and exposes Flask at `http://localhost:3330`.
- `docker-compose.yml` references `web_variables.env` but it is NOT committed — you must create it locally with required env vars.
- Production uses `Procfile`: `web` runs `gunicorn app.main:app`; `clock` runs `python app/jobs.py` (APScheduler hitting `/linebot/...` endpoints).

### Config gotchas (important for agents)
- `create_app()` requires `DATABASE_URL` and immediately does `os.environ.get('DATABASE_URL').replace('://', 'ql://', 1)`; if `DATABASE_URL` is missing, importing `app.main` will crash.
- `app/main.py` fetches Google service-account credentials at import time: `json_keyfile = requests.get(os.environ.get('JSON_KEYFILE')).json()`; set `JSON_KEYFILE` (URL returning JSON) before imports.

### Data layer & migrations
- ORM is Flask-SQLAlchemy; shared/core models live in `app/models.py` (e.g. `Org`, `Strategy*`, address tables).
- Alembic/Flask-Migrate is configured in `migrations/`; typical flow is `FLASK_APP=app.main:app flask db upgrade/migrate`.
- There are many one-off import/maintenance commands in the `dbutils` CLI group inside `app/main.py` (e.g. `flask dbutils import-leave-data`).

### Auth/permissions conventions
- Flask-Login `user_loader` is blueprint-aware: `academic_services` loads a different account model than the default `StaffAccount` (see `app/main.py`).
- Role/permission checks are via Flask-Principal; `admin_permission` lives in `app/roles.py` and gates `/admin` (see `MyAdminIndexView` in `app/main.py`).

### Frontend conventions
- Templates use Bulma/Buefy and are rooted at `app/templates/` (base shell: `app/templates/base.html`).
- Continuing education templates are under the misspelled folder `app/templates/continueing_edu/` (note the extra “e”).

### Integrations you’ll run into
- Email: Flask-Mail (Gmail SMTP) configured in `create_app()`.
- LINE: `/linebot` blueprint for notifications and login flows.
- S3 storage: boto3 client configured from Bucketeer env vars (`BUCKETEER_*`) in `app/main.py`; continuing education uses it for certificates/materials.
- PDFs: some flows optionally use WeasyPrint (guarded import in `app/continuing_edu/views.py`).

### Module-specific instructions
- Continuing education has deep, module-specific guidance in `app/continuing_edu/.github/copilot-instructions.md` — consult that when working in `app/continuing_edu/` or `app/templates/continueing_edu/`.

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
