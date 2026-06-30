from __future__ import annotations

import json
from pathlib import Path

from concrete_pmm_pro.core.models import PrestressElement, Rebar
from concrete_pmm_pro.geometry import default_registry
from concrete_pmm_pro.geometry.generators import rectangle
from concrete_pmm_pro.visualization import create_section_preview


def _default_params(preset: dict) -> dict[str, float | str | bool]:
    params: dict[str, float | str | bool] = {}
    for parameter in preset.get("parameters", []):
        name = str(parameter["name"])
        if name in {"Ebeam_MPa", "Edeck_MPa"}:
            continue
        if "default" in parameter:
            params[name] = parameter["default"]
    return params


def _figure_text_blob(fig) -> str:
    return json.dumps(fig.to_plotly_json(), default=str).lower()


def test_shared_preview_canvas_theme_has_no_undefined_legend_title_for_all_presets() -> None:
    presets_path = Path(__file__).resolve().parents[1] / "data" / "section_presets.json"
    presets = json.loads(presets_path.read_text(encoding="utf-8"))["presets"]

    checked = 0
    for preset in presets:
        params = _default_params(preset)
        generator_params = {name: value for name, value in params.items() if isinstance(value, (int, float, str, bool))}
        geometry = default_registry.geometry(preset["generator"])(**generator_params, name=preset["display_name"])
        dimensions = default_registry.dimensions(preset["dimensions_generator"])(**generator_params)
        fig = create_section_preview(geometry, dimensions)

        assert fig.layout.title.text == ""
        assert fig.layout.legend.title.text == ""
        assert "undefined" not in _figure_text_blob(fig)
        checked += 1

    assert checked >= 10


def test_shared_preview_canvas_theme_applies_to_rebar_and_prestress_previews() -> None:
    geometry = rectangle(width_mm=500, height_mm=600)
    rebar = Rebar(label="B1", x_mm=0, y_mm=-220, diameter_mm=20, material_name="SD40")
    prestress = PrestressElement(
        label="P1",
        x_mm=0,
        y_mm=-180,
        steel_type="strand",
        diameter_mm=12.7,
        area_mm2=98.7,
        fpu_mpa=1860,
        ep_mpa=195000,
        pe_eff_n=120000,
    )

    for fig in [
        create_section_preview(geometry, rebars=[rebar]),
        create_section_preview(geometry, prestress_elements=[prestress]),
        create_section_preview(geometry, rebars=[rebar], prestress_elements=[prestress]),
    ]:
        assert fig.layout.title.text == ""
        assert fig.layout.legend.title.text == ""
        assert fig.layout.legend.font.size == 11
        assert fig.layout.legend.borderwidth == 1
        assert fig.layout.xaxis.gridcolor == "#e2e8f0"
        assert fig.layout.yaxis.gridcolor == "#e2e8f0"
        assert "undefined" not in _figure_text_blob(fig)
