# Member Registration Flow Test Cases
**Test Date:** November 20, 2025
**Test URL:** http://localhost:5000/continuing_edu/register?lang=en

## Test Scenario 1: Manual Registration (Happy Path)

### Test Steps:
1. ✅ Open registration page: `/continuing_edu/register?lang=en`
2. Fill in Account Information:
   - Username: `testuser001`
   - Email: `testuser001@example.com`
   - Password: `TestPass123!`
   - Confirm Password: `TestPass123!`
3. Fill in Personal Information:
   - Title: `Mr.`
   - Full Name (EN): `Test User One`
   - Full Name (TH): `ทดสอบ ผู้ใช้หนึ่ง`
   - Phone: `0812345678`
   - Member Type: Select any
   - Gender: Select any
   - Age Range: Select any
4. Fill in Organization:
   - Organization Name: `Test University`
   - Organization Type: `University`
   - Country: `Thailand`
   - Occupation: `Student`
5. Fill in Address:
   - Address Type: `current`
   - Address Line 1: `123 Test Street`
   - City: `Bangkok`
   - State/Province: `Bangkok`
   - Postal Code: `10110`
   - Country: `Thailand`
6. Accept Policies:
   - ✅ Privacy Policy
   - ✅ Terms and Conditions
   - ✅ Receive News (optional)
7. Anti-Bot Verification:
   - Type: `human` or `มนุษย์`
8. Click "Register" button
9. Verify OTP code is sent to email
10. Enter OTP code
11. Verify successful registration

### Expected Results:
- ✅ All form fields validate correctly
- ✅ No duplicate username/email errors
- ✅ Password matches confirmation
- ✅ Member record created in database
- ✅ Address record created
- ✅ OTP sent successfully
- ✅ Redirect to OTP verification page
- ✅ After OTP: Redirect to login page

---

## Test Scenario 2: Google Sign-up (New User)

### Test Steps:
1. ✅ Open registration page
2. Click "Sign in with Google" button
3. Select Google account
4. Verify JWT token is sent to backend
5. Check redirect to `/complete-profile`
6. Fill in additional profile information:
   - Member Type
   - Gender
   - Age Range
   - Organization
   - Address (optional)
7. Submit profile
8. Verify redirect to home page

### Expected Results:
- ✅ Google authentication successful
- ✅ JWT token verified
- ✅ New Member created with `google_sub`
- ✅ `is_verified = True` (Google pre-verified)
- ✅ Session contains `member_id`
- ✅ Profile completion page shows
- ✅ Profile updates saved to database

---

## Test Scenario 3: Google Sign-up (Existing Email)

### Test Steps:
1. Create member manually first: `testuser002@gmail.com`
2. Try to sign up with same Google account email
3. Verify account linking behavior

### Expected Results:
- ✅ Existing member found by email
- ✅ `google_sub` added to existing account
- ✅ `google_connected_at` timestamp set
- ✅ User logged in automatically
- ✅ No duplicate account created

---

## Test Scenario 4: Validation Errors

### Test Cases:
1. **Empty Username**
   - Leave username blank → Error: "Username required"
   
2. **Duplicate Username**
   - Use existing username → Error: "Username already exists"
   
3. **Duplicate Email**
   - Use existing email → Redirect to "Email already registered" page
   
4. **Password Mismatch**
   - Password: `Test123`
   - Confirm: `Test456`
   - → Error: "Passwords do not match"
   
5. **Missing Privacy Policy**
   - Don't check privacy checkbox → Error: "Please accept privacy policy"
   
6. **Missing Terms**
   - Don't check terms checkbox → Error: "Please accept terms and conditions"
   
7. **Bot Verification Failed**
   - Type anything except "human" or "มนุษย์" → Error: "Please confirm you are not a bot"
   
8. **No Address Provided**
   - Leave all address fields empty → Error: "Please provide at least one address"
   
9. **Custom Organization Type without Name**
   - Select "Other" but leave text empty → Error: "Please specify organization type"

---

## Test Scenario 5: Database Verification

### SQL Queries to Verify:
```python
# Check new member
from app.continuing_edu.models import Member
member = Member.query.filter_by(username='testuser001').first()
print(f"ID: {member.id}")
print(f"Email: {member.email}")
print(f"Is Verified: {member.is_verified}")
print(f"Google Sub: {member.google_sub}")
print(f"Created: {member.created_at}")

# Check address
from app.continuing_edu.models import MemberAddress
addresses = MemberAddress.query.filter_by(member_id=member.id).all()
for addr in addresses:
    print(f"Type: {addr.address_type}, Line1: {addr.line1}")

# Check Google-linked members
google_members = Member.query.filter(Member.google_sub.isnot(None)).all()
for gm in google_members:
    print(f"User: {gm.username}, Google Sub: {gm.google_sub}, Connected: {gm.google_connected_at}")
```

---

## Test Scenario 6: UI/UX Testing

### Checklist:
- [ ] Page loads with modern gradient design
- [ ] Step indicator shows "Step 1: Create Account"
- [ ] Google Sign-in button displays correctly
- [ ] Divider shows "OR" between Google and manual form
- [ ] All form sections are collapsible
- [ ] Input fields have modern styling
- [ ] Password fields show/hide toggle works
- [ ] Dropdown selects populate correctly
- [ ] Address can be added dynamically
- [ ] Error messages display with proper styling
- [ ] Success messages show after registration
- [ ] Loading states work properly
- [ ] Responsive design works on mobile

---

## Test Scenario 7: Email Testing

### Email Templates to Verify:
1. **Registration OTP Email**
   - Subject: "Your Registration OTP Code"
   - Body contains 6-digit code
   - Code format: `000000` to `999999`

2. **Login OTP Email** (for email comeback)
   - Subject: "Your Login OTP Code"
   - Body contains OTP code

3. **Password Reset OTP Email**
   - Subject: "Your Password Reset OTP"
   - Contains expiry notice (10 minutes)

---

## Current Test Status

### ✅ Completed:
- Route `/register` loads successfully (HTTP 200)
- Template `register_modern.html` renders
- Google Client ID configured
- Form structure complete
- Validation logic implemented
- Database schema ready (google_sub, google_connected_at columns exist)

### 🔄 In Progress:
- Manual registration flow testing
- Google OAuth flow testing

### ⏳ Pending:
- Email OTP verification
- Profile completion after Google signup
- Error handling edge cases
- Mobile responsiveness testing

---

## Test Environment Info
- **Python Version:** 3.11
- **Flask Version:** Running in debug mode
- **Database:** PostgreSQL with Alembic migrations
- **Google Client ID:** 206836986017-1dctro1ehrqta2r91e5appn5j78spn9h.apps.googleusercontent.com
- **Base URL:** http://localhost:5000
- **Registration URL:** http://localhost:5000/continuing_edu/register?lang=en
- **Test Page URL:** http://localhost:5000/continuing_edu/test-google-signup

---

## Next Steps for Testing

1. **Manual Test:** Fill out registration form manually and submit
2. **Check Logs:** Monitor Flask terminal for errors
3. **Database Check:** Verify member record created
4. **Email Check:** Confirm OTP sent (check email or logs)
5. **Google Test:** Test Google Sign-in button
6. **Profile Test:** Complete profile after Google signup
7. **Edge Cases:** Test all validation scenarios
