Feature: External employee login
  External employees should be able to sign in with their external email and password, then reach the external landing page.

  Scenario: External employee logs in with a full email and lands on the external portal
    Given an external staff account with email "external.employee@example.com" and password "Secret123!"
    When I submit the external login form
    Then I should be logged in and directed to the external landing page

  Scenario: External employee logs in with a username and lands on the external portal
    Given an external staff account with email "external.employee@example.com" and password "Secret123!"
    When I submit the external login form with "external.employee" as a username
    Then I should be logged in and directed to the external landing page
