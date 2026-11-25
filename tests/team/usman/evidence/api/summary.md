# API test summary

Spec version 8.8.4; 116 tests: 101 PASS, 15 XFAIL, 0 FAIL, 0 XPASS

| Test | Kind | Requirements | Risks | Status |
| --- | --- | --- | --- | --- |
| S-CO-01 | scenario | CO-01 | R-A2 | PASS |
| S-CO-02a | scenario | CO-02 | R-A8 | PASS |
| S-CO-02b | scenario | CO-02 | R-A8 | PASS |
| S-CO-03a | scenario | CO-03 | R-A2, R-A3 | PASS |
| S-CO-03b | scenario | CO-03 | R-A2 | PASS |
| S-CO-03c | scenario | CO-03 | R-A2, R-A3 | PASS |
| S-CO-03d | scenario | CO-03 | R-A2 | PASS |
| S-CO-03e | scenario | CO-01, CO-03 | R-A8 | PASS |
| S-CI-01 | scenario | CI-01 | R-A5 | PASS |
| S-CI-02 | scenario | CI-02 | R-A2 | PASS |
| S-CI-03 | scenario | CI-03 | R-A2, R-A3 | PASS |
| S-CI-04a | scenario | CI-04 | R-A5, R-A3 | PASS |
| S-CI-04b | scenario | CI-04 | R-A5 | PASS |
| S-AUTH-01 | scenario | CO-03, CI-03 | R-A4 | PASS |
| S-AUTH-02 | scenario | CO-03 | R-A4 | PASS |
| S-CONC-01 | scenario | CO-03 | R-A2 | PASS |
| CI.asset-id.below-minimum-0 | generated | CI-01 | R-A3 | PASS |
| CI.asset-id.decimal-number | generated | CI-01 | R-A3 | PASS |
| CI.asset-id.id-that-matches-no-asset | generated | CI-01 | R-A3 | PASS |
| CI.asset-id.negative-1 | generated | CI-01 | R-A3 | PASS |
| CI.asset-id.non-numeric-text | generated | CI-01 | R-A3 | PASS |
| CI.baseline.valid-baseline-request | generated | CI-01 | R-A3, R-A4, R-A5, R-A8 | PASS |
| CI.checkin-at.explicit-null | generated | CI-01 | R-A8 | PASS |
| CI.checkin-at.impossible-calendar-date-2027-02-29 | generated | CI-01 | R-A8 | XFAIL |
| CI.checkin-at.month-out-of-range-2027-13-01 | generated | CI-01 | R-A8 | XFAIL |
| CI.checkin-at.text-that-is-not-a-date | generated | CI-01 | R-A8 | XFAIL |
| CI.checkin-at.valid-leap-day-2028-02-29 | generated | CI-01 | R-A8 | PASS |
| CI.checkin-at.valid-value-today | generated | CI-01 | R-A8 | PASS |
| CI.checkin-at.wrong-type-boolean | generated | CI-01 | R-A8 | XFAIL |
| CI.clear-name.enumeration-value-with-changed-case | generated | CI-01 | R-A8 | XFAIL |
| CI.clear-name.valid-value-1 | generated | CI-01 | R-A8 | PASS |
| CI.clear-name.value-outside-the-enumeration | generated | CI-01 | R-A8 | XFAIL |
| CI.clear-name.wrong-type-number | generated | CI-01 | R-A8 | XFAIL |
| CI.location-id.above-minimum-2 | generated | CI-01 | R-A8 | PASS |
| CI.location-id.at-minimum-1 | generated | CI-01 | R-A8 | PASS |
| CI.location-id.below-minimum-0 | generated | CI-01 | R-A8 | XFAIL |
| CI.location-id.explicit-null | generated | CI-01 | R-A8 | PASS |
| CI.location-id.valid-value-location | generated | CI-01 | R-A8 | PASS |
| CI.location-id.well-formed-id-that-matches-no-row-2147483647 | generated | CI-01 | R-A8 | PASS |
| CI.location-id.wrong-type-boolean | generated | CI-01 | R-A8 | XFAIL |
| CI.location-id.wrong-type-decimal | generated | CI-01 | R-A8 | XFAIL |
| CI.location-id.wrong-type-text | generated | CI-01 | R-A8 | XFAIL |
| CI.name.explicit-null | generated | CI-01 | R-A1, R-A8 | PASS |
| CI.name.length-254-below-maximum | generated | CI-01 | R-A1, R-A8 | PASS |
| CI.name.length-255-at-maximum | generated | CI-01 | R-A1, R-A8 | PASS |
| CI.name.length-256-above-maximum | generated | CI-01 | R-A1, R-A8 | PASS |
| CI.name.valid-value-sqe-returned-laptop | generated | CI-01 | R-A1, R-A8 | PASS |
| CI.name.wrong-type-number | generated | CI-01 | R-A1, R-A8 | XFAIL |
| CI.note.explicit-null | generated | CI-01 | R-A8 | PASS |
| CI.note.valid-value-returned-in-good-condition | generated | CI-01 | R-A8 | PASS |
| CI.note.wrong-type-number | generated | CI-01 | R-A8 | PASS |
| CI.status-id.above-minimum-2 | generated | CI-02, CI-03 | R-A8 | PASS |
| CI.status-id.at-minimum-1 | generated | CI-02, CI-03 | R-A8 | PASS |
| CI.status-id.below-minimum-0 | generated | CI-02, CI-03 | R-A8 | PASS |
| CI.status-id.valid-value-deployable-status | generated | CI-02, CI-03 | R-A8 | PASS |
| CI.status-id.well-formed-id-that-matches-no-row-2147483647 | generated | CI-02, CI-03 | R-A8 | PASS |
| CI.status-id.wrong-type-boolean | generated | CI-02, CI-03 | R-A8 | XFAIL |
| CI.status-id.wrong-type-decimal | generated | CI-02, CI-03 | R-A8 | XFAIL |
| CI.status-id.wrong-type-text | generated | CI-02, CI-03 | R-A8 | PASS |
| CO.asset-id.below-minimum-0 | generated | CO-01 | R-A3 | PASS |
| CO.asset-id.decimal-number | generated | CO-01 | R-A3 | PASS |
| CO.asset-id.id-that-matches-no-asset | generated | CO-01 | R-A3 | PASS |
| CO.asset-id.negative-1 | generated | CO-01 | R-A3 | PASS |
| CO.asset-id.non-numeric-text | generated | CO-01 | R-A3 | PASS |
| CO.assigned-user.above-minimum-2 | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.at-minimum-1 | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.below-minimum-0 | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.required-field-is-null | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.required-field-omitted | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.well-formed-id-that-matches-no-row-2147483647 | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.wrong-type-boolean | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.wrong-type-decimal | generated | CO-01 | R-A8 | PASS |
| CO.assigned-user.wrong-type-text | generated | CO-01 | R-A8 | PASS |
| CO.baseline.valid-baseline-request | generated | CO-01 | R-A2, R-A3, R-A4, R-A8 | PASS |
| CO.checkout-at.explicit-null | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.impossible-calendar-date-2027-02-29 | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.month-out-of-range-2027-13-01 | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.text-that-is-not-a-date | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.valid-leap-day-2028-02-29 | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.valid-value-today | generated | CO-01 | R-A8 | PASS |
| CO.checkout-at.wrong-type-boolean | generated | CO-01 | R-A8 | PASS |
| CO.checkout-to-type.enumeration-value-with-changed-case | generated | CO-01 | R-A8 | PASS |
| CO.checkout-to-type.required-field-is-null | generated | CO-01 | R-A8 | PASS |
| CO.checkout-to-type.required-field-omitted-server-infers-it | generated | CO-01 | R-A8 | PASS |
| CO.checkout-to-type.value-outside-the-enumeration | generated | CO-01 | R-A8 | PASS |
| CO.checkout-to-type.wrong-type-number | generated | CO-01 | R-A8 | PASS |
| CO.expected-checkin.explicit-null | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.impossible-calendar-date-2027-02-29 | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.month-out-of-range-2027-13-01 | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.text-that-is-not-a-date | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.valid-leap-day-2028-02-29 | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.valid-value-due-date | generated | CO-02 | R-A8 | PASS |
| CO.expected-checkin.wrong-type-boolean | generated | CO-02 | R-A8 | PASS |
| CO.name.explicit-null | generated | CO-04 | R-A1, R-A8 | PASS |
| CO.name.length-254-below-maximum | generated | CO-04 | R-A1, R-A8 | PASS |
| CO.name.length-255-at-maximum | generated | CO-04 | R-A1, R-A8 | PASS |
| CO.name.length-256-above-maximum | generated | CO-04 | R-A1, R-A8 | PASS |
| CO.name.valid-value-sqe-laptop | generated | CO-04 | R-A1, R-A8 | PASS |
| CO.name.wrong-type-number | generated | CO-04 | R-A1, R-A8 | XFAIL |
| CO.note.explicit-null | generated | CO-01 | R-A8 | PASS |
| CO.note.valid-value-issued-at-the-lab-desk | generated | CO-01 | R-A8 | PASS |
| CO.note.wrong-type-number | generated | CO-01 | R-A8 | PASS |
| CO.requestable.explicit-null | generated | CO-01 | R-A8 | PASS |
| CO.requestable.number-outside-0-1 | generated | CO-01 | R-A8 | PASS |
| CO.requestable.text-that-is-not-a-boolean | generated | CO-01 | R-A8 | PASS |
| CO.requestable.valid-boolean-true | generated | CO-01 | R-A8 | PASS |
| CO.requestable.valid-value-false | generated | CO-01 | R-A8 | PASS |
| CO.status-id.above-minimum-2 | generated | CO-03 | R-A8 | PASS |
| CO.status-id.at-minimum-1 | generated | CO-03 | R-A8 | PASS |
| CO.status-id.below-minimum-0 | generated | CO-03 | R-A8 | PASS |
| CO.status-id.explicit-null | generated | CO-03 | R-A8 | PASS |
| CO.status-id.valid-value-deployable-status | generated | CO-03 | R-A8 | PASS |
| CO.status-id.well-formed-id-that-matches-no-row-2147483647 | generated | CO-03 | R-A8 | PASS |
| CO.status-id.wrong-type-boolean | generated | CO-03 | R-A8 | PASS |
| CO.status-id.wrong-type-decimal | generated | CO-03 | R-A8 | PASS |
| CO.status-id.wrong-type-text | generated | CO-03 | R-A8 | PASS |
