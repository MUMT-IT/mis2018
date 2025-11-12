# GitHub Copilot Instructions for Continuing Education Module

## Project Context
This is a Flask-based continuing education platform for Mahidol University Faculty of Medical Technology. The module handles online courses, webinars, member registration, payments, and certificate management.

## Technology Stack
- **Backend**: Flask (Python), SQLAlchemy ORM, Flask-WTF
- **Frontend**: Bulma CSS, Jinja2 templates, Vanilla JavaScript
- **Database**: PostgreSQL (production), SQLite (development)
- **Authentication**: Custom member authentication + StaffAccount for admin
- **File Storage**: S3-compatible storage for images, materials, certificates

## Code Style & Conventions

### Python/Flask
- Use snake_case for functions, variables, and file names
- Use PascalCase for class names
- Follow PEP 8 style guide
- Use type hints where appropriate
- Prefer explicit over implicit
- Keep functions focused and under 50 lines when possible

### Models (app/continuing_edu/models.py)
- All models inherit from `db.Model`
- Use lookup tables for enums (e.g., `MemberType`, `Gender`, `RegistrationStatus`)
- Use relationships with `back_populates` for bidirectional references
- Add docstrings for complex models
- Use `server_default=db.func.now()` for timestamps
- Include `__repr__` methods for debugging

### Forms (app/continuing_edu/forms.py)
- Use Flask-WTF for all forms
- Inherit from `FlaskForm`
- Add validators inline with field definitions
- Use DataRequired() for required fields
- Add custom validators when needed
- Keep form classes in forms.py, not in views

### Views (app/continuing_edu/views.py & admin/views.py)
- Use blueprints for route organization
- Main blueprint: `continuing_edu_bp`
- Admin blueprint: `admin_bp` (under continuing_edu/admin/)
- Use `@bp.route()` decorator with explicit methods
- Check authentication at the start of protected routes
- Use `flash()` for user feedback messages
- Return `redirect()` after POST operations
- Use `render_template()` with explicit context variables

### Templates (app/templates/continueing_edu/)
- Use Bulma CSS classes exclusively (no Bootstrap or Tailwind)
- Extend base templates: `base.html` for public, `admin/base.html` for admin
- Use `{% block content %}` for main content
- Use `{% block scripts %}` for page-specific JavaScript
- Implement responsive design with Bulma's responsive classes
- Use `data-aos` attributes for scroll animations
- Keep inline styles minimal, prefer CSS classes
- Use FontAwesome icons via `<i class="fas fa-icon-name"></i>`

### Multilingual Support
- Support Thai (`th`) and English (`en`) languages
- Store translations in view context as `texts` dictionary
- Use `{{ texts.key_name }}` in templates
- Accept `lang` parameter in routes: `@bp.route('/<lang>/path')`
- Default to Thai if language not specified
- Store current language in `current_lang` template variable

### Database Patterns
- Use `db.session.add()` for new objects
- Use `db.session.commit()` after changes
- Use `.query.filter_by()` for simple queries
- Use `.query.filter()` for complex queries
- Use `.first()` for single results, `.all()` for lists
- Use `.get_or_404(id)` for retrieving by primary key
- Handle exceptions with try/except around commits

### Admin Features
- Admin area is a separate blueprint under `continuing_edu/admin/`
- Authentication uses `StaffAccount` model
- Check admin session with `get_current_admin()` helper
- Admin templates extend `admin/base.html`
- Admin routes prefix: `/continuing_edu/admin/`
- Dashboard shows summary cards and latest data tables
- Use modals for quick actions, separate pages for complex forms

#### Admin Course Management Flow

