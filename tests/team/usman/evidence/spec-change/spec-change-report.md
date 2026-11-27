# Spec-change demonstration

Two constraints were changed in a copy of `hardware-loans.openapi.json`; the generator was run on both.

| Constraint | Before | After |
| --- | --- | --- |
| checkout `name` maxLength | 255 | 100 |
| checkout `assigned_user` minimum | 1 | 10 |

Cases before: 100. Cases after: 100. Removed: 6. Added: 6. Modified in place: 0.

## Removed (only in the original spec)

- `CO.assigned-user.above-minimum-2` expects **depends**, body {"checkout_to_type": "user", "assigned_user": 2}
- `CO.assigned-user.at-minimum-1` expects **depends**, body {"checkout_to_type": "user", "assigned_user": 1}
- `CO.assigned-user.below-minimum-0` expects **reject**, body {"checkout_to_type": "user", "assigned_user": 0}
- `CO.name.length-254-below-maximum` expects **accept**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(254 chars)"}
- `CO.name.length-255-at-maximum` expects **accept**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(255 chars)"}
- `CO.name.length-256-above-maximum` expects **reject**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(256 chars)"}

## Added (only in the changed spec)

- `CO.assigned-user.above-minimum-11` expects **depends**, body {"checkout_to_type": "user", "assigned_user": 11}
- `CO.assigned-user.at-minimum-10` expects **depends**, body {"checkout_to_type": "user", "assigned_user": 10}
- `CO.assigned-user.below-minimum-9` expects **reject**, body {"checkout_to_type": "user", "assigned_user": 9}
- `CO.name.length-100-at-maximum` expects **accept**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(100 chars)"}
- `CO.name.length-101-above-maximum` expects **reject**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(101 chars)"}
- `CO.name.length-99-below-maximum` expects **accept**, body {"checkout_to_type": "user", "assigned_user": "@student", "name": "LLL...(99 chars)"}

## Modified in place


## What this means for the tests

* A 255-character name was valid and is now invalid, so `...length-255-at-maximum` is replaced by `...length-100-at-maximum` and the 256-character rejection case becomes a 101-character one. The API must now reject 101 characters with HTTP 200 and status `error`, and the saved asset must keep its previous name, borrower, due date, status, counters and history.
* With minimum 10, user id 9 is the below-minimum rejection and 10 and 11 become the boundary neighbours; because user ids are table keys, whether 10 and 11 succeed depends on those users existing (the runner asks the API).
