# UI.THEME1 — Commercial Engineering Theme Foundation

This milestone applies a visual-only commercial engineering theme foundation to Concrete Section Pro.
It borrows the preferred navy engineering-tool look from the reference UI while preserving the existing workflow structure.

## Scope

Changed only global CSS/theme behavior in `app.py`:

- app background and density polish,
- dark navy sidebar foundation,
- dark navy expander/section bars,
- stronger engineering-style metric cards,
- table/editor outer chrome,
- plot/report panel chrome,
- existing custom result-card polish,
- alert/input border polish.

## Non-scope

No solver equations, data-editor commit logic, widget keys, project schema, geometry, prestress/debonding logic, load-combination logic, report certification wording, or navigation/page routing was changed.

## Regression intent

The theme is intentionally CSS-only. Tests check that the new commercial theme markers exist and that no app navigation structure is added, removed, or renamed.
