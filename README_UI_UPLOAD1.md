# UI.UPLOAD1 — Readable Project JSON Review Card

## Scope

This milestone improves the shared sidebar Project JSON selection and review UI.

- Shows the full selected filename with safe wrapping at sidebar width.
- Shows file size, JSON validation state, and the member workflow stored in the file.
- Keeps file selection and validation read-only; Project session state changes only after `Apply Loaded Project`.
- Disables Apply for invalid JSON and shows a readable validation reason.
- Uses the Concrete Section Pro navy/blue theme, teal-green for validated files, and dark red on pale pink for blocked/invalid states.
- Replaces the low-contrast Crossbeam sidebar geometry blocker with a scoped readable notice.
- Narrows uploader button styling to the dropzone button so the native remove control is not action-styled.

## Cross-workflow behavior

The Project File panel is part of the shared application shell, so the visual improvement is available in every member workflow. The canonical Project JSON apply route remains unchanged. A selected file does not mutate the active project; pressing Apply restores the complete project and can therefore switch the active member workflow to the workflow stored in that file.

## Exclusions

- No engineering equations changed.
- No ULS/SLS or prestress-loss calculation logic changed.
- No Project JSON schema or serialization changed.
- No automatic Project apply was added.
- No result-cache persistence was added.
