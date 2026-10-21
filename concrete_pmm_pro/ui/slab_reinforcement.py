"""Compact native shell-import workspace and entry to the slab section review."""
from __future__ import annotations

from math import isfinite
import pandas as pd
import streamlit as st

from concrete_pmm_pro.core.design_code import workflow_project_code_label_from_session
from concrete_pmm_pro.io import slab_shell_import as source
from concrete_pmm_pro.ui.commercial import render_metric_cards, render_page_header, render_section_bar


def _compact_context() -> None:
    # Reuse SLS54's screen inset for the toolbar, scoped to the two slab pages.
    st.html('''<style>@media screen{
      [data-testid="stMainBlockContainer"]:has(.st-key-slab_shell55_nav){padding-top:4.75rem!important}
    }</style>''')
    st.caption(workflow_project_code_label_from_session(st.session_state) +
        " · CSI shell package: kN/m, kN·m/m; coordinates / thickness: m")


def export_guide() -> str:
    lines = ["# CSiBridge deck slab import — " + source.VERSION, "",
        "Upload complete native .xlsx exports. Keep every worksheet, title, header and units row.",
        "Filenames are examples; tables are detected by column schema. The four sets may be combined in one workbook.",
        "Export in kN, m. Shell forces: kN/m; shell moments: kN-m/m; geometry and thickness: m.", ""]
    for i, row in enumerate(source.FILE_GUIDE, 1):
        lines += [f"{i}. {row['File / export set']}", f"   Tables: {row['Required tables']}", f"   Use: {row['Use']}", ""]
    lines += ["* The Advanced axes table is required where AdvanceAxes = Yes; this applies to the supplied model.",
        "Keep all design cases (for example U1A, U1B, U2A, U2B), with every exported Max/Min or static-result row. New equivalent-train-load case names are accepted. Supplied force components in each row are taken as concurrent, per the project input basis.",
        "StepType is optional when CSI omits the column. The app retains an empty step identity, without creating Max/Min or changing any force. Repeated case/corner records still require distinct exported step identities.",
        "Keep generated ~ joints in Objects And Elements - Joints; original Joint Coordinates alone does not cover the analysis mesh.",
        "Keep Thick1..4 and original Joint1..4 order for variable-thickness areas.",
        "Keep BridgeObj, BOSpan, StartSta and EndSta in Area Bridge Object Flags; station progression defines the straight bridge reinforcement directions.",
        "Top Slab is selected from CompType; diaphragm results stay in the source package and are excluded from slab checks.",
        "Keep Connectivity - Frame in the complete Connectivity Data export: its frame endpoints locate the I-girder connection lines. No additional workbook is needed.",
        "Program Control, Links, Auto Mesh and Edge Constraints may stay; they are not used by this import route.",
        "The latest Objects And Elements export containing both Areas and Joints replaces the older Areas-only workbook.",
        "No stress workbook, load-combination definitions or moving-load recording-settings export is required for this workflow.",
        "For a new equivalent train UDL analysis, re-export the same four complete sets together. Actions are already factored CSI results: the app applies no further impact / load factor, force-reference shift or ballast redistribution. Record ballast and the actual UDL basis in Analysis > Slab Reinforcement > CSI load basis / Ballast.",
        "Materials, code and four slab reinforcement groups are read from the current project inputs. Punching additionally needs physical load-area X/Y/L/B; no load-area dimensions are inferred from shell-force peaks.",
        "Analysis > Slab Reinforcement calculates AASHTO LRFD 2020 directional N-M, shear and tension-side shear-tie component checks with the existing four physical reinforcement mats.",
        "Agreed girder/diaphragm lines, bearing end zones and the fixed REVIEW61 isolated-peak rule are excluded before resistance evaluation; original source actions remain in the audit.",
        "Four-mat temperature/spacing, sufficient flexural minimum and required development length are calculated. Girder and diaphragm face samples use the existing flange width / exported shell thickness, with no dv relaxation. Shell coupling, local support/load-path qualification, actual anchorage, fatigue and SLS remain separate. Punching has its own loaded-area normal-force check; existing Final Composite longitudinal interface results are linked read-only by current input hashes. Optional legacy research and zone averages are folded away.",
        "Save Project JSON includes the imported shell tables, units and source file identities. Reopening that JSON restores them automatically; re-upload only to replace the analysis data. Calculate slab checks again after loading."]
    return "\n".join(lines) + "\n"


