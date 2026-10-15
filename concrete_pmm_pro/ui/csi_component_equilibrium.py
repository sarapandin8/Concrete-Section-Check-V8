"""Optional read-only component-force evidence in the existing Loads uploader."""
import streamlit as st
from concrete_pmm_pro.analysis.csi_component_equilibrium import audit_payload


@st.cache_data(show_spinner=False, max_entries=8, ttl=3600)
def _read_audit(payload, filename, source_mode, concurrency_confirmed, evidence):
    return audit_payload(payload, filename, source_mode=source_mode,
        concurrency_confirmed=concurrency_confirmed, evidence=evidence)


def render_component_equilibrium(files, *, source_mode, concurrency_confirmed, evidence, key_prefix):
    reports = []
    for index, uploaded in enumerate(files):
        try:
            report = _read_audit(uploaded.getvalue(), uploaded.name, source_mode, concurrency_confirmed, evidence)
        except Exception:
            continue  # The existing importer owns format errors and import eligibility.
        if not report.summary.empty:
            reports.append((index, uploaded.name, report))
    if not reports:
        return
    with st.expander("Girder / Beam / Slab force equilibrium", expanded=False):
        st.caption("Girder = Beam + Slab after translating all moments to the same point. "
            "This audit does not change Loads, strength, or Analysis acceptance.")
        st.caption("A small Beam torque alone does not establish assembly safety; slab, interface and connection actions still require resistance checks.")
        for index, filename, report in reports:
            st.markdown("**" + filename.replace("*", "") + "**")
            columns = [c for c in ("Girder", "Case", "Step", "Matched cuts", "Audit status",
                "Max force residual kN", "Max moment residual kN-m", "Holdout moment residual kN-m", "Reason")
                if c in report.summary]
            st.dataframe(report.summary[columns], hide_index=True, use_container_width=True)
            if report.trace.empty:
                continue
            st.caption("Offsets below are empirical fits from P/M2/M3, checked against torque at held-out stations. "
                "They are not CSI origin metadata and are not applied to the project reference setting.")
            st.dataframe(report.offsets[["Girder", "Case", "Component", "C_component-C_G local2 m",
                "C_component-C_G local3 m"]], hide_index=True, use_container_width=True)
            # A reported cut is selected independently per Girder and source state.
            grouping = ["Bridge", "Girder", "Case", "Step", "Step number"]
            peak_indices = report.trace.groupby(grouping, dropna=False)["Girder T"].apply(lambda s: s.abs().idxmax())
            columns = ["Girder", "Station x (m)", "Occurrence", "Beam T at B kN-m", "Slab T at S kN-m",
                "Beam r2V3 kN-m", "Slab r2V3 kN-m", "Beam -r3V2 kN-m", "Slab -r3V2 kN-m",
                "Rebuilt T", "Girder T", "Residual T"]
            st.caption("Torque components at the largest |Girder T| in each source state (kN-m).")
            st.dataframe(report.trace.loc[peak_indices, columns], hide_index=True, use_container_width=True)
            st.download_button("Download component force audit (CSV)",
                report.trace.to_csv(index=False).encode("utf-8-sig"),
                file_name="CSI_component_force_audit.csv", mime="text/csv",
                key=key_prefix + "_component_audit_" + str(index))
