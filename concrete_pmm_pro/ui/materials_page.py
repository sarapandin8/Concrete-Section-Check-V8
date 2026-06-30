"""Materials tab UI."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from concrete_pmm_pro.core.concrete_materials import (
    CONCRETE_EC_METHOD_OPTIONS,
    c45_precast_material,
    ensure_concrete_material_library,
)
from concrete_pmm_pro.core.models import ConcreteMaterial, PrestressSteelMaterial, RebarMaterial
from concrete_pmm_pro.ui.commercial import render_page_header, render_section_bar

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRESTRESS_DB_PATH = REPO_ROOT / "data" / "prestress_steel_database.csv"
STEEL_TYPE_OPTIONS = ["wire", "strand", "prestressing_bar", "tendon_group", "custom"]

_MATERIALS_DASHBOARD_CSS = """
<style>
.cpmm-material-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 0.58rem;
  margin: 0.58rem 0 0.55rem 0;
}
.cpmm-material-card {
  border: 1px solid #d7e2ee;
  border-left: 4px solid #1d6fe7;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
  padding: 0.62rem 0.70rem;
  min-height: 72px;
  box-shadow: 0 4px 12px rgba(7, 26, 51, 0.045);
}
.cpmm-material-card.ready {
  border-left-color: #22a447;
  background: linear-gradient(180deg, #ffffff 0%, #f5fff7 100%);
}
.cpmm-material-card.warning {
  border-left-color: #f59e0b;
  background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%);
}
.cpmm-material-card.neutral {
  border-left-color: #98a2b3;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
}
.cpmm-material-label {
  color: #526f8d;
  font-size: 0.62rem;
  font-weight: 950;
  letter-spacing: 0.065em;
  text-transform: uppercase;
  margin-bottom: 0.14rem;
}
.cpmm-material-value {
  color: #0b3a66;
  font-size: 0.98rem;
  font-weight: 920;
  line-height: 1.14;
  overflow-wrap: anywhere;
}
.cpmm-material-detail {
  color: #667085;
  font-size: 0.68rem;
  line-height: 1.28;
  margin-top: 0.14rem;
}
.cpmm-material-guidance {
  border: 1px solid #cfe0ff;
  border-left: 4px solid #1d6fe7;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
  padding: 0.58rem 0.70rem;
  margin: 0.38rem 0 0.64rem 0;
  color: #0b3a66;
  font-size: 0.76rem;
  line-height: 1.36;
}
.cpmm-material-command {
  border: 1px solid #cfe0ff;
  border-left: 5px solid #1d6fe7;
  border-radius: 13px;
  background: linear-gradient(180deg, #ffffff 0%, #f6faff 100%);
  padding: 0.66rem 0.75rem;
  min-height: 70px;
  box-shadow: 0 4px 12px rgba(7, 26, 51, 0.045);
}
.cpmm-material-command-kicker {
  color: #526f8d;
  font-size: 0.62rem;
  font-weight: 950;
  letter-spacing: 0.065em;
  text-transform: uppercase;
  margin-bottom: 0.12rem;
}
.cpmm-material-command-title {
  color: #071a33;
  font-size: 0.98rem;
  font-weight: 920;
  line-height: 1.16;
}
.cpmm-material-command-detail {
  color: #667085;
  font-size: 0.70rem;
  line-height: 1.30;
  margin-top: 0.16rem;
}
.cpmm-material-section-note {
  color: #667085;
  font-size: 0.74rem;
  line-height: 1.34;
  margin: 0.25rem 0 0.45rem 0;
}
</style>
"""


def _render_material_cards(cards: list[dict[str, object]]) -> None:
    html_cards: list[str] = []
    for card in cards:
        status = escape(str(card.get("status", "info") or "info"))
        title = escape(str(card.get("title", "")))
        value = escape(str(card.get("value", "")))
        detail = escape(str(card.get("detail", "")))
        html_cards.append(
            f'<div class="cpmm-material-card {status}">'
            f'<div class="cpmm-material-label">{title}</div>'
            f'<div class="cpmm-material-value">{value}</div>'
            f'<div class="cpmm-material-detail">{detail}</div>'
            '</div>'
        )
    st.markdown(_MATERIALS_DASHBOARD_CSS + '<div class="cpmm-material-grid">' + ''.join(html_cards) + '</div>', unsafe_allow_html=True)


def _render_material_guidance(message: str) -> None:
    st.markdown(
        _MATERIALS_DASHBOARD_CSS
        + f'<div class="cpmm-material-guidance">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _render_prestress_product_command(material: PrestressSteelMaterial) -> None:
    area = f"{material.area_mm2:.1f} mm²" if material.area_mm2 is not None else "area not listed"
    fpu = f"fpu {material.fpu_MPa:.0f} MPa"
    fpy = f"fpy {material.fpy_MPa:.0f} MPa" if material.fpy_MPa is not None else "fpy not listed"
    detail = f"{material.steel_type} · {area} · {fpy} · {fpu} · Ep {material.Ep_MPa:.0f} MPa"
    st.markdown(
        _MATERIALS_DASHBOARD_CSS
        + '<div class="cpmm-material-command">'
        + '<div class="cpmm-material-command-kicker">Selected prestress product</div>'
        + f'<div class="cpmm-material-command-title">{escape(material.name)}</div>'
        + f'<div class="cpmm-material-command-detail">{escape(detail)}</div>'
        + '</div>',
        unsafe_allow_html=True,
    )


def _render_material_workspace_dashboard() -> None:
    concrete_materials: list[ConcreteMaterial] = st.session_state.get("concrete_materials", [])
    rebar_materials: list[RebarMaterial] = st.session_state.get("rebar_materials", [])
    prestress_materials: list[PrestressSteelMaterial] = st.session_state.get("prestress_materials", [])
    section_concrete = str(st.session_state.get("active_concrete_material_name") or "controlled in Section Builder")
    topping_concrete = str(st.session_state.get("deck_topping_material_name") or "controlled in Section Builder")
    _render_material_cards(
        [
            {
                "title": "Concrete library",
                "value": f"{len(concrete_materials):,} material(s)",
                "detail": f"section: {section_concrete}",
                "status": "ready" if concrete_materials else "warning",
            },
            {
                "title": "Rebar library",
                "value": f"{len(rebar_materials):,} material(s)",
                "detail": "bar size controls standard fy in Rebar",
                "status": "ready" if rebar_materials else "warning",
            },
            {
                "title": "Prestress products",
                "value": f"{len(prestress_materials):,} product(s)",
                "detail": "Product controls Area, fpy, fpu, and Ep",
                "status": "ready" if prestress_materials else "warning",
            },
            {
                "title": "Deck / topping",
                "value": topping_concrete,
                "detail": "assigned by section/preset context",
                "status": "info",
            },
        ]
    )



def load_prestress_steel_database(path: Path | str = DEFAULT_PRESTRESS_DB_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def default_rebar_materials() -> list[RebarMaterial]:
    return [
        RebarMaterial(name="SD40", fy_MPa=390.0, Es_MPa=200000.0),
        RebarMaterial(name="SD50", fy_MPa=490.0, Es_MPa=200000.0),
    ]


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _optional_float(value: Any) -> float | None:
    if _is_blank(value):
        return None
    parsed = float(value)
    return parsed if parsed > 0 else None


def _infer_fc_from_material_id(name: str) -> float | None:
    """Infer f'c from simple grade IDs such as C40 or C45.5."""
    match = re.fullmatch(r"C\s*(\d+(?:\.\d+)?)", name.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    fc = float(match.group(1))
    return fc if fc > 0 else None


def _default_concrete_row_value(column: str, name: str) -> float | str | None:
    if column == "fc_MPa":
        return _infer_fc_from_material_id(name)
    if column == "ecu":
        return 0.003
    if column == "density_kg_m3":
        return 2400.0
    if column == "Ec_method":
        return "ACI auto"
    return None


def _bool_from_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if _is_blank(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def prestress_material_from_database_row(row: pd.Series) -> PrestressSteelMaterial:
    return PrestressSteelMaterial(
        name=str(row["name"]),
        steel_type=str(row["type"]),
        diameter_mm=None if pd.isna(row["diameter_mm"]) else float(row["diameter_mm"]),
        area_mm2=None if pd.isna(row["area_mm2"]) else float(row["area_mm2"]),
        grade=None if pd.isna(row["grade"]) else str(row["grade"]),
        fpy_MPa=None if pd.isna(row["fpy_MPa"]) else float(row["fpy_MPa"]),
        fpu_MPa=float(row["fpu_MPa"]),
        Ep_MPa=float(row["Ep_MPa"]),
        relaxation_class=None,
        source=None if pd.isna(row["source"]) else str(row["source"]),
        area_source=None if pd.isna(row["area_source"]) else str(row["area_source"]),
        is_catalog_verified=_bool_from_value(row["is_catalog_verified"]),
    )


def _upsert_by_name(items: list[PrestressSteelMaterial], material: PrestressSteelMaterial) -> list[PrestressSteelMaterial]:
    return [item for item in items if item.name != material.name] + [material]


def _default_prestress_materials() -> list[PrestressSteelMaterial]:
    db = load_prestress_steel_database()
    names = set(db["name"])
    defaults = ["15.2mm strand"]
    if "PS Bar 32 - 1080/1230" in names:
        defaults.append("PS Bar 32 - 1080/1230")
    return [prestress_material_from_database_row(db.loc[db["name"] == name].iloc[0]) for name in defaults if name in names]


def _ensure_material_defaults() -> None:
    concrete_library = ensure_concrete_material_library(
        concrete_material=st.session_state.get("concrete_material", c45_precast_material()),
        concrete_materials=st.session_state.get("concrete_materials", []),
        active_concrete_material_name=st.session_state.get("active_concrete_material_name"),
        deck_topping_material_name=st.session_state.get("deck_topping_material_name"),
        preserve_existing_primary=not bool(st.session_state.get("concrete_materials", [])),
    )
    st.session_state["concrete_materials"] = concrete_library.materials
    st.session_state["active_concrete_material_name"] = concrete_library.active_concrete_material_name
    st.session_state["primary_concrete_material_name"] = concrete_library.active_concrete_material_name
    st.session_state["deck_topping_material_name"] = concrete_library.deck_topping_material_name
    st.session_state["concrete_material"] = concrete_library.active_material
    if "rebar_materials" not in st.session_state or not st.session_state["rebar_materials"]:
        st.session_state["rebar_materials"] = default_rebar_materials()
    if "prestress_materials" not in st.session_state or not st.session_state["prestress_materials"]:
        st.session_state["prestress_materials"] = _default_prestress_materials()
    st.session_state.setdefault("active_rebar_material_name", st.session_state["rebar_materials"][0].name)
    st.session_state.setdefault("active_prestress_material_name", st.session_state["prestress_materials"][0].name)


def _concrete_materials_dataframe(materials: list[ConcreteMaterial]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for material in materials:
        row = material.model_dump()
        row["Effective Ec_MPa"] = material.effective_Ec_MPa
        rows.append(row)
    return pd.DataFrame(rows)


def _positive_float_from_cell(value: Any, *, row_number: int, label: str, errors: list[str]) -> tuple[float | None, bool]:
    if _is_blank(value):
        return None, True
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        errors.append(f"Row {row_number}: {label} must be a positive number.")
        return None, False
    if parsed <= 0:
        errors.append(f"Row {row_number}: {label} must be greater than 0.")
        return None, False
    return parsed, True


def _parse_concrete_materials(df: pd.DataFrame) -> tuple[list[ConcreteMaterial], list[str], list[str]]:
    materials: list[ConcreteMaterial] = []
    warnings: list[str] = []
    errors: list[str] = []
    seen_names: set[str] = set()
    required_columns = ["name", "fc_MPa", "ecu", "density_kg_m3", "Ec_method", "Ec_MPa", "note"]
    for index, row in df.iterrows():
        row_number = int(index) + 1
        if all(_is_blank(row.get(column)) for column in required_columns):
            continue

        name = str(row.get("name") or "").strip()
        if not name:
            # A blank dynamic row is a draft; do not block the page with a hard error.
            if any(not _is_blank(row.get(column)) for column in required_columns if column != "name"):
                warnings.append(f"Row {row_number}: draft material ignored until Material ID is entered.")
            continue
        if name in seen_names:
            warnings.append(f"Row {row_number}: duplicate Material ID '{name}' was ignored; material IDs must be unique.")
            continue
        seen_names.add(name)

        fc_value, fc_ok = _positive_float_from_cell(row.get("fc_MPa"), row_number=row_number, label="f'c", errors=errors)
        ecu_value, ecu_ok = _positive_float_from_cell(row.get("ecu"), row_number=row_number, label="ecu", errors=errors)
        density_value, density_ok = _positive_float_from_cell(
            row.get("density_kg_m3"), row_number=row_number, label="density_kg_m3", errors=errors
        )
        beta1_value, beta1_ok = _positive_float_from_cell(row.get("beta1"), row_number=row_number, label="beta1", errors=errors)
        ec_override, ec_ok = _positive_float_from_cell(row.get("Ec_MPa"), row_number=row_number, label="Manual Ec_MPa", errors=errors)
        if not all((fc_ok, ecu_ok, density_ok, beta1_ok, ec_ok)):
            continue

        fc_value = fc_value or _default_concrete_row_value("fc_MPa", name)
        ecu_value = ecu_value or _default_concrete_row_value("ecu", name)
        density_value = density_value or _default_concrete_row_value("density_kg_m3", name)
        ec_method_raw = row.get("Ec_method")
        ec_method = str(ec_method_raw or _default_concrete_row_value("Ec_method", name) or "ACI auto").strip()
        if ec_method not in CONCRETE_EC_METHOD_OPTIONS:
            ec_method = "ACI auto"

        if fc_value is None:
            warnings.append(
                f"Row {row_number}: '{name}' is incomplete and was not saved. "
                "Enter f'c, or use a grade-style ID such as C40 to auto-fill defaults."
            )
            continue
        if ecu_value is None or density_value is None:
            warnings.append(
                f"Row {row_number}: '{name}' is incomplete and was not saved. "
                "ecu and density must be positive values."
            )
            continue
        if ec_method == "Manual" and ec_override is None:
            warnings.append(f"Row {row_number}: '{name}' uses Manual Ec but no positive Manual Ec_MPa was entered.")
            continue

        try:
            materials.append(
                ConcreteMaterial(
                    name=name,
                    fc_MPa=float(fc_value),
                    ecu=float(ecu_value),
                    density_kg_m3=float(density_value),
                    beta1=beta1_value,
                    Ec_method=ec_method,
                    Ec_MPa=ec_override,
                    note=None if _is_blank(row.get("note")) else str(row.get("note")),
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            errors.append(f"Row {row_number}: invalid concrete material ({exc}).")
    return materials, warnings, errors


def _render_concrete_section() -> None:
    render_section_bar(
        "Concrete Material Library",
        "Library-only concrete definitions. Section-specific assignment remains in Section Builder.",
        mark="C",
    )
    _render_material_guidance(
        "Concrete materials are defined here as a library only. Assign the section concrete in "
        "Sections → Section Builder so each section/preset can use its own main, deck/topping, web, "
        "or cast-in-place slab concrete without changing the project library."
    )

    edited_df = st.data_editor(
        _concrete_materials_dataframe(st.session_state["concrete_materials"]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Material ID"),
            "fc_MPa": st.column_config.NumberColumn("f'c, MPa", min_value=0.1, step=1.0),
            "density_kg_m3": st.column_config.NumberColumn("Density, kg/m3", min_value=1.0, step=10.0),
            "ecu": st.column_config.NumberColumn("ecu", min_value=0.0001, step=0.0001, format="%.4f"),
            "beta1": st.column_config.NumberColumn("beta1 manual", min_value=0.01, max_value=1.0, step=0.01),
            "Ec_method": st.column_config.SelectboxColumn("Ec method", options=CONCRETE_EC_METHOD_OPTIONS),
            "Ec_MPa": st.column_config.NumberColumn("Manual Ec_MPa", min_value=0.1, step=100.0),
            "Effective Ec_MPa": st.column_config.NumberColumn("Effective Ec_MPa", disabled=True, format="%.0f"),
            "note": st.column_config.TextColumn("Use / description / note"),
        },
        key="concrete_materials_editor",
    )
    materials, warnings, errors = _parse_concrete_materials(edited_df)
    for warning in warnings:
        st.warning(warning)
    if errors:
        for error in errors:
            st.error(error)
        return
    if not materials:
        st.error("At least one concrete material is required.")
        return

    st.session_state["concrete_materials"] = materials
    material_names = [material.name for material in materials]
    material_map = {material.name: material for material in materials}

    active_name = st.session_state.get("active_concrete_material_name")
    if active_name not in material_map:
        active_name = material_names[0]
        st.session_state["active_concrete_material_name"] = active_name
        st.session_state["primary_concrete_material_name"] = active_name
        st.session_state["concrete_material"] = material_map[active_name]

    deck_name = st.session_state.get("deck_topping_material_name")
    if deck_name not in material_map:
        deck_name = material_names[min(1, len(material_names) - 1)]
        st.session_state["deck_topping_material_name"] = deck_name

    st.caption(
        "Assignment controls are intentionally hidden here. Current section concrete is selected in "
        "Section Builder; rebar fy is resolved from bar size in Rebar; prestress fpu/fpy/Ep is resolved from Product in Prestress."
    )
    st.success("Concrete material library is valid.")


def _rebar_materials_dataframe(materials: list[RebarMaterial]) -> pd.DataFrame:
    return pd.DataFrame([material.model_dump() for material in materials])


def _parse_rebar_materials(df: pd.DataFrame) -> tuple[list[RebarMaterial], list[str]]:
    materials: list[RebarMaterial] = []
    errors: list[str] = []
    for index, row in df.iterrows():
        row_number = int(index) + 1
        if all(_is_blank(row.get(column)) for column in ["name", "fy_MPa", "Es_MPa", "note"]):
            continue
        try:
            materials.append(
                RebarMaterial(
                    name=str(row.get("name")).strip(),
                    fy_MPa=float(row.get("fy_MPa")),
                    Es_MPa=float(row.get("Es_MPa")),
                    note=None if _is_blank(row.get("note")) else str(row.get("note")),
                )
            )
        except (TypeError, ValueError, ValidationError) as exc:
            errors.append(f"Row {row_number}: invalid rebar material ({exc}).")
    return materials, errors


def _render_rebar_section() -> None:
    render_section_bar(
        "Rebar Material Library",
        "Standard bar size remains the source of truth for DB rows; custom material rows stay available for project-specific cases.",
        mark="R",
    )
    _render_material_guidance(
        "Rebar materials are kept here as a library. Standard DB bar rows use the selected Bar Size as the source of truth: "
        "DB10–DB28 → SD40 / fy 390 MPa and DB32 → SD50 / fy 490 MPa. Use Custom bar size only when a project-specific material is required."
    )
    edited_df = st.data_editor(
        _rebar_materials_dataframe(st.session_state["rebar_materials"]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Material name"),
            "fy_MPa": st.column_config.NumberColumn("fy, MPa", min_value=0.1),
            "Es_MPa": st.column_config.NumberColumn("Es, MPa", min_value=0.1),
            "note": st.column_config.TextColumn("Note"),
        },
        key="rebar_materials_editor",
    )
    materials, errors = _parse_rebar_materials(edited_df)
    if errors:
        for error in errors:
            st.error(error)
    elif materials:
        st.session_state["rebar_materials"] = materials
        active_names = [material.name for material in materials]
        active_name = st.session_state.get("active_rebar_material_name")
        if active_name not in active_names:
            st.session_state["active_rebar_material_name"] = active_names[0]
        st.caption("No active rebar material is assigned on this page; standard bar size controls fy in the Rebar workspace.")
        st.success("Rebar material library is valid.")


def _render_prestress_section() -> None:
    render_section_bar(
        "Prestressing Steel Material Library",
        "Catalog products provide Area, fpy, fpu, and Ep; prestress force and losses remain in the Prestress workspace.",
        mark="P",
    )
    _render_material_guidance(
        "Prestressing steel products are kept here as a library. In the Prestress workspace, Product is the source of truth "
        "for Area, fpy, fpu, and Ep; effective prestress force/loss input remains on the Prestress page."
    )

    db = load_prestress_steel_database()
    mode = st.radio("Prestressing steel material input", ["Select from prestress_steel_database.csv", "Custom material"], horizontal=True)

    if mode == "Select from prestress_steel_database.csv":
        product = st.selectbox("Database product", [str(name) for name in db["name"].tolist()])
        row = db.loc[db["name"] == product].iloc[0]
        selected_material = prestress_material_from_database_row(row)
        command_cols = st.columns([3.2, 1.0])
        with command_cols[0]:
            _render_prestress_product_command(selected_material)
        with command_cols[1]:
            st.caption("Project library action")
            if st.button("Add selected product", use_container_width=True, type="primary", key="ui_keys1_materials_page_button_359"):
                st.session_state["prestress_materials"] = _upsert_by_name(st.session_state["prestress_materials"], selected_material)
                st.session_state["active_prestress_material_name"] = selected_material.name
                st.success(f"Added {selected_material.name}.")
        with st.expander("Selected product engineering properties", expanded=False):
            st.dataframe(pd.DataFrame([selected_material.model_dump()]), use_container_width=True, hide_index=True)

    else:
        cols = st.columns(3)
        with cols[0]:
            name = st.text_input("Material name", value="Custom PT Bar")
            steel_type = st.selectbox("Steel type", STEEL_TYPE_OPTIONS, index=STEEL_TYPE_OPTIONS.index("prestressing_bar"))
            diameter_mm = _optional_float(st.number_input("Diameter, mm", min_value=0.0, value=32.0, step=1.0))
        with cols[1]:
            area_mm2 = _optional_float(st.number_input("Area, mm2", min_value=0.0, value=804.2, step=1.0))
            grade = st.text_input("Grade", value="1080/1230")
            fpy_MPa = _optional_float(st.number_input("fpy, MPa", min_value=0.0, value=1080.0, step=10.0))
        with cols[2]:
            fpu_MPa = st.number_input("fpu, MPa", min_value=0.1, value=1230.0, step=10.0)
            Ep_MPa = st.number_input("Ep, MPa", min_value=0.1, value=200000.0, step=1000.0)
            relaxation_class = st.text_input("Relaxation class", value="")

        source = st.text_input("Source", value="project_custom")
        area_source = st.text_input("Area source", value="manual")
        is_catalog_verified = st.checkbox("Catalog verified", value=False)
        note = st.text_area("Prestress material note", value="")

        if st.button("Add / Update Custom Prestress Material", use_container_width=True, type="primary", key="ui_keys1_materials_page_button_384"):
            try:
                material = PrestressSteelMaterial(
                    name=name,
                    steel_type=steel_type,
                    diameter_mm=diameter_mm,
                    area_mm2=area_mm2,
                    grade=grade or None,
                    fpy_MPa=fpy_MPa,
                    fpu_MPa=fpu_MPa,
                    Ep_MPa=Ep_MPa,
                    relaxation_class=relaxation_class or None,
                    source=source or None,
                    area_source=area_source or None,
                    is_catalog_verified=is_catalog_verified,
                    note=note or None,
                )
                st.session_state["prestress_materials"] = _upsert_by_name(st.session_state["prestress_materials"], material)
                st.session_state["active_prestress_material_name"] = material.name
                st.success(f"Added {material.name}.")
            except ValidationError as exc:
                st.error(f"Prestressing steel material error: {exc.errors()[0]['msg']}")

    materials: list[PrestressSteelMaterial] = st.session_state["prestress_materials"]
    active_names = [material.name for material in materials]
    active_name = st.session_state.get("active_prestress_material_name")
    if active_names and active_name not in active_names:
        st.session_state["active_prestress_material_name"] = active_names[0]
    st.caption("No active prestress material is assigned on this page; Product controls fpu/fpy/Ep in the Prestress workspace.")


def _render_summary() -> None:
    render_section_bar(
        "Material Library Summary",
        "Compact project material inventory. Section assignment remains controlled outside this library page.",
        mark="S",
    )
    concrete_materials: list[ConcreteMaterial] = st.session_state.get("concrete_materials", [])
    _render_material_cards(
        [
            {
                "title": "Concrete library",
                "value": f"{len(concrete_materials):,} material(s)",
                "detail": "fc, Ec, density, beta1 basis",
                "status": "ready" if concrete_materials else "warning",
            },
            {
                "title": "Rebar library",
                "value": f"{len(st.session_state.get('rebar_materials', [])):,} material(s)",
                "detail": "SD40 / SD50 project defaults",
                "status": "ready" if st.session_state.get("rebar_materials", []) else "warning",
            },
            {
                "title": "Prestress library",
                "value": f"{len(st.session_state.get('prestress_materials', [])):,} product(s)",
                "detail": "catalog + project products",
                "status": "ready" if st.session_state.get("prestress_materials", []) else "warning",
            },
        ]
    )
    st.caption("Current section material assignment is controlled outside this library page.")

    with st.expander("Rebar materials — library audit", expanded=False):
        st.dataframe(_rebar_materials_dataframe(st.session_state["rebar_materials"]), use_container_width=True, hide_index=True)

    with st.expander("Prestressing steel materials — library audit", expanded=False):
        prestress_rows = []
        for material in st.session_state["prestress_materials"]:
            row = material.model_dump()
            row["PT Bar / Prestressing Bar"] = material.steel_type == "prestressing_bar"
            prestress_rows.append(row)
        st.dataframe(pd.DataFrame(prestress_rows), use_container_width=True, hide_index=True)


def render_materials_page() -> None:
    render_page_header(
        "Materials",
        "Manage project material libraries for concrete, reinforcement, and prestressing steel without changing section-specific assignments.",
        icon="MA",
        badge="Library workspace",
    )
    _ensure_material_defaults()
    _render_material_workspace_dashboard()
    _render_concrete_section()
    st.divider()
    _render_rebar_section()
    st.divider()
    _render_prestress_section()
    st.divider()
    _render_summary()