def _guide() -> None:
    st.markdown("**Upload the 4 complete export sets — keep all worksheets**")
    st.caption("Select complete Excel exports together. Keep filenames and all worksheets; tables are matched automatically.")
    st.dataframe(pd.DataFrame([
        {"Export set": i, "Example filename": row["File / export set"], "Contents": contents}
        for i, (row, contents) in enumerate(zip(source.FILE_GUIDE, (
            "Shell forces · ULS cases", "Analysis Areas + Joints (including ~ nodes)",
            "Area flags, thickness, sections, local axes", "Original Areas + Joint Coordinates")), 1)
    ]), hide_index=True, use_container_width=True,
        column_config={"Export set": st.column_config.NumberColumn(width="small"),
            "Example filename": st.column_config.TextColumn(width="large")})
    with st.expander("CSiBridge tables to export", expanded=False):
        for i, row in enumerate(source.FILE_GUIDE, 1):
            st.markdown(f"**{i}. {row['File / export set']}**")
            st.markdown("\n".join(f"- `{table.strip()}`" for table in row["Required tables"].split(";")))
            st.caption(row["Use"])
        st.caption("* Advanced axes is required where AdvanceAxes = Yes, as in the supplied model. Sheet names may omit Assignments.")
        st.markdown("Export in **kN, m**. Keep all ULS cases and every Max/Min or static-result row. New equivalent-UDL case names are accepted.")
        st.caption("StepType may be blank or absent in a native CSI export. It is retained as blank; do not add artificial Max/Min rows.")
        st.caption("After reanalysis with equivalent train loading, export the same four sets together. Imported strength forces are used directly, without multiplying impact / load factors or dispersing them through ballast again.")
        st.caption("Keep Connectivity - Frame for I-girder connection geometry, plus the other worksheets in the complete exports. The latest Areas + Joints export replaces the older Areas-only file.")
        st.download_button("Download export checklist", export_guide(),
            file_name="CSiBridge_Deck_Slab_Export_Checklist.txt", mime="text/plain", key="slab_shell55_guide")


def _overview(package: source.ShellPackage) -> None:
    from concrete_pmm_pro.analysis.slab_review68 import current
    result=current(st.session_state)
    summary = package.summary
    render_metric_cards([
        {"title": "Imported Top Slab", "value": f"{summary['slab_elements']:,} elements", "detail": f"{summary['slab_objects']:,} Area objects", "status": "info"},
        {"title": "Slab force records", "value": f"{summary['slab_force_rows']:,}", "detail": f"{summary['excluded_force_rows']:,} non-slab records excluded from slab view", "status": "info"},
        {"title": "Thickness from CSI", "value": f"{summary['thickness_min_mm']:g}–{summary['thickness_max_mm']:g} mm", "detail": "Object corner overwrites; variable thickness retained", "status": "neutral"},
        {"title": "AASHTO components", "value": result['component_status'] if result else "NOT CALCULATED", "detail": "Analysis → Slab Reinforcement · complete deck acceptance remains separate", "status": "warning"},
    ])
    st.caption("Cases: " + ", ".join(summary["cases"]) + " · F / V: kN/m · M: kN·m/m · Coordinates: m")


def _audit(package: source.ShellPackage) -> None:
    with st.expander("Imported tables / validation details", expanded=False):
        if package.missing:
            st.markdown("**Missing tables**")
            for spec in package.missing:
                st.markdown(f"- {spec.title} — export set {spec.group}")
        for error in package.errors:
            st.error(error)
        for note in package.notes:
            st.caption(note)
        if package.sources:
            st.dataframe(pd.DataFrame(package.sources), hide_index=True, use_container_width=True)
        if package.summary:
            st.dataframe(package.summary["case_rows"], hide_index=True, use_container_width=True)
        st.caption("Validation covers table presence, units, numeric fields, unique record keys, parent/element/corner joins and coordinate coverage. It does not check slab resistance or certify shell-axis transformations.")
        st.caption("Components in each supplied row are taken as concurrent per the project input basis. All eight components and case/step identities are retained; no component-wise design envelope is assembled during import.")


