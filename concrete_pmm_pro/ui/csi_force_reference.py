"""Small source-reference panel shared by ULS and SLS; input state only."""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from concrete_pmm_pro.io.csi_force_reference import (
    SETTINGS_KEY, SNAPSHOT_KEY, canonical_profile, configured_profile,
    bind_reference, profile_from_payload,
)
from concrete_pmm_pro.io.girder_csi_import import source_info


def bind_current_sources(state, profile):
    """Bind explicitly selected CSI origins, preserving all numerical actions."""
    from concrete_pmm_pro.io import girder_sls_import as sls
    from concrete_pmm_pro.io import girder_load_bank as uls
    uls.save_active(state)
    sls.save_active(state)
    changed = 0
    for key in (uls.BANK_KEY, "beam_uls_loads_table", sls.BANK_KEY, sls.TABLE_KEY):
        if key not in state:
            continue
        before = pd.DataFrame(state[key])
        after = bind_reference(before, profile, replace=True)
        if "Note" in after:
            changed += sum(source_info(row) is not None for _, row in after.iterrows())
        state[key] = after
    # Numerical results for a different origin are stale, not reusable.
    for key in list(state):
        if (str(key) in {"_beam_uls_manual_calc_cache", "igird_member_results"}
                or str(key).startswith("result_summary_beam_girder_sls_")):
            state.pop(key, None)
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    state.pop(ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY, None)
    state.pop(mr.CACHE_KEY, None)
    return changed


def save_profile(state, profile, *, bind_loaded=True):
    cfg = canonical_profile(profile)
    metadata = dict(state.get("project_metadata") or {})
    metadata[SETTINGS_KEY] = cfg
    state["project_metadata"] = metadata
    if bind_loaded:
        bind_current_sources(state, cfg)
    return cfg


def source_summary(state):
    from concrete_pmm_pro.io.girder_load_bank import BANK_KEY
    from concrete_pmm_pro.io.girder_sls_import import BANK_KEY as SLS_BANK
    rows = {}
    for key, label in ((BANK_KEY, "ULS"), (SLS_BANK, "SLS")):
        for _, row in pd.DataFrame(state.get(key, [])).iterrows():
            info = source_info(row) or {}
            cfg = info.get(SNAPSHOT_KEY)
            if cfg:
                identity = (label, info.get("source_sha256") or info.get("source_file"),
                            cfg.get("profile_sha256"))
                rows[identity] = {"Loads": label, "Source file": info.get("source_file"),
                    "CSI depth below deck top (m)": cfg["depth_below_deck_top_m"],
                    "Local-3 offset from web (m)": cfg["local3_offset_from_web_m"],
                    "Force kind": cfg["force_kind"]}
    return pd.DataFrame(rows.values())


def render_settings(*, key_prefix):
    current = configured_profile(st.session_state)
    if current:
        st.caption(f"CSI reference: {current['depth_below_deck_top_m']:.6f} m below deck top · "
            f"{current['horizontal_location']} · source snapshots retained.")
    else:
        st.caption("CSI reference is not configured. Existing load behavior is retained; "
            "set the reporting point to enable automatic moment transport.")
    with st.expander("CSI force output reference", expanded=False):
        st.caption("One setting per CSI model/section. Save binds the current CSI files; "
            "new imports retain their own source snapshot. Changing Section Builder "
            "recalculates resistance origins without changing the original force origin.")
        uploaded = st.file_uploader("Read CSI section reference", type=["json", "csv", "xlsx"],
            key=key_prefix + "_ref_file",
            help="Reference JSON, or a full CSI Section Points table in m. "
                 "Mixed-material sections require reported CSI Ycg.")
        if isinstance(uploaded, list):
            uploaded = None  # This single-file control never consumes Loads batches.
        parsed = None
        if uploaded:
            try:
                parsed = profile_from_payload(uploaded.getvalue(), uploaded.name)
                st.info(f"Detected CSI reporting depth: {parsed['depth_below_deck_top_m']:.6f} m")
            except (ValueError, TypeError, KeyError, OSError) as exc:
                st.error(str(exc))
        preset = parsed or current or {}
        # Form keys include source content, so changing the reference file does
        # not retain the numeric widget value of a previous CSI section.
        signature = str(preset.get("profile_sha256", "unset"))[:12]
        with st.form(key_prefix + "_ref_form_" + signature):
            depth = st.number_input("CSI reporting depth below deck top (m)", min_value=0.,
                value=float(preset.get("depth_below_deck_top_m", 0)), step=.01, format="%.6f")
            offset = st.number_input("CSI reporting offset along local 3 from web (m)",
                value=float(preset.get("local3_offset_from_web_m", 0)), step=.01, format="%.6f",
                help="Center of Girder Web = 0. Positive follows CSI local 3 / section view left-to-right.")
            kinds = ["GIRDER_COMPOSITE", "BEAM_ONLY"]
            kind = st.selectbox("CSI force result", kinds,
                index=kinds.index(preset.get("force_kind", "GIRDER_COMPOSITE")),
                format_func=lambda v: "Girder — beam + deck slab" if v == "GIRDER_COMPOSITE" else "Beam only")
            apply = st.form_submit_button("Save CSI reference and apply to current files")
        if apply:
            try:
                cfg = save_profile(st.session_state, {**preset,
                    "depth_below_deck_top_m": depth, "local3_offset_from_web_m": offset,
                    "force_kind": kind, "basis": preset.get("basis", "Entered CSI output location")})
                from concrete_pmm_pro.ui.loads_page import _sync_workflow_load_tables_metadata
                _sync_workflow_load_tables_metadata()
                st.success("CSI reference saved. Recalculate Analysis for the current section.")
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        if current:
            st.download_button("Download CSI reference JSON",
                json.dumps(current, ensure_ascii=False, indent=2).encode(),
                file_name="CSiBridge_force_reference.json", mime="application/json",
                key=key_prefix + "_ref_json")
        summary = source_summary(st.session_state)
        if not summary.empty:
            st.dataframe(summary, hide_index=True, use_container_width=True)
        st.caption("Force transport does not verify composite shear–torsion reinforcement "
            "or interface action. Those resistance mechanisms remain separately qualified.")
