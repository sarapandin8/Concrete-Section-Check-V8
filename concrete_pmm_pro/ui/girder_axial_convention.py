"""Source convention control shared by I-Girder Loads and Analysis."""
import streamlit as st

from concrete_pmm_pro.analysis.girder_axial_convention import (
    SETTINGS_KEY, LABELS, CSI_TENSION_POSITIVE, axial_convention,
)


def render_axial_convention() -> None:
    current = axial_convention(st.session_state)
    choices = [None, *LABELS]
    selected = st.selectbox("Final ULS Nu input convention", choices,
        index=choices.index(current["input_sign"]) if current["declared"] else 0,
        format_func=lambda choice: LABELS.get(choice, "Legacy input — source convention not selected"),
        key="igird_axial_input_sign",
        help="Keep the imported signs. CSiBridge frame P is positive in tension; the app converts Nu before section equilibrium and the AASHTO checks. Select already-converted only if your table is compression-positive.")
    # Render alone does not silently declare a legacy input. A changed choice
    # is an explicit declaration; corrected supplied projects include it.
    if selected is not None:
        cfg = {"input_sign": selected}
        st.session_state[SETTINGS_KEY] = cfg
        metadata = dict(st.session_state.get("project_metadata") or {})
        metadata[SETTINGS_KEY] = cfg
        st.session_state["project_metadata"] = metadata
    elif current["declared"]:
        st.session_state.pop(SETTINGS_KEY, None)
        metadata = dict(st.session_state.get("project_metadata") or {})
        metadata.pop(SETTINGS_KEY, None)
        st.session_state["project_metadata"] = metadata
    if selected == CSI_TENSION_POSITIVE:
        st.caption("CSiBridge P is kept in Loads. Solver Nu = −P (positive compression); AASHTO tension-positive Nu = P. Mux, Muy, Vuy, Vux and Tu retain their entered signs and the existing axis mapping.")
    elif selected is not None:
        st.caption("Solver Nu equals the entered compression-positive Nu. AASHTO tension-positive Nu = −Nu. Imported table values are preserved.")
    if selected is None:
        st.warning("Legacy project: Nu convention has not been declared; compression-positive behavior is retained. For an unchanged CSiBridge P table, select CSiBridge / CSI frame P before Calculate.")
