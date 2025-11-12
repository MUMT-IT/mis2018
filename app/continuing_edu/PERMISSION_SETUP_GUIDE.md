# Continuing Education Admin - Permission Setup Guide

## สรุปการแก้ปัญหา "Forbidden"

เดิม: ระบบใช้ session-based authentication แยกจากระบบหลัก  
ปัญหา: หลังจากย้ายไปใช้ Flask-Login จากระบบ MIS แล้ว ยังไม่มีการตรวจสอบว่า staff มีสิทธิ์เข้า continuing_edu module หรือไม่

## วิธีแก้: ใช้ Flask-Principal Role System ของ MIS

ระบบ MIS มี Role-based Permission พร้อมใช้งานแล้ว ไม่ต้องสร้างตารางใหม่!

### ระบบที่มีอยู่:
- **Flask-Principal** framework สำหรับ permission
- `Role` model และ `user_roles` association table
- Permission decorators: `@admin_permission.require()`, `@hr_permission.require()`, etc.

---

## ขั้นตอนการ Setup (ทำครั้งเดียว)

### 1. สร้าง Role ในฐานข้อมูล

รันคำสั่ง:
```bash
python utils/setup_continuing_edu_admins.py
```

**หรือ** รัน SQL โดยตรง:
```sql
INSERT INTO roles (role_need, action_need, resource_id) 
VALUES ('continuing_edu_admin', NULL, NULL);
```

### 2. เพิ่ม Admin คนแรก

**วิธีที่ 1: แก้ไข setup script**
1. เปิดไฟล์ `utils/setup_continuing_edu_admins.py`
2. แก้ไข list `initial_admins`:
   ```python
   initial_admins = [
       'your.email@mahidol.ac.th',
       'another.admin@mahidol.ac.th',
   ]
   ```
3. รันคำสั่ง: `python utils/setup_continuing_edu_admins.py`

**วิธีที่ 2: ใช้ Flask shell**
```python
flask shell

>>> from app.staff.models import Role, StaffAccount
>>> from app.main import db

>>> # Get the role
>>> role = Role.query.filter_by(role_need='continuing_edu_admin').first()

>>> # Get staff by email
>>> staff = StaffAccount.query.filter_by(email='your.email@mahidol.ac.th').first()

>>> # Assign role
>>> staff.roles.append(role)
>>> db.session.commit()
>>> print(f"✓ Assigned to {staff.fullname}")
```

**วิธีที่ 3: ใช้ SQL โดยตรง**
```sql
-- Find staff_account_id
SELECT id, email, personal_id FROM staff_account WHERE email = 'your.email@mahidol.ac.th';

-- Find role_id
SELECT id FROM roles WHERE role_need = 'continuing_edu_admin';

-- Insert into user_roles
INSERT INTO user_roles (staff_account_id, role_id) 
VALUES (YOUR_STAFF_ID, YOUR_ROLE_ID);
```

### 3. Restart Application

```bash
# ถ้าใช้ Flask development server
Ctrl+C
flask run

# ถ้าใช้ Gunicorn
sudo systemctl restart your-app-service
```

---

## การใช้งาน

### จัดการ Administrators ผ่าน UI

1. Login เข้าระบบ MIS
2. ไปที่ **Continuing Education Admin** → **Settings** → **Administrators**
3. เพิ่ม/ลบผู้ดูแลระบบได้ตามต้องการ

URL: `http://your-site/continuing_edu/admin/settings/administrators`

### สิทธิ์ของ Administrators

ผู้ที่มี `continuing_edu_admin` role จะสามารถ:
- ✅ เข้าถึง Dashboard และรายงานทั้งหมด
- ✅ สร้างและแก้ไขคอร์สอบรม/กิจกรรม
- ✅ จัดการสมาชิกและการลงทะเบียน
- ✅ อนุมัติการชำระเงิน
- ✅ ออกใบเสร็จและใบประกาศนียบัตร
- ✅ ตั้งค่าระบบ
- ✅ จัดการผู้ดูแลคนอื่นๆ

---

## ไฟล์ที่เกี่ยวข้อง

### 1. `/app/roles.py`
เพิ่ม `continuing_edu_admin_role` และ `continuing_edu_admin_permission`

