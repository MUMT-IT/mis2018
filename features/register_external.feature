Feature: External staff account
  External staff accounts must be registered by staff with HR permissions only.

  Scenario: HR staff registers a new external account
    Given a staff account belongs to external organization
    When an HR submit the staff account form
    Then the HR should be directed to the HR's staff edit password page