def render_import_page() -> None:
    _compact_context()
    render_page_header("Slab Shell Results", "Import CSiBridge shell demands for top and bottom deck reinforcement in both directions.",
        icon="SL", kicker="Loads / Deck slab", badge="Input package", accent="amber")
    _guide()
    revision = st.session_state.get("slab_shell55_upload_revision", 0)
    uploads = st.file_uploader("CSiBridge Excel files — select all export sets", type=["xlsx"],
        accept_multiple_files=True, key=f"slab_shell55_uploads_{revision}",
        help="Keep complete native CSI exports, including headers and units. The tables may be spread across several files or combined.")
    if uploads:
        st.session_state[source.PENDING_KEY] = source.upload_signature(uploads)
    cols = st.columns([2, 1])
    with cols[0]:
        clicked = st.button("Import & validate shell data", type="primary", disabled=not uploads,
            use_container_width=True, key="slab_shell55_import")
    with cols[1]:
        clear = st.button("Clear shell package", disabled=source.BANK_KEY not in st.session_state,
            use_container_width=True, key="slab_shell55_clear")
    if clear:
        st.session_state.pop(source.BANK_KEY, None)
        st.session_state.pop(source.PENDING_KEY, None)
        st.session_state.pop("slab_shell55_restored_from_project", None)
        st.session_state.pop("slab_shell55_strength56_result", None)
        st.session_state.pop("slab_shell55_aashto62_result", None)
        st.session_state.pop("slab_shell55_aashto62_csv_payload", None)
        st.session_state.pop("slab_shell55_aashto63_faces_payload", None)
        st.session_state.pop("slab_shell55_shear64_result", None)
        st.session_state.pop("slab_shell55_top65_result", None)
        st.session_state.pop("slab_shell55_design66_result", None)
        st.session_state.pop("slab_shell55_review68_result", None)
        st.session_state.pop("slab_shell55_top65_report", None)
        st.session_state["slab_shell55_upload_revision"] = revision + 1
        st.rerun()
    if clicked:
        st.session_state.pop("slab_shell55_restored_from_project", None)
        st.session_state.pop("slab_shell55_strength56_result", None)
        st.session_state.pop("slab_shell55_aashto62_result", None)
        st.session_state.pop("slab_shell55_aashto62_csv_payload", None)
        st.session_state.pop("slab_shell55_aashto63_faces_payload", None)
        st.session_state.pop("slab_shell55_shear64_result", None)
        st.session_state.pop("slab_shell55_top65_result", None)
        st.session_state.pop("slab_shell55_design66_result", None)
        st.session_state.pop("slab_shell55_review68_result", None)
        st.session_state.pop("slab_shell55_top65_report", None)
        with st.spinner("Reading complete CSI workbooks and matching shell records…"):
            package = source.parse_files(uploads)
            st.session_state[source.BANK_KEY] = package
            st.session_state[source.PENDING_KEY] = package.signature
        # The sidebar's download payload is rendered before this page. Refresh
        # it now so the next Save includes this import, not the previous bank.
        st.rerun()
    package = st.session_state.get(source.BANK_KEY)
    if isinstance(package, source.ShellPackage):
        if source.current_package(st.session_state) is not None:
            st.success("IMPORTED — required tables and input links are available. Open Slab Reinforcement to calculate or review section checks.")
            if st.session_state.get("slab_shell55_restored_from_project"):
                st.caption("Restored from Project JSON — shell inputs are ready. Calculate slab checks again; upload Excel only to replace the data.")
            _overview(package)
            if st.button("Open Slab Reinforcement →", key="slab_shell55_open_analysis"):
                st.session_state["_nav_active_workspace"] = "Analysis"
                st.session_state["_nav_analysis_subpage"] = "Slab Reinforcement"
                st.rerun()
        elif package.ready:
            st.warning("STALE — selected files differ from the imported package. Press Import & validate to replace it.")
        else:
            missing = "; ".join(s.title for s in package.missing)
            st.warning("INCOMPLETE — " + ("Missing: " + missing if missing else "Resolve the import errors below."))
            for error in package.errors[:4]:
                st.error(error)
        _audit(package)
    else:
        st.info("No shell data imported. Select the Excel exports and press Import & validate shell data.")
    st.caption("Save Project JSON includes the last imported shell package. Import selected replacement files before saving. Reopening the saved JSON restores the inputs automatically.")


def reinforcement_inventory(state) -> pd.DataFrame:
    from concrete_pmm_pro.analysis.igird_dowel_detail35 import mesh_inventory
    from concrete_pmm_pro.analysis.igird_slab_layers import detail_from_state
    rows = mesh_inventory(detail_from_state(state), dict(state.get("section_parameters") or {}))
    output = []
    for row in rows:
        fields = ("Diameter_mm", "Spacing_mm", "Clear_cover_mm", "fy_MPa", "As_mm2_per_m")
        complete = all(row.get(k) is not None and isfinite(float(row[k])) and float(row[k]) > 0 for k in fields)
        output.append({"Layer": row["Layer"], "Direction": "Longitudinal" if row["Direction"] == "Along girder" else "Transverse",
            "Bar (mm)": row["Diameter_mm"], "Spacing (mm)": row["Spacing_mm"],
            "Clear cover (mm)": row["Clear_cover_mm"], "fy (MPa)": row["fy_MPa"],
            "As (mm²/m)": row["As_mm2_per_m"], "Input status": "Available" if complete else "Missing input"})
    return pd.DataFrame(output)


def render_analysis_page() -> None:
    _compact_context()
    from concrete_pmm_pro.ui.slab_top65_workspace import render
    from concrete_pmm_pro.analysis import slab_review68
    render(analysis_engine=slab_review68)
