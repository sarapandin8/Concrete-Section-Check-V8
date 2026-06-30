# DESIGN.CODE.ROUTE1 — Workflow-compatible design-code display guard

## Issue

The global app chrome and some Analysis/Prestress status cards could display a stale `design_code` from session state. Example: active workflow = Bridge Beam/Girder with a bridge I-girder preset, but the top context strip still showed `ACI 318` while Beam/Girder ULS routes correctly used AASHTO LRFD.

## Cause

The Project page normalizes `design_code` for the active workflow, but the app chrome is rendered on every page and may run before the Project page has normalized state. Some status cards also read `project_design_code_from_session()` directly instead of the workflow-compatible design code.

## Fix

Add workflow-aware read helpers:

- `workflow_member_type_from_session`
- `workflow_project_design_code_from_session`
- `workflow_project_code_edition_from_session`
- `workflow_project_code_label_from_session`

Use these helpers for:

- always-visible app chrome Design Code label
- Analysis workspace/report dashboard cards
- Prestress loss basis when inheriting from project/workflow code

## Engineering boundary

This milestone changes display/routing guards only. It does not change ACI/AASHTO solver formulas.
