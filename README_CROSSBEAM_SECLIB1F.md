# CROSSBEAM.SECLIB1F — One-click Edit button and section-name action polish

This milestone replaces the Project Section Summary row-selection checkbox with an explicit one-click `Edit` button column when the deployed Streamlit runtime supports `st.column_config.ButtonColumn`. The button click stages the selected Section ID before the next full render, so the Geometry Parameters, gross properties, live preview, and management controls open the selected section in one interaction.

A read-only table plus the existing Quick section switch remains as a compatibility fallback for older Streamlit runtimes that do not provide ButtonColumn.

The section-name action is also moved out of a form and rendered as the app-standard primary `st.button`, so `Save name` follows the same blue commercial action styling as other Concrete Section Pro controls. The button remains disabled until the project-facing name actually changes.

No section geometry equations, gross properties, Segment Layout data, Rebar/Tendon data, ULS/SLS solvers, prestress-loss logic, Project JSON schema, Result Summary, Report/QA, or non-Crossbeam workflow behavior is changed.