### 2. `/app/continuing_edu/admin/decorators.py`
อัปเดต `@admin_required` ให้ใช้ Flask-Principal permission

### 3. `/utils/setup_continuing_edu_admins.py`
Script สำหรับสร้าง role และเพิ่ม admin คนแรก

### 4. `/app/continuing_edu/admin/admin_management_views.py`
Views สำหรับจัดการ administrators ผ่าน UI

### 5. `/app/templates/continueing_edu/admin/settings_administrators.html`
หน้า UI สำหรับจัดการ administrators

### 6. `/app/continuing_edu/admin/__init__.py`
Blueprint definition และ import views

---

## การทดสอบ

### ทดสอบว่า Permission ทำงาน:

```python
flask shell

>>> from app.staff.models import StaffAccount
>>> from app.roles import continuing_edu_admin_permission

>>> # Get a staff
>>> staff = StaffAccount.query.filter_by(email='test@mahidol.ac.th').first()

>>> # Check if has permission
>>> with continuing_edu_admin_permission.require():
>>>     print("✓ Has permission")
```

### ทดสอบผ่าน Browser:

1. **ไม่มี permission:**
   - Login ด้วย staff ที่ไม่มี role
   - เข้า `/continuing_edu/admin/`
   - ควรได้ 403 Forbidden

2. **มี permission:**
   - Login ด้วย staff ที่มี continuing_edu_admin role
   - เข้า `/continuing_edu/admin/`
   - ควรเห็น Dashboard

---

## Troubleshooting

### ปัญหา: ยังได้ 403 หลังจากเพิ่ม role แล้ว

**วิธีแก้:**
1. ตรวจสอบว่า role ถูกเพิ่มจริง:
   ```sql
   SELECT sa.email, r.role_need 
   FROM staff_account sa
   JOIN user_roles ur ON sa.id = ur.staff_account_id
   JOIN roles r ON ur.role_id = r.id
   WHERE r.role_need = 'continuing_edu_admin';
   ```

2. Logout แล้ว Login ใหม่ (refresh session)

3. Restart application

### ปัญหา: Import error "continuing_edu_admin_permission not found"

**วิธีแก้:**
1. ตรวจสอบว่า role มีในฐานข้อมูล
2. Restart application เพื่อให้ `/app/roles.py` load ใหม่

### ปัญหา: Menu "Administrators" ไม่แสดง

**วิธีแก้:**
1. ตรวจสอบว่า import ใน `__init__.py` ครบถ้วน
2. Clear browser cache
3. Restart application

---

## เปรียบเทียบ Before/After

### Before (Session-based)
```python
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            return redirect(url_for('continuing_edu_admin.login'))
        return f(*args, **kwargs)
    return decorated_function
```

❌ แยกระบบ login จากระบบหลัก  
❌ ไม่มี role management  
❌ ต้องจัดการ session เอง

### After (Flask-Principal)
```python
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        with continuing_edu_admin_permission.require(http_exception=403):
            return f(*args, **kwargs)
    
    return decorated_function
```

✅ ใช้ระบบ login ร่วมกับ MIS  
✅ ใช้ role system มาตรฐาน  
✅ จัดการผ่าน UI ได้

---

## สรุป

### ข้อดี:
1. **ไม่ต้องสร้างตารางใหม่** - ใช้ `roles` table ที่มีอยู่แล้ว
2. **ระบบมาตรฐาน** - ใช้ Flask-Principal เหมือนกับส่วนอื่นของ MIS
3. **จัดการง่าย** - มี UI สำหรับเพิ่ม/ลบ admin
4. **Audit Trail** - ทุก role assignment บันทึกไว้ในฐานข้อมูล
5. **Centralized** - จัดการสิทธิ์ทั้งระบบในที่เดียว

### Next Steps:
1. รัน setup script เพื่อสร้าง role
2. เพิ่ม admin คนแรก
3. Restart application
4. ทดสอบการเข้าถึง
5. เพิ่ม admin คนอื่นๆ ผ่าน UI

---

**หมายเหตุ:** ระบบนี้ใช้ Flask-Principal ที่มีอยู่แล้วใน MIS เหมือนกับ module อื่นๆ เช่น HR, Finance, Procurement ไม่ต้องสร้างระบบ permission ใหม่
