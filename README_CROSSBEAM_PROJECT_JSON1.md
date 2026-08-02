# CROSSBEAM.PROJECT.JSON1 — Canonical Restore and Geometry Guard

This milestone makes the saved Crossbeam input model authoritative and prevents
historical default-seed heuristics or stale Streamlit widget payloads from
changing restored member stations.

## Restore changes

- Treats a current `crossbeam_input_model` Project-JSON block as the source of
  truth for Crossbeam length, Segment Layout, and preserved construction layouts.
- Restricts the historical 30 m-to-20 m seed adoption to the legacy-key path;
  canonical Project-JSON rows are only normalized, never rescaled or reseeded.
- Clears transient member-length, construction-method, Segment editor, and
  Rebar Zone editor widget payloads before applying a canonical Crossbeam block.
- Marks the legacy seed migration complete after canonical restore so later
  Streamlit reruns cannot reinterpret valid saved 30 m stations.

## Geometry guard and explicit repair

- Audits Segment Layout, Rebar Zones, Tendon Profile, Column/support stations,
  and active ULS/SLS load stations after Project restore without mutating them.
- Reports the exact mismatch, for example:
  `Rebar Zone extent = 0.000–45.000 m, but Crossbeam length = 30.000 m.`
- Shows `PROJECT GEOMETRY INCONSISTENT — BLOCKED` at the Project load point.
- Offers `Reset Rebar Zones from Segment Layout` only when the restored model
  proves one Zone per Segment. Custom subdivisions are never replaced by this
  shortcut.
- The explicit reset preserves both Rebar Template Libraries, rebuilds only the
  Segment/Zone assignments, clears stale editor payloads, refreshes validation,
  and marks dependent analysis/report state out of date.
- Crossbeam ULS Flexure consumes the Rebar geometry blocker directly. Prestress
  Loss remains independent of ordinary Rebar Zone extent.

## Regression evidence

- Actual supplied Project JSON: `L = 30.000 m` and Segment boundaries
  `0–4.5–10.5–15–19.5–25.5–30 m` persist through repeated reruns.
- Actual supplied Project JSON: Rebar stays at 45 m until the visible reset is
  pressed; after reset its extent is 30 m and the audit is `READY`.
- Targeted regression: `36 passed`.
- Crossbeam regression: `497 passed`; the same 8 baseline failures remain.
- Full repository regression: `2,328 passed`; the same 15 baseline failures remain.
- Streamlit AppTest: canonical load, visible blocker, explicit reset, and
  post-reset `READY` state complete without exceptions.

## Safety retained

- No Project JSON schema version changed.
- No Section, Rebar quantity, Tendon, Prestress Loss, ULS, or SLS equation changed.
- No automatic scaling or silent Rebar repair was added to Project load.
- New projects still use the established 20 m default.
- Existing valid custom Rebar subdivisions remain valid and are not offered the
  one-click destructive reset.

## Repo summary

Preserve canonical Crossbeam length and Segment stations on Project JSON restore, surface exact cross-system geometry blockers, and provide a guarded one-click Rebar Zone reset.
