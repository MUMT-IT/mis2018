# OT Matching Invariants

This document captures the current rules used by `get_all_ot_records_table()` and the surrounding helpers in `app/ot/views.py`.

## Core Rules

- A login row is normalized into a reusable pair by `_build_checkin_pairs()`.
- Rows with a real `end_datetime` are treated as complete pairs.
- Open rows stay open unless they are part of a clearly identifiable same-day or overnight sequence.
- Open rows are never allowed to leak into a different calendar day.
- Complete pairs are preferred over open or synthetic rows when multiple candidates can fit a shift.
- A row can only be used once as an open/synthetic candidate.
- Midnight placeholder scans are only valid for actual midnight-starting shifts.
- A checkout that has already been consumed as a synthetic midnight anchor cannot be reused as a later check-in.

## Supported Cases

- Same-day complete check-in / check-out pairs.
- Late check-in and early checkout adjustments for normal hourly OT.
- Late check-ins beyond the cutoff still show work duration, but payment is `0.00`.
- Open rows that should remain visible as incomplete attendance.
- Per-period OT rows that pay full shift value when the pair is complete.
- Overnight sequences that legitimately cross midnight.
- Reuse of one complete pair across adjacent shifts when the pair truly spans them.

## Known Limitation

- A single complete pair that spans multiple adjacent shifts is still easiest to calculate when a `00:00` anchor exists.
- Without that anchor, the current matching logic may not always distribute the pair the way a human would expect across adjacent shifts.
- A complete pair that exceeds the late cutoff is not paid, even though work duration is still computed and displayed.

## Non-Goals

- Do not let an open check-in from a different day satisfy an earlier shift.
- Do not infer a checkout for an open row.
- Do not let one scan pair satisfy unrelated shifts unless the pairing rules explicitly allow it.

## Regression Coverage

- Wrong-day open scan reuse is covered in `tests/test_ot_get_all_ot_records_table.py`.
- Overnight split behavior is covered in `tests/test_ot_get_all_ot_records_table.py`.
- Reuse of a complete pair across adjacent shifts is covered in `tests/test_ot_get_all_ot_records_table.py`.
