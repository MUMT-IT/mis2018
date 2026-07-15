# Continuing Education Test Cases (System Flow)

## Scope
- Sub-app: `continuing_edu`
- Focus: end-to-end system flow and admin event management flow
- Priority: happy path + high-risk validation and permission checks

## Test Data Setup
- Create at least 2 users:
- `member_a` (new user, no profile)
- `member_b` (profile complete)
- Create at least 2 events:
- `event_free_course` (published, registration open, fee = 0)
- `event_paid_webinar` (published, registration open, paid fee)
- Create admin accounts:
- `admin_editor` (editor role)
- `admin_cert_manager` (certificate_manager role)
- `admin_no_role` (continuing_edu_admin but no event role)

## Member Flow Test Cases

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-M-001 | Register new account | Username/email not used | Open register page, submit required fields | Account created, OTP step shown |
| CE-M-002 | Register duplicate email | Existing user email | Submit registration with duplicate email | Registration blocked, duplicate message shown |
| CE-M-003 | OTP verify success | Pending verification user | Submit correct OTP | User marked verified, redirected to login/home |
| CE-M-004 | OTP verify invalid | Pending verification user | Submit wrong OTP | Verification fails, error message shown |
| CE-M-005 | Login success | Verified user exists | Submit correct username/password | Login success, redirect to requested page/home |
| CE-M-006 | Login invalid password | Verified user exists | Submit wrong password | Login fails, error message shown |
| CE-M-007 | Forgot password request | Existing user | Submit username/email for reset | Reset OTP/token flow started |
| CE-M-008 | Forgot password unknown account | Unknown username/email | Submit reset request | No password change, safe error feedback |
| CE-M-009 | Reset password success | Valid reset token/OTP | Set valid new password | Password updated, can login with new password |
| CE-M-010 | Reset password invalid token | Expired/invalid token | Open set password page and submit | Request rejected, redirected to forgot password |

## Profile Completion Flow

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-P-001 | Enforce profile before event registration | Logged in user with incomplete profile | Access register event URL | Redirected to complete profile |
| CE-P-002 | Complete profile success | Incomplete profile user | Fill required fields and submit | Profile saved, redirected to next target |
| CE-P-003 | Complete profile missing required | Incomplete profile user | Submit without required fields | Validation error shown, profile not saved |
| CE-P-004 | Account settings update | Logged in user | Update account settings fields | Changes persisted and visible on reload |
| CE-P-005 | Address create/update | Logged in user | Add or edit address form | Address persisted and listed in settings |

## Event Discovery and Registration Flow

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-E-001 | View home/index events | Published events exist | Open `/continuing_edu/` | Event cards shown with correct CTA links |
| CE-E-002 | Event detail open | Published event exists | Open course/webinar detail URL | Detail page rendered with correct event info |
| CE-E-003 | Register free event success | Logged in + complete profile + open registration | Submit confirm registration | Registration created, confirmation page shown |
| CE-E-004 | Register paid event create payment | Logged in + complete profile + open registration | Submit confirm registration for paid event | Payment record created, redirected to payment process |
| CE-E-005 | Register when closed | Registration closed | Try register event | Blocked with warning, redirected to detail page |
| CE-E-006 | Duplicate registration blocked | User already registered same event | Try register again | Second registration blocked with warning |

## Payment Flow

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-PAY-001 | Payment page access control | Payment belongs to another user | Access payment URL directly | Access denied or redirected safely |
| CE-PAY-002 | Upload payment slip success | Pending payment for user | Upload valid slip file | Slip saved, status updated (or pending review), success message |
| CE-PAY-003 | Upload payment slip invalid file | Pending payment | Upload disallowed file type | Upload rejected with validation message |
| CE-PAY-004 | Invoice view | Payment exists for user | Open invoice route | Invoice page rendered with payment/event/member data |
| CE-PAY-005 | My payments list | Logged in user with payments | Open my payments | List shows only current user payments and statuses |

## Learning and Certificate Flow

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-L-001 | Course learn access paid-not-approved | Registration exists but payment not approved | Open learn page | Access denied/redirected to payment/event detail |
| CE-L-002 | Course learn access approved | Registration exists with approved payment | Open learn page | Course learn page accessible |
| CE-L-003 | Certificate view before issue | Completed or registered but no certificate issued | Open certificate page | No downloadable certificate shown |
| CE-L-004 | Certificate view after issue | Certificate issued for registration | Open certificate page/PDF | Certificate rendered/downloadable |

