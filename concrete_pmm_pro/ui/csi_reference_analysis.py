"""Analysis readers for CSI source origins; never mutate persisted Loads."""
from __future__ import annotations
from functools import wraps
import inspect
import math
import pandas as pd
from concrete_pmm_pro.io import csi_force_reference as ref
from concrete_pmm_pro.io.girder_csi_import import source_info


def convert_for_check(state, row, *, check_name, geometry=None):
    if ref.SNAPSHOT_KEY not in (source_info(row) or {}):
        return dict(row)
    from concrete_pmm_pro.ui import igird_shear_section as shear
    from concrete_pmm_pro.ui import igird_station_section as station
    params = state.get("section_parameters") or {}
    if geometry is None:
        if check_name in {"Shear", "Shear + Torsion"}:
            prepared = shear.prepared_section(state)
            if not prepared.get("ready"):
                raise ValueError("Resistance geometry is unavailable for CSI reference transport.")
            geometry = prepared["state"]["section_geometry"]
        else:
            geometry = state.get(station.WEB_GEOMETRY, state.get("section_geometry")) if check_name == "Torsion" else state.get("section_geometry")
    metadata = getattr(geometry, "metadata", {}) or (geometry.get("metadata", {}) if isinstance(geometry, dict) else {})
    includes_deck = "composite" in str(metadata.get("preset", ""))
    origin = ref.geometry_origin(geometry, deck_thickness_mm=params.get("Tslab_mm", 0),
        includes_deck=includes_deck)
    converted = ref.translate_row(row, origin=origin)
    if check_name in {"Torsion", "Shear + Torsion"}:
        # CSITU46: the imported scalar torque stays at the CSI reporting point.
        # Bending readers retain their existing origins; no resistance upgrade
        # or equivalence of this mixed-reference screening vector is inferred.
        converted = ref.retain_reported_torsion(converted)
    return converted


def dataframe_reader(check_name):
    def decorate(fn):
        signature = inspect.signature(fn)
        @wraps(fn)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            state = bound.arguments["state"]
            source = ref.prepare_analysis_frame(bound.arguments["active_df"])
            if check_name == "Flexure":
                from concrete_pmm_pro.ui.igird_station_section import at_station
                values = []
                for _, row in source.iterrows():
                    local = at_station(state, row["Station x (m)"])
                    values.append(convert_for_check(local, row, check_name=check_name))
                source = pd.DataFrame(values, index=source.index) if values else source
            bound.arguments["active_df"] = source
            value = fn(*bound.args, **bound.kwargs)
            frame = value[0] if isinstance(value, tuple) else value
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                frame = frame.copy(deep=True)
                for index, result in frame.iterrows():
                    candidates = source[source["Case Name"].astype(str).eq(str(result.get("Case", "")))]
                    try:
                        x = float(result.get("Source station x (m)", result.get("Station x (m)",
                            str(result.get("Governing x", "")).replace(" m", ""))))
                    except (ValueError, TypeError):
                        continue
                    candidates = candidates[pd.to_numeric(candidates["Station x (m)"]).sub(x).abs() < 1e-7]
                    if len(candidates) != 1:
                        continue
                    row = candidates.iloc[0].to_dict()
                    if ref.SNAPSHOT_KEY not in (source_info(row) or {}):
                        continue
                    from concrete_pmm_pro.ui.igird_station_section import at_station
                    local = at_station(state, x)
                    converted = convert_for_check(local, row, check_name=check_name)
                    qualified = ref.qualify_result(result.to_dict(), converted, check_name=check_name)
                    for key, item in qualified.items():
                        if key not in frame:
                            frame[key] = None
                        frame.at[index, key] = item
            return (frame, *value[1:]) if isinstance(value, tuple) else frame
        return wrapped
    return decorate


def sls_row(state, row, basis):
    if ref.SNAPSHOT_KEY not in (source_info(row) or {}):
        return dict(row)
    from concrete_pmm_pro.ui import analysis_page as ap
    geometry = state.get("section_geometry")
    _, bottom, _, top = ap._beam_uls_section_bounds(geometry)
    params = state.get("section_parameters") or {}
    origin = {"deck_top_y_mm": top + float(params.get("Tslab_mm", 0)),
        "target_y_mm": bottom + float(basis.centroid_y_from_bottom_mm),
        "target_local3_mm": 0}
    converted = ref.translate_row(row, origin=origin, sls=True)
    trace = converted[ref.RUNTIME_KEY]
    if trace["mode"] == "BLOCKED":
        raise ValueError(trace["error"])
    return converted


