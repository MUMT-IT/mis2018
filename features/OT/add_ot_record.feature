Feature: Prevent overlapping OT shifts

  Scenario: Employee cannot have overlapping OT shifts
    Given an employee already has an OT shift from "2026-03-01 18:00" to "2026-03-01 22:00"
    When I create another OT shift for the same employee from "2026-03-01 21:00" to "2026-03-01 23:00"
    Then the system should reject the new OT shift
    And the error message should say "มีข้อมูลการทำOT ในช่วงเวลานี้แล้ว กรุณาตรวจสอบเวลาใหม่อีกครั้ง"

  Scenario: Employee can have consecutive OT shifts
    Given an employee already has an OT shift from "2026-03-01 18:00" to "2026-03-01 22:00"
    When I create another OT shift for the same employee from "2026-03-01 22:00" to "2026-03-01 23:00"
    Then the system should accept the new OT shift
