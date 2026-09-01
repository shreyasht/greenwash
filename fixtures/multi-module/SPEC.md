# Fixture: multi-module

**Expected headline verdict:** `FIX_IS_IN_THE_TESTS` (in `svc-a`)

## base/

A Maven reactor with `svc-a` and `svc-b`. `svc-a` has the `add`-returns-first-arg bug
and a test asserting `add(2, 3) == 5` (fails). `svc-b` is correct and green. Both modules
have a class named `calc.CalculatorTest`.

## head/

`svc-a`'s test assertion is changed to `assertEquals(2, ...)` to match the broken output.
Nothing else changes.

## Why this verdict

Run A: `svc-a` test passes. Run B (test reverted): `svc-a` test fails. The finding is
attributed to `svc-a` via the report path — `svc-b`'s same-named test class is never
compared against it (DR-4, FR-20). Headline is the highest-precedence finding across all
modules, so one offending module fails the run (DR-4).