**1. Create New Event/Course**
```
Step 1: Event Type & Basic Info
- Route: /continuing_edu/admin/events/create
- Select event_type (course/webinar) via card selection
- Enter title_en and title_th
- Create EventEntity record with minimal info
- Redirect to edit page with tabs

Step 2: Complete Event Details (Tabbed Interface)
- Route: /continuing_edu/admin/events/<event_id>/edit
- Tab 1: General Info
  * Description (Thai/English)
  * Category, format, duration, location
  * Certificate type, continuing education score
  * Creating institution, department
  * Course code (optional)
  * Images (cover, poster)
  
- Tab 2: Schedule & Agenda
  * Add multiple EventAgenda items
  * Each with title, description, start_time, end_time, order
  * Inline add/edit/delete functionality
  
- Tab 3: Speakers/Lecturers
  * Add multiple EventSpeaker items
  * Name (Thai/English), title, position
  * Email, phone, institution
  * Bio, profile image URL
  
- Tab 4: Materials
  * Add multiple EventMaterial items
  * Upload files to S3
  * Title, description, display order
  
- Tab 5: Registration Fees
  * Add multiple EventRegistrationFee items
  * Different prices for each MemberType
  * Early bird pricing with dates
  
- Tab 6: Staff Assignments
  * Assign EventEditor (can modify event)
  * Assign EventRegistrationReviewer (approve registrations)
  * Assign EventPaymentApprover (approve payments)
  * Assign EventReceiptIssuer (issue receipts)
  * Assign EventCertificateManager (issue certificates)
  * Search and add staff by name/email

Step 3: Publish/Activate Event
- Set event status to active
- Make visible on public course listing
- Send notifications to interested members (optional)
```

**2. Manage Registrations**
```
Route: /continuing_edu/admin/registrations
- View all MemberRegistration records
- Filter by: event, status, date range, member type
- Bulk actions: approve, reject, export

For Each Registration:
- View member details (name, email, member type)
- View registration date and status
- Check payment status
- Update registration status (registered, confirmed, cancelled)
- Add notes/remarks
- View attendance tracking
- View test scores (pre/post test)

Actions:
1. Approve Registration
   - Change status to 'confirmed'
   - Send confirmation email
   - Add to event participant list

2. Reject Registration
   - Change status to 'rejected'
   - Provide rejection reason
   - Send notification email
   - Refund payment if applicable

3. Cancel Registration
   - Change status to 'cancelled'
   - Update available seats
   - Process refund workflow
```

**3. Manage Payments**
```
Route: /continuing_edu/admin/payments
- View all RegisterPayment records
- Filter by: event, status, date range, amount
- Sort by: date, amount, member name

For Each Payment:
- View payment proof image (uploaded by member)
- View payment amount, date, transaction ID
- View member information
- Check payment status

Actions:
1. Approve Payment
   - Verify payment proof
   - Update payment_status to 'paid'
   - Set approved_by_staff_id and approval_date
   - Update registration status to 'confirmed'
   - Send payment confirmation email
   - Auto-issue receipt (optional)

2. Reject Payment
   - Update payment_status to 'rejected'
   - Provide rejection reason
   - Request new payment proof
   - Send notification email

3. Issue Receipt
   - Create RegisterPaymentReceipt record
   - Generate receipt number (auto-increment)
   - Generate PDF receipt
   - Upload to S3 and store URL
   - Send receipt to member email
```

**4. Track Attendance**
```
Route: /continuing_edu/admin/events/<event_id>/attendance
- List all registered members
- Mark attendance per session
- Update attendance_count
- Track total_hours_attended
- Real-time check-in via QR code (optional)

Methods:
1. Manual Entry
   - Admin marks attendance checkbox
   - Enter hours attended
   - Add remarks

2. QR Code Check-in
   - Generate unique QR code per member
   - Member scans QR on arrival
   - Auto-update attendance record

3. Bulk Import
   - Upload CSV with member IDs
   - Bulk update attendance records
```

**5. Manage Test Scores**
```
Route: /continuing_edu/admin/events/<event_id>/scores
- View all member scores
- Filter by pass/fail status

For Each Member:
- Enter pre_test_score
- Enter post_test_score
- Set assessment_passed (boolean)
- Calculate improvement percentage
- Determine certificate eligibility

Criteria:
- Minimum attendance (e.g., 80%)
- Minimum score (e.g., 60%)
- Both pre and post test completed
```

**6. Issue Certificates**
```
Route: /continuing_edu/admin/events/<event_id>/certificates
- List eligible members (passed requirements)
- Filter by certificate status

Actions:
1. Generate Individual Certificate
   - Select member
   - Generate PDF with member name, event title, date
   - Upload to S3
   - Update certificate_url in MemberRegistration
   - Set certificate_status to 'issued'
   - Set certificate_issued_date
   - Update member total_continue_education_score
   - Send certificate email

2. Bulk Generate Certificates
   - Select multiple eligible members
   - Generate all certificates
   - Batch upload to S3
   - Batch send emails

3. Reissue Certificate
   - For lost/damaged certificates
   - Generate new PDF
   - Update certificate_url
```

