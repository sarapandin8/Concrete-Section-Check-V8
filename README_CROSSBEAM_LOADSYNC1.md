# CROSSBEAM.LOADSYNC1 — Canonical Prestress Contract Restore

This milestone prevents stale Streamlit widget transport values from replacing
the restored Crossbeam Station Force Contract after a Project JSON load.

## Restore transaction

- Clears only the `crossbeam_loads1b_*` widget namespace before applying any
  loaded Project; canonical load tables, Station Force Contract, and Effective
  Prestress Link remain Project data.
- Clears the prior project's derived station-force validation handoff so it
  cannot appear under the newly loaded Project.
- Restores the Effective Prestress Link before canonicalizing the Station Force
  Contract.

## Canonical authority

- When the Effective Prestress Link is `ready`, its uniform system-average total
  loss, effective ratio, Source ID, and Contract ID are authoritative.
- Disabled Loads widgets are display-only and are synchronized from the ready
  link on every rerun.
- When the link is not ready, the engineer-entered contract values remain
  available; no loss value is invented.

## Analysis status

- Adds the Station Force Contract and Effective Prestress Link to the `Loads`
  dirty-state input group.
- Changing either source after an Analysis run marks Analysis and Report output
  out of date.

## Scope retained

- No Project JSON schema changed.
- No load row, sign conversion, ULS, SLS, or Prestress Loss equation changed.
- The explicit Rebar Zone reset rule from `CROSSBEAM.PROJECT.JSON1` is unchanged.
- The first load of a saved 45 m Rebar extent still requires one user-approved
  reset to the saved 30 m Segment Layout.

## Regression evidence

- New targeted regression: `4 passed`.
- Related Project JSON / Loads / Effective Prestress regression:
  `35 passed`; the same 3 selected baseline failures remain.
- Crossbeam regression: `501 passed`; the same 8 baseline failures remain.
- Full repository regression: `2,332 passed`; the same 15 baseline failures
  remain.
- Streamlit integration with the supplied 30 m Project completed without
  exceptions: the guarded Rebar reset changed geometry to `READY`, stale `0%`
  widget values were replaced by the ready `17.286%` link, the ULS + Transfer +
  Service handoff became `READY`, and `Calculate Flexure` was enabled.

## Repo summary

Preserve the ready Effective Prestress Link across Project restore, isolate Loads widget transport state, and invalidate Analysis when the station-force contract changes.
