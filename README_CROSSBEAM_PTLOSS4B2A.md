# CROSSBEAM.PTLOSS4B2A — Time-Dependent Widget Default Initialization Hotfix

Fixes the Streamlit runtime `ValueError` raised when opening the Crossbeam Time-Dependent tab after PTLOSS4B2.

## Root cause

The PTLOSS4B2 later-load `Δfcd` widget key was accidentally inserted inside the existing permanent-load default tuple. That tuple therefore contained three values while the initialization loop expected exactly `key, value`, causing the page to fail before rendering.

## Fix

- Replaces the fragile inline tuple list with `_initialize_crossbeam_td_session_defaults(...)`.
- Seeds all ten Time-Dependent widget keys through one explicit key-to-default mapping.
- Includes the new `td_later_load_delta_fcgp_mpa` input as its own mapping entry.
- Preserves any value already present in Streamlit Session State.
- Adds a regression test that initializes all Time-Dependent keys and verifies the later-load input without tuple-unpacking failure.

## Engineering scope

No prestress-loss equations, event-based frame solver, concrete-stress sources, construction schedule, Project JSON schema, or results are changed.