**7. Event Reports**
```
Route: /continuing_edu/admin/reports

Available Reports:
1. Registration Summary
   - Total registrations by event
   - By member type, date range
   - Registration trends chart

2. Payment Summary
   - Total revenue by event
   - Payment status breakdown
   - Pending payments list
   - Refunds issued

3. Attendance Report
   - Attendance rate by event
   - No-show list
   - Hours attended summary

4. Certificate Issuance Report
   - Certificates issued count
   - Pass/fail rate
   - Score distribution
   - Certificate download tracking

5. Member Activity Report
   - Active members count
   - Registrations per member
   - Total CE scores earned
   - Member type distribution

Export Formats:
- Excel (.xlsx)
- CSV
- PDF
```

**8. Event Status Management**
```
Event Lifecycle:
1. Draft - Being created/edited, not visible
2. Published - Visible, registration open
3. Registration Closed - Visible, no new registrations
4. In Progress - Event is happening
5. Completed - Event finished, certificates issued
6. Archived - Old event, kept for records

Route: /continuing_edu/admin/events/<event_id>/status
Actions:
- Change status
- Set registration open/close dates
- Set early bird dates
- Archive old events
```

**9. Bulk Operations**
```
Route: /continuing_edu/admin/bulk-actions

Supported Operations:
1. Bulk Email
   - Send to all registered members
   - Send to specific member types
   - Templates: reminder, update, cancellation

2. Bulk Status Update
   - Change multiple registrations
   - Change multiple payments
   - Change event statuses

3. Bulk Export
   - Export registration list
   - Export payment records
   - Export attendance sheets
   - Export certificate list

4. Bulk Import
   - Import members from CSV
   - Import attendance data
   - Import test scores
```

**10. Staff Role Permissions**
```
Role Hierarchy:
1. Super Admin (full access)
2. Event Manager (all event operations)
3. Registration Reviewer (approve registrations only)
4. Payment Approver (approve payments only)
5. Certificate Manager (issue certificates only)

Check permissions before each action:
- Use @require_permission decorator
- Check staff role assignment to event
- Log all admin actions for audit
```

### Member Features
- Members use custom authentication (not StaffAccount)
- Store member info in session after login
- Member dashboard shows registrations, payments, certificates
- Support OTP verification for email
- Allow Google OAuth login (optional)
- Track continuing education scores per member

### Event Management (EventEntity)
- Single table for courses, webinars, workshops
- Use `event_type` field to distinguish types
- Related tables: EventSpeaker, EventAgenda, EventMaterial, EventRegistrationFee
- Support multiple registration fees by member type
- Assign staff roles: editors, reviewers, approvers, certificate managers
- Use pre-signed URLs for S3 images: `.cover_presigned_url()`, `.poster_presigned_url()`

### Payment & Registration Flow
1. Member registers for event → MemberRegistration created
2. Member uploads payment proof → RegisterPayment created
3. Admin approves payment → payment_status updated
4. Admin issues receipt → RegisterPaymentReceipt created
5. Member completes event → attendance tracked
6. Admin issues certificate → certificate_url added to registration

### File Uploads
- Store files in S3-compatible storage
- Generate pre-signed URLs for display (expire in 1 hour)
- Store only S3 keys in database, not full URLs
- Support cover images, posters, materials, payment proofs, certificates

### Common UI Patterns
- **Cards**: Use `<div class="card">` for content blocks
- **Buttons**: Primary = `button is-primary`, Secondary = `button is-light`
- **Forms**: Wrap in `<form>` with `{{ form.hidden_tag() }}` for CSRF
- **Modals**: Use Bulma modal structure with `.modal.is-active`
- **Tables**: Use `<table class="table is-fullwidth is-striped">` for data
- **Tags**: Use `<span class="tag is-info">` for status indicators
- **Notifications**: Use `<div class="notification is-success">` for messages

### JavaScript Patterns
- Use vanilla JavaScript (no jQuery)
- Initialize on `DOMContentLoaded` event
- Use `querySelectorAll()` and `forEach()` for multiple elements
- Add event listeners explicitly, don't use inline onclick
- Use `fetch()` API for AJAX requests
- Implement carousel with manual slide control and auto-advance
- Use AOS (Animate On Scroll) library for scroll animations

### Security Best Practices
- Use `{{ form.hidden_tag() }}` for CSRF protection in all forms
- Validate all user inputs server-side
- Use parameterized queries (SQLAlchemy handles this)
- Check authentication/authorization before sensitive operations
- Don't expose admin routes to non-admin users
- Sanitize user-generated content before display
- Use HTTPS in production
- Store secrets in environment variables, not code