def sls_trace(row):
    result = ref.trace_columns(row)
    if not result:
        return result
    reasons = []
    if abs(float(row.get("My", 0))) > 1e-9:
        reasons.append("Top/bottom SLS checks primary M3 only; M2 corner-fiber stress remains separate.")
    if result["Reference status"] != "EXACT":
        reasons.append("Moment bounds do not establish the joint stress envelope; correspondence is required.")
    result["Reference review"] = " ".join(reasons)
    return result


def render_trace(row):
    """Format stored transport evidence; never call geometry or a solver."""
    if not row or row.get("Reference version") != ref.VERSION:
        return
    import streamlit as st
    r2, r3 = float(row["C-O local2 m"]), float(row["C-O local3 m"])
    p = float(row["Original CSI P kN"])
    v2, v3 = float(row["Original CSI V2 kN"]), float(row["Original CSI V3 kN"])
    tr2, tr3 = float(row.get("T C-O local2 m", r2)), float(row.get("T C-O local3 m", r3))
    t, m2, m3 = [float(row[f"Original CSI {f} kN-m"]) for f in ("T","M2","M3")]
    direct_t = row.get("T reference version") == ref.SOURCE_TORSION_POLICY
    torque_equation = ({"Action":"T", "Equation":"T_used = T_CSI (unchanged)",
        "Substitution":f"{t:.6g}", "Result (kN-m)":t} if direct_t else
        {"Action":"T","Equation":"T_O=T_C+r2·V3−r3·V2",
            "Substitution":f"{t:.6g}+({tr2:.6g})×{v3:.6g}−({tr3:.6g})×{v2:.6g}",
            "Result (kN-m)":t+tr2*v3-tr3*v2})
    frame = pd.DataFrame([
        torque_equation,
        {"Action":"M2","Equation":"M2_O=M2_C−r3·P",
            "Substitution":f"{m2:.6g}−({r3:.6g})×{p:.6g}",
            "Result (kN-m)":m2-r3*p},
        {"Action":"M3","Equation":"M3_O=M3_C−r2·P",
            "Substitution":f"{m3:.6g}−({r2:.6g})×{p:.6g}",
            "Result (kN-m)":m3-r2*p},
    ])
    st.markdown("**CSI force reference / Equations**")
    st.caption(f"C: y={float(row['CSI C y mm']):.3f} mm; "
        f"O: y={float(row['Resistance O y mm']):.3f} mm; "
        f"r2={r2:.6f} m, r3={r3:.6f} m · {row['Reference status']}")
    if direct_t:
        st.caption("Tu ใช้ค่าต้นทาง CSiBridge ณ จุดรายงานเดิม ไม่ย้ายไป centroid คาน I · "
            "M2/M3 ใช้จุดอ้างอิงของการตรวจดัดตามเดิม")
    if row["Reference status"] == "EXACT":
        st.dataframe(frame, hide_index=True, use_container_width=True)
    else:
        st.info("Envelope moments use interval transport; the six row extrema do not form a simultaneous action vector.")
    if row.get("Reference review"):
        st.warning(str(row["Reference review"]))


def aligned_plot_source(source, results, *, column):
    """Plot the calculated demand at its resistance origin, not raw CSI M."""
    if results is None or results.empty or "Reference version" not in results:
        return source
    output = source.copy(deep=True)
    for index, row in output.iterrows():
        if ref.SNAPSHOT_KEY not in (source_info(row) or {}):
            continue
        selected = results[results["Case"].astype(str).eq(str(row["Case Name"]))]
        stations = pd.to_numeric(selected.get("Source station x (m)",
            selected.get("Station x (m)", selected["Governing x"].astype(str).str.replace(" m", "", regex=False))), errors="coerce")
        selected = selected[stations.sub(float(row["Station x (m)"])).abs() < 1e-7]
        values = pd.to_numeric(selected.get("Demand kN-m", pd.Series(dtype=float)), errors="coerce").dropna().unique()
        output.at[index, column] = float(values[0]) if len(values) == 1 else float("nan")
    return output
