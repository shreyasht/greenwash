# Fixture: config-weakened

**Expected headline verdict:** `CONFIG_WEAKENED`

## base/

`Calculator` has `add` (tested) and `subtract` (untested). The JaCoCo `check` goal
requires 80% line coverage — the untested `subtract` drops coverage below that, so
`mvn verify` fails at `jacoco:check`.

## head/

`pom.xml` lowers the coverage minimum to `0.00`. Nothing else changes.

## Why this verdict

Run A (new pom): `jacoco:check` passes. Run B (pom reverted to base): `jacoco:check`
fails. A gate that failed under the base config passes under the new config —
`CONFIG_WEAKENED`, exit 1. No per-test outcome changed, so this is invisible to the
per-test observable (§4.2).
