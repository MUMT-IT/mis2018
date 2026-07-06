Feature: Derive normal attendance from GPS check-in records
  As an OT system administrator
  I want the system to derive normal daily check-in and check-out from GPS records
  So that normal attendance can be evaluated consistently for all employees

  Background:
    Given the normal work period is from "09:00" to "16:30"

  Scenario: Employee has multiple GPS records in one day
    Given employee "E001" has GPS check-in records on "2026-06-26" at:
      | time  |
      | 07:48 |
      | 10:15 |
      | 12:03 |
      | 15:55 |
      | 16:10 |
      | 18:30 |
    When the system derives normal attendance for employee "E001" on "2026-06-26"
    Then the actual check-in time should be "07:48"
    And the actual check-out time should be "18:30"
    And the employee should not be marked as late
    And the employee should not be marked as early checkout

  Scenario: Employee checks in late
    Given employee "E002" has GPS check-in records on "2026-06-26" at:
      | time  |
      | 09:12 |
      | 12:01 |
      | 16:35 |
    When the system derives normal attendance for employee "E002" on "2026-06-26"
    Then the actual check-in time should be "09:12"
    And the actual check-out time should be "16:35"
    And the employee should be marked as late
    And the employee should not be marked as early checkout

  Scenario: Employee checks out early
    Given employee "E003" has GPS check-in records on "2026-06-26" at:
      | time  |
      | 08:55 |
      | 10:30 |
      | 16:10 |
    When the system derives normal attendance for employee "E003" on "2026-06-26"
    Then the actual check-in time should be "08:55"
    And the actual check-out time should be "16:10"
    And the employee should not be marked as late
    And the employee should be marked as early checkout

  Scenario: Employee has only one GPS record
    Given employee "E004" has GPS check-in records on "2026-06-26" at:
      | time  |
      | 09:03 |
    When the system derives normal attendance for employee "E004" on "2026-06-26"
    Then the actual check-in time should be "09:03"
    And the actual check-out time should be missing
    And the employee should be marked as late
    And the attendance record should require review

  Scenario: Employee has no GPS record
    Given employee "E005" has no GPS check-in records on "2026-06-26"
    When the system derives normal attendance for employee "E005" on "2026-06-26"
    Then the actual check-in time should be missing
    And the actual check-out time should be missing
    And the attendance record should require review

  Scenario: Employee has multiple GPS records at Salaya
    Given employee "E006" has GPS check-in records at place "salaya" on "2026-06-26" at:
      | time  |
      | 08:01 |
      | 17:12 |
    When the system derives normal attendance for employee "E006" on "2026-06-26"
    Then the employee should have 2 work login rows for the day
    And the actual check-in time should be "08:01"
    And the actual check-out time should be "17:12"
    And the employee should not be marked as late
    And the employee should not be marked as early checkout

  Scenario: Employee has multiple QR records in one day
    Given employee "E007" has QR check-in records on "2026-06-26" at:
      | time  |
      | 08:15 |
      | 17:20 |
    When the system derives QR attendance for employee "E007" on "2026-06-26"
    Then the employee should have 2 work login rows for the day
    And the actual check-in time should be "08:15"
    And the actual check-out time should be "17:20"
    And the employee should not be marked as late
    And the employee should not be marked as early checkout
