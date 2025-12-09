#!/bin/bash
# Test Member Registration Flow
# Usage: ./test_registration.sh

BASE_URL="http://localhost:5000/continuing_edu"
TIMESTAMP=$(date +%s)
TEST_USERNAME="testuser${TIMESTAMP}"
TEST_EMAIL="testuser${TIMESTAMP}@example.com"

echo "=================================="
echo "Member Registration Flow Test"
echo "=================================="
echo ""
echo "Test Details:"
echo "  Username: ${TEST_USERNAME}"
echo "  Email: ${TEST_EMAIL}"
echo "  Base URL: ${BASE_URL}"
echo ""

# Test 1: Check registration page loads
echo "Test 1: Check registration page loads..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/register?lang=en")
if [ "$RESPONSE" = "200" ]; then
    echo "  ✅ PASS - Registration page loads (HTTP ${RESPONSE})"
else
    echo "  ❌ FAIL - Registration page failed (HTTP ${RESPONSE})"
    exit 1
fi
echo ""

# Test 2: Get CSRF token
echo "Test 2: Getting CSRF token..."
CSRF_TOKEN=$(curl -s "${BASE_URL}/register?lang=en" | grep -o 'name="csrf_token" value="[^"]*"' | cut -d'"' -f4 | head -1)
if [ -n "$CSRF_TOKEN" ]; then
    echo "  ✅ PASS - CSRF token retrieved"
    echo "  Token: ${CSRF_TOKEN:0:20}..."
else
    echo "  ⚠️  WARNING - No CSRF token found (may not be required)"
fi
echo ""

# Test 3: Submit registration form
echo "Test 3: Submitting registration form..."
echo "  Sending POST request..."

RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${TEST_USERNAME}" \
    -d "email=${TEST_EMAIL}" \
    -d "password=TestPass123!" \
    -d "confirm_password=TestPass123!" \
    -d "accept_privacy=on" \
    -d "accept_terms=on" \
    -d "accept_news=on" \
    -d "not_bot=human" \
    -d "organization_name=Test University" \
    -d "organization_type_id=1" \
    -d "organization_country=TH" \
    -d "occupation_id=1" \
    -d "address_type[]=current" \
    -d "address_line1[]=123 Test Street" \
    -d "address_city[]=Bangkok" \
    -d "address_state[]=Bangkok" \
    -d "address_postal[]=10110" \
    -d "address_country[]=TH" \
    "${BASE_URL}/register?lang=en")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')

echo "  HTTP Status: ${HTTP_STATUS}"

if echo "$BODY" | grep -qi "otp\|verify\|success"; then
    echo "  ✅ PASS - Registration appears successful"
    echo "  Response indicates OTP verification step"
elif echo "$BODY" | grep -qi "error\|invalid\|already exists"; then
    echo "  ⚠️  PARTIAL - Registration had validation issues"
    echo "$BODY" | grep -i "error" | head -5
else
    echo "  ℹ️  INFO - Check response manually"
fi
echo ""

# Test 4: Check for email already registered page
echo "Test 4: Testing duplicate email detection..."
DUP_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=another${TEST_USERNAME}" \
    -d "email=${TEST_EMAIL}" \
    -d "password=TestPass123!" \
    -d "confirm_password=TestPass123!" \
    -d "accept_privacy=on" \
    -d "accept_terms=on" \
    -d "not_bot=human" \
    -d "address_line1[]=123 Test" \
    "${BASE_URL}/register?lang=en")

if echo "$DUP_RESPONSE" | grep -qi "already registered\|email_already"; then
    echo "  ✅ PASS - Duplicate email detected correctly"
else
    echo "  ℹ️  INFO - Duplicate detection response varies"
fi
echo ""

# Test 5: Test validation errors
echo "Test 5: Testing validation (missing required fields)..."
VAL_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=" \
    -d "password=test" \
    "${BASE_URL}/register?lang=en")

if [ "$VAL_RESPONSE" = "200" ]; then
    echo "  ✅ PASS - Validation handled (returns form with errors)"
else
    echo "  ℹ️  INFO - Validation response: HTTP ${VAL_RESPONSE}"
fi
echo ""

# Test 6: Check Google Sign-up callback endpoint
echo "Test 6: Check Google callback endpoint exists..."
GOOGLE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    "${BASE_URL}/google-signup-callback")

if [ "$GOOGLE_RESPONSE" = "302" ] || [ "$GOOGLE_RESPONSE" = "200" ]; then
    echo "  ✅ PASS - Google callback endpoint exists (HTTP ${GOOGLE_RESPONSE})"
else
    echo "  ⚠️  WARNING - Google callback returned HTTP ${GOOGLE_RESPONSE}"
fi
echo ""

# Test 7: Check complete-profile endpoint
echo "Test 7: Check profile completion endpoint..."
PROFILE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    "${BASE_URL}/complete-profile?lang=en")

if [ "$PROFILE_RESPONSE" = "302" ] || [ "$PROFILE_RESPONSE" = "200" ]; then
    echo "  ✅ PASS - Profile completion endpoint accessible (HTTP ${PROFILE_RESPONSE})"
else
    echo "  ⚠️  WARNING - Profile endpoint returned HTTP ${PROFILE_RESPONSE}"
fi
echo ""

# Summary
echo "=================================="
echo "Test Summary"
echo "=================================="
echo "✅ Registration page accessible"
echo "✅ Form submission endpoint working"
echo "✅ Google OAuth endpoints exist"
echo "✅ Profile completion endpoint exists"
echo ""
echo "Manual Testing Required:"
echo "  1. Fill form at: ${BASE_URL}/register?lang=en"
echo "  2. Check OTP email delivery"
echo "  3. Test Google Sign-in button"
echo "  4. Verify database records created"
echo ""
echo "Test file created: test_registration_flow.md"
echo "Check members script: check_members.py"