## Admin Event Management Flow (Event Edit Tabs)

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-A-001 | Create event step 1 | `admin_editor` logged in | Submit event type + title | Event created and redirected to edit tabs |
| CE-A-002 | Update general quick publish toggle | Event exists | Submit `_quick_publish_toggle=1` | `is_published` updated, success flash |
| CE-A-003 | Update general quick registration toggle | Event exists | Submit `_quick_registration_toggle=1` | `registration_open` updated, success flash |
| CE-A-004 | Update general missing title | Event exists | Submit general form without `title_en` | Validation error, no commit |
| CE-A-005 | Update general invalid CE score | Event exists | Submit `continue_education_score` non-number or out of range | Validation error, no commit |
| CE-A-006 | Update general invalid early bird range | Event exists | Submit `early_bird_end <= early_bird_start` | Validation error, no commit |
| CE-A-007 | Add speaker required fields check | Event exists | Submit speaker form with missing required fields | Validation error, speaker not created |
| CE-A-008 | Attach existing speaker duplicate | Existing event speaker by same email | Attach same profile again | Duplicate blocked with warning |
| CE-A-009 | Add agenda success | Event exists | Submit valid agenda fields with start < end | Agenda created, success flash |
| CE-A-010 | Add agenda invalid time range | Event exists | Submit agenda with end <= start | Validation error, agenda not created |
| CE-A-011 | Update agenda via HTMX | Agenda exists | Submit update with `HX-Request` header | Partial template returned, data updated |
| CE-A-012 | Delete agenda via HTMX | Agenda exists | Delete with `HX-Request` header | Partial template returned, agenda removed |
| CE-A-013 | Add material required fields | Event exists | Submit missing title or URL | Validation error, material not created |
| CE-A-014 | Add fee invalid price | Event exists | Submit negative or non-numeric price | Validation error, fee not created |
| CE-A-015 | Add fee success | Event exists + member type exists | Submit valid member type and price | Fee created, success flash |
| CE-A-016 | Reorder agendas JSON payload | Multiple agendas exist | POST JSON `order` list | Agenda order persisted in given sequence |
| CE-A-017 | Reorder materials form payload | Multiple materials exist | POST `order[]` values | Material order persisted in given sequence |
| CE-A-018 | Update event roles add | Staff exists | Submit role_type + staff_id | Role assignment added and committed |
| CE-A-019 | Update event roles remove | Existing role assignment | Submit `remove_role_*` field | Role assignment removed and committed |
| CE-A-020 | Certificates tab permission denied | Admin without certificate role | Open edit event `tab=certificates` | Access redirected with permission warning |
| CE-A-021 | Issue certificate blocked when not eligible | Registration incomplete/not passed/not paid | Trigger `issue_certificate` without `force` | Issue blocked with warning |
| CE-A-022 | Issue certificate force | Registration exists | Trigger `issue_certificate` with `force=1` | Certificate issued and status updated |
| CE-A-023 | Reset certificate | Certificate already issued | Trigger `reset_certificate` | Certificate reset to pending |

## Security and Permission Checks

| ID | Flow | Preconditions | Steps | Expected Result |
|---|---|---|---|---|
| CE-S-001 | Admin route unauthenticated | Not logged in | Access `/continuing_edu/admin/...` route | Redirect to login |
| CE-S-002 | Admin route without continuing_edu_admin role | Logged in staff without role | Access admin dashboard | 403 forbidden |
| CE-S-003 | Event tab action without event role | Admin logged in but no event role | POST update action on event tab | 403 or blocked by role checks |
| CE-S-004 | Member accesses other member invoice/payment | Logged in as different member | Open payment/invoice by another payment_id | Access blocked/redirected |

## Regression Checklist for Release
- Registration, login, and password reset still work in both `th` and `en`.
- Event registration path works for both free and paid events.
- Payment upload + payment status rendering still works in list and detail pages.
- Admin event edit tabs do not break HTMX partial updates.
- Certificate issue/reset actions do not bypass permission checks.
- No broken links between index, detail, register, payment, and dashboard pages.