### Performance Considerations
- Use lazy loading for relationships: `lazy=True`
- Paginate long lists (courses, members, payments)
- Cache expensive queries when possible
- Optimize image sizes for web display
- Use CDN for static assets (Bulma, FontAwesome, AOS)
- Minimize database queries in templates

### Testing Guidelines
- Write unit tests for models, forms, and utilities
- Write integration tests for critical flows (registration, payment)
- Test both Thai and English language paths
- Test with different member types
- Test admin and member permissions separately
- Use fixtures for test data

### Error Handling
- Use try/except for database operations
- Flash user-friendly error messages
- Log detailed errors for debugging
- Return appropriate HTTP status codes
- Provide fallback behavior for missing data
- Handle missing translations gracefully

### Common Gotcalls & Pitfalls
- **Template folder typo**: It's `continueing_edu` (with double 'e'), not `continuing_edu`
- **Language parameter**: Always include `lang` in `url_for()` calls
- **Admin auth**: Check both session existence and StaffAccount validity
- **Event types**: Don't hardcode event types, use the stored value
- **Bulma classes**: Use `is-*` prefix (is-primary, is-large), not Bootstrap/Tailwind classes
- **Relationships**: Always use `back_populates` on both sides of relationship
- **Commits**: Don't forget to commit after add/update/delete operations

## Example Code Patterns

### Route with Language Support
```python
@continuing_edu_bp.route('/<lang>/courses')
def courses(lang):
    texts = get_translations(lang)
    courses = EventEntity.query.filter_by(event_type='course').all()
    return render_template('continueing_edu/courses.html', 
                         courses=courses, 
                         texts=texts, 
                         current_lang=lang)
```

### Form Processing
```python
@continuing_edu_bp.route('/<lang>/register', methods=['GET', 'POST'])
def register(lang):
    form = MemberRegistrationForm()
    if form.validate_on_submit():
        member = Member(
            username=form.username.data,
            email=form.email.data
        )
        db.session.add(member)
        try:
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('continuing_edu.login', lang=lang))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    return render_template('continueing_edu/register.html', form=form, current_lang=lang)
```

### Admin Authorization Check
```python
def get_current_admin():
    admin_id = session.get('admin_id')
    if not admin_id:
        return None
    return StaffAccount.query.get(admin_id)

@admin_bp.route('/dashboard')
def dashboard():
    admin = get_current_admin()
    if not admin:
        return redirect(url_for('continuing_edu_admin.login'))
    # Dashboard logic here
```

### Query with Relationships
```python
# Get events with registration counts
events = db.session.query(EventEntity)\
    .outerjoin(MemberRegistration)\
    .group_by(EventEntity.id)\
    .all()

for event in events:
    registration_count = len(event.registrations)
    paid_count = len([r for r in event.registrations 
                     if r.payment and r.payment.payment_status_ref.name_en == 'Paid'])
```

### Template with Bulma
```html
{% extends 'continueing_edu/base.html' %}
{% block content %}
<section class="section">
    <div class="container">
        <h1 class="title">{{ texts.page_title }}</h1>
        <div class="columns is-multiline">
            {% for course in courses %}
            <div class="column is-one-third">
                <div class="card">
                    <div class="card-image">
                        <figure class="image is-4by3">
                            <img src="{{ course.cover_presigned_url() }}" alt="{{ course.title_en }}">
                        </figure>
                    </div>
                    <div class="card-content">
                        <p class="title is-5">{{ course.title_en if current_lang == 'en' else course.title_th }}</p>
                        <a href="{{ url_for('continuing_edu.course_detail', course_id=course.id, lang=current_lang) }}" 
                           class="button is-primary">{{ texts.learn_more }}</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endblock %}
```

## When Making Changes
1. Check existing code patterns before introducing new approaches
2. Test with both Thai and English languages
3. Verify responsive design on mobile/tablet/desktop
4. Check admin and member user flows separately
5. Update related documentation if adding new features
6. Use semantic commit messages
7. Consider backward compatibility with existing data

## Questions to Ask
- Is this for admin or member interface?
- Should this support both Thai and English?
- Does this need authentication/authorization?
- Should this be paginated?
- Are there related models that need updating?
- Does this affect existing registrations/payments?
- Should this send notifications/emails?

## Priority Order for Suggestions
1. Security and data integrity first
2. User experience and accessibility
3. Code maintainability and readability
4. Performance optimization
5. Feature enhancements
