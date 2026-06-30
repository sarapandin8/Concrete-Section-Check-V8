# UPLOAD.FILEUPLOADER.CLEAR1 — Preserve Streamlit Uploaded-File Remove Control

## Intent

Fix a Loads-page UX regression where the native Streamlit uploaded-file `x` control could become difficult or impossible to click after a file was selected for import.

## Root cause

The commercial action-button CSS used a broad selector under `stFileUploader`:

```css
div[data-testid="stFileUploader"] button
```

That selector does not only target the uploader Browse button. It can also reach the native uploaded-file pill controls, including the small remove (`x`) button. Styling those internal controls is fragile because Streamlit owns their DOM structure and click target geometry.

## Change

The uploader styling is now limited to the dropzone Browse button only:

```css
div[data-testid="stFileUploaderDropzone"] button
```

This keeps the Browse action visually consistent while leaving uploaded-file remove controls under Streamlit's native behavior.

## Scope

Changed only global CSS and CSS regression tests. No load import parsing, session state, project IO, solver, geometry, section-property, rebar, prestress, SLS, shear, torsion, or report logic was changed.

## Validation

Added source-level regression tests to prevent reintroducing broad `stFileUploader` button selectors.
