# UI.COMMERCIAL4.5 — Soft Metric Cards and Load Workspace Hierarchy Polish

This milestone softens the Streamlit metric card styling introduced during the commercial dashboard polish. Summary metrics are now treated as secondary dashboard evidence rather than primary actions: the cards use a light blue-tinted surface, blue accent border, dark readable labels, and blue numeric values instead of a solid blue fill.

Primary actions and selected navigation states remain blue. Navy/dark tones remain reserved for brand/structural emphasis where still applicable.

Scope:

- Replaces solid-blue `st.metric` cards with soft dashboard metric cards.
- Keeps load-count summaries readable without overpowering load tables and validation messages.
- Preserves the light-blue accordion system from `UI.COMMERCIAL4.4`.
- Does not modify solver equations, SLS/ULS/PMM logic, rebar/prestress logic, report logic, widget keys, project schema, save/load behavior, or navigation state.
