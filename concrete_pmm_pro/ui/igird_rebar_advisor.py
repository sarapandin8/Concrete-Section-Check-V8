"""Explicit Analysis-only trial calculation; production inputs/results stay owned.

The sizing table is a read-only view of hash-current stored results. Trial output
has a separate runtime key, is never published to Summary/Report, and disappears
from view when model, loads, options or the proposed layout changes.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import igird_rebar_advisor as advisor
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY
from concrete_pmm_pro.ui.result_table_display import result_table_for_display

RUNTIME_KEY = "_igird_rebaradvisor_trial_runtime"


def current_packages(state, rows_by_member, *, route, selected_results=None, selected_check=None):
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    packages = {}
    cache = state.get(mr.CACHE_KEY, {})
    for member, rows in rows_by_member.items():
        package = {}
        for check in ("Shear", "Torsion", "Shear + Torsion"):
            fingerprint = mr.result_hash(state, rows, check_name=check, route=route)
            result = mr.current_result(cache, member, check, fingerprint)
            if result is None and member == state.get(ACTIVE_KEY):
                result = ap._beam_uls_current_cached_result(state, check, fingerprint)
            if check == selected_check and selected_results is not None:
                result = selected_results.get(member)
            if isinstance(result, dict) and not result.get("error"):
                package.update({key: result[key] for key in advisor.FRAME_KINDS if isinstance(result.get(key), pd.DataFrame)})
        packages[member] = package
    return packages


def signature(state, rows_by_member, layout, *, route, options):
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    hashes = [mr.result_hash(state, rows, check_name="Shear + Torsion", route=route)
              for rows in rows_by_member.values()]
    normalized = ap._beam_uls_shear_reinforcement_dataframe_from_state({advisor.TABLE_KEY: layout})
    payload = repr((advisor.VERSION, list(rows_by_member), hashes, options)) + normalized.to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculate_trial(state, rows_by_member, layout, *, route, calculator=None, progress=None):
    """Only a button owner may call this; no mutable state or cache is returned."""
    from concrete_pmm_pro.ui import igird_member_results as mr, igird_shear_section
    calculate = calculator or mr.calculate_member
    local = deepcopy({key: value for key, value in dict(state).items()
                      if key not in {RUNTIME_KEY, mr.CACHE_KEY, igird_shear_section.RUNTIME_KEY}})
    local[advisor.TABLE_KEY] = layout.copy(deep=True)
    results = {}
    for member, rows in rows_by_member.items():
        if progress:
            progress(member)
        results[member] = calculate(local, rows.copy(deep=True), check_name="Shear + Torsion", route=route)
    return results


def _render_actions(actions, *, key):
    columns = ["Girder", "Zone", "Issue", "Required action", "Status", "Governing x m", "D/C"]
    st.dataframe(result_table_for_display(actions[columns]), hide_index=True, use_container_width=True,
        column_config={"Required action": st.column_config.TextColumn(width="large"),
            "D/C": st.column_config.NumberColumn(format="%.3f"),
            "Governing x m": st.column_config.NumberColumn("x m", format="%.2f")})
    if st.session_state.get(key, 0) not in range(len(actions)):
        st.session_state[key] = 0
    selected = st.selectbox("Action details — อ่านคำแนะนำและ case ที่คุม", range(len(actions)), key=key,
        format_func=lambda i: f"{actions.iloc[i]['Girder']} · {actions.iloc[i]['Zone']} · {actions.iloc[i]['Issue']}")
    row = actions.iloc[selected]
    st.info(str(row["Required action"]))
    st.caption(f"{row['Status']} · x={row['Governing x m']:.3f} m · {row['Affected rows']} affected row(s) · {row['Case']}")


def render_advisor(state, rows_by_member, packages, *, route, key_prefix="collection", allow_trial=True):
    if not any(package for package in packages.values()):
        return
    from concrete_pmm_pro.ui import analysis_page as ap
    layout = ap._beam_uls_shear_reinforcement_dataframe_from_state(state)
    st.markdown("##### Reinforcement advisor — ตำแหน่งและวิธีแก้ไข")
    st.caption("ใช้ทุก case และทุก station ที่คำนวณแล้วของทุกคานกับช่วงปลอกร่วมกัน จุด Governing ระบุแรงที่คุม; ข้อเสนอใช้ตลอดช่วง Zone ไม่ใช่เฉพาะจุดที่แสดงบนกราฟ")
    with st.expander("Trial options — ข้อกำหนดระยะสำหรับชุดทดลอง", expanded=False):
        cols = st.columns(2)
        minimum = cols[0].number_input("Minimum trial spacing (mm)", min_value=10.0, max_value=200.0,
            value=50.0, step=10.0, key="igird_advisor_min_" + key_prefix,
            help="ระยะขั้นต่ำที่ผู้ใช้ยอมให้ลองเพื่อพิจารณาการจัดเหล็ก เป็น trial screen ไม่ใช่ระยะขั้นต่ำจากมาตรฐาน")
        step = cols[1].number_input("Spacing increment (mm)", min_value=5.0, max_value=50.0,
            value=10.0, step=5.0, key="igird_advisor_step_" + key_prefix)
        st.caption("ลองลดระยะโดยคงขนาดเดิมก่อน ถ้าต่ำกว่าระยะขั้นต่ำที่เลือกจึงลอง DB16/20/25/32; คงจำนวนขาและ fy เดิม และไม่ขยายระยะเดิม ต้องตรวจพื้นที่จัดเหล็ก cover และ hook จากแบบจริง")
    options = advisor.Options(minimum_spacing_mm=float(minimum), spacing_step_mm=float(step))
    proposal = advisor.recommend(layout, packages, options=options)
    if proposal.zones.empty:
        st.warning("LAYOUT REQUIRED — กำหนดและเปิดใช้ช่วงเหล็กปลอกใน Sections → Rebar ก่อนให้แอปแนะนำขนาด/ระยะ")
        return
    missing_members = [member for member, package in packages.items() if not package]
    if missing_members:
        st.warning("ข้อมูลผลคำนวณยังไม่ครบทุกคาน: " + "; ".join(missing_members) + ". Calculate สำหรับ inputs ปัจจุบันก่อนใช้ชุดแนะนำร่วมกัน")
    if not proposal.complete_combined:
        st.info("PRELIMINARY — ยังไม่มีผล Shear + Torsion ปัจจุบันครบทุกคาน ข้อเสนอจาก checks ที่มีต้องตรวจ combined V+T ด้วยปุ่มชุดทดลองด้านล่าง")
    compact = ["Zone", "x start m", "x end m", "Current", "Proposed trial", "Action",
               "Before φTn D/C", "Before V+T transverse D/C", "Governing girder", "Governing x m"]
    st.dataframe(result_table_for_display(proposal.zones[compact]), hide_index=True, use_container_width=True,
        column_config={"x start m": st.column_config.NumberColumn("Start m", format="%.2f"),
            "x end m": st.column_config.NumberColumn("End m", format="%.2f"),
            "Before φTn D/C": st.column_config.NumberColumn("φTn D/C", format="%.3f"),
            "Before V+T transverse D/C": st.column_config.NumberColumn("V+T D/C", format="%.3f"),
            "Governing x m": st.column_config.NumberColumn("Gov. x m", format="%.2f")})
    st.caption("Proposed trial เป็นขนาด/ระยะที่ได้จาก required Av/s และ At/s ในผลปัจจุบัน ยังต้องคำนวณซ้ำ เพราะ ph, εs, θ, development และแรงตามยาวอาจคุมผล การผ่านตัวเลขปลอกไม่ยืนยัน overall PASS")
    with st.expander("Governing cases / sampled failure locations — ที่มาข้อเสนอ", expanded=False):
        st.dataframe(result_table_for_display(proposal.zones), hide_index=True, use_container_width=True)
        st.caption("Failed sampled x เป็นตำแหน่งที่มีข้อมูลตรวจจริง ไม่ใช่ขอบเขตต่อเนื่องของ failure; ข้อเสนอครอบคลุมทั้ง Zone ที่มีอยู่")
    if not proposal.actions.empty:
        with st.expander("Required actions beyond stirrups — สาเหตุที่ต้องแก้ร่วมกัน", expanded=True):
            _render_actions(proposal.actions, key="igird_advisor_action_" + key_prefix)
            st.caption("ตรวจแถว Longitudinal force / Pretensioned steel condition ก่อนเพิ่มเหล็กตามยาว; ตรวจ Force concurrency, development และ interface ก่อนยืนยันการออกแบบ")
    if not allow_trial:
        return
    trial_hash = signature(state, rows_by_member, proposal.layout, route=route, options=options)
    saved = state.get(RUNTIME_KEY)
    if isinstance(saved, dict) and saved.get("signature") != trial_hash:
        st.caption("STALE — ชุดทดลองก่อนหน้าไม่ตรง inputs/options ปัจจุบัน กด Calculate trial ใหม่")
        saved = None
    ready = proposal.can_verify and not missing_members
    if not proposal.can_verify:
        st.warning("DATA / LAYOUT REVIEW — มีช่วงปลอก ข้อมูล transverse หรือ coverage ที่ไม่ครบ ตรวจรายละเอียดในตารางก่อนคำนวณชุดทดลอง")
    if st.button("Calculate trial — ตรวจชุดปลอกที่แนะนำทุกคาน", key="igird_advisor_calculate_" + key_prefix, disabled=not ready):
        with st.spinner("คำนวณ Shear + Torsion ด้วยชุดปลอกทดลองสำหรับทุก case ของทุกคาน…"):
            results = calculate_trial(state, rows_by_member, proposal.layout, route=route)
        saved = {"signature": trial_hash, "layout": proposal.layout.copy(deep=True),
                 "results": results, "summary": advisor.trial_summary(results)}
        state[RUNTIME_KEY] = saved
    if not isinstance(saved, dict):
        return
    st.markdown("###### Trial verification — ผลหลังปรับปลอก")
    errors = [f"{member}: {result['error']}" for member, result in saved["results"].items() if result.get("error")]
    if errors:
        st.error("TRIAL INCOMPLETE — " + "; ".join(errors))
    summary = saved["summary"]
    if not summary.empty:
        columns = [c for c in ("Girder", "Zone", "φTn D/C", "V+T transverse D/C", "Spacing D/C", "Longitudinal D/C", "Stress D/C", "Transverse verification", "Overall V+T") if c in summary]
        st.dataframe(result_table_for_display(summary[columns]), hide_index=True, use_container_width=True,
            column_config={c: st.column_config.NumberColumn(format="%.3f") for c in columns if c.endswith("D/C")})
        if summary["Transverse verification"].eq("MEETS NUMERIC CHECKS").all() and not errors:
            st.success("ชุดปลอกทดลองผ่านตัวเลข φTn / transverse V+T / shear / ระยะปลอก ณ station ที่คำนวณแล้ว ตรวจ Overall V+T และ Required actions ที่เหลือด้านล่างก่อนยืนยันแบบ")
        else:
            st.warning("ชุดทดลองยังมี transverse / detailing ที่ไม่ผ่านหรือข้อมูลไม่ครบ ตรวจ trial audit ก่อนปรับชุดถัดไป")
    st.caption("ผลชุดทดลองแยกจากผลออกแบบปัจจุบัน Inputs ยังใช้ปลอกเดิม หากเลือกใช้ชุดนี้ให้แก้ใน Sections → Rebar แล้ว Calculate production ใหม่; Result Summary / Report ใช้ผล production เท่านั้น")
    trial_issues = advisor.remaining_issues(saved["results"])
    remaining = advisor.action_summary(trial_issues)
    if not remaining.empty:
        with st.expander("Trial remaining actions — รายการที่ยังไม่ผ่านหลังเพิ่มปลอก", expanded=True):
            _render_actions(remaining, key="igird_advisor_trial_action_" + key_prefix)
    with st.expander("Trial audit / downloads — ผลตรวจและตารางปลอกทดลอง", expanded=False):
        st.dataframe(result_table_for_display(summary), hide_index=True, use_container_width=True)
        st.download_button("Download proposed stirrup layout (CSV)", saved["layout"].to_csv(index=False).encode("utf-8-sig"),
            file_name="igird_rebaradvisor13_trial_stirrups.csv", mime="text/csv", key="igird_advisor_layout_" + key_prefix)
        st.download_button("Download trial verification (CSV)", summary.to_csv(index=False).encode("utf-8-sig"),
            file_name="igird_rebaradvisor13_trial_verification.csv", mime="text/csv", key="igird_advisor_summary_" + key_prefix)
        if not remaining.empty:
            st.download_button("Download remaining actions (CSV)", remaining.to_csv(index=False).encode("utf-8-sig"),
                file_name="igird_rebaradvisor13_trial_remaining_actions.csv", mime="text/csv", key="igird_advisor_remaining_" + key_prefix)
        for member, result in saved["results"].items():
            frame = result.get("combined_vt_df")
            if isinstance(frame, pd.DataFrame):
                st.markdown("**" + member + " — all trial source rows**")
                st.dataframe(result_table_for_display(frame), hide_index=True, use_container_width=True)
