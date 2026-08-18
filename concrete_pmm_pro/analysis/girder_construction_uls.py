"""Precast composite girder Construction-ULS demand foundation.

This module generates the *demand* for the pre-composite construction stage of
an ordinary unshored precast bridge girder.  It deliberately does not select or
claim AASHTO load factors.  The engineer enters project-applicable factors and
confirms their basis before the generated demand is eligible for PASS/FAIL use.

The resisting section for this stage is the precast girder only.  Wet deck,
formwork, and construction loads are loads on that non-composite member; the
CIP deck is not credited to flexural strength here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from concrete_pmm_pro.serviceability.girder_sls_load_components import (
    BeamGirderSystemSettings,
    default_sls_station_grid,
    girder_self_weight_kN_m,
    simple_span_udl_moment_kNm,
    simple_span_udl_shear_kN,
    wet_topping_load_kN_m,
)


BEAM_GIRDER_CONSTRUCTION_ULS_SETTINGS_KEY = "beam_girder_construction_uls_settings"
CONSTRUCTION_ULS_CASE_NAME = "AUTO-CONSTRUCTION-ULS"


@dataclass(frozen=True)
class BeamGirderConstructionULSSettings:
    """Engineer-owned settings for the generated construction-stage ULS demand.

    Factors default to 1.0 on purpose.  They are *not* asserted to be AASHTO
    factors.  ``factors_confirmed`` is therefore a required engineering gate
    before this route can issue an acceptance status.
    """

    construction_support: str = "Unshored"
    include_girder_self_weight: bool = True
    include_wet_deck: bool = True
    include_formwork: bool = False
    formwork_line_load_kN_m: float = 0.0
    include_construction_live_load: bool = False
    construction_live_load_kN_m: float = 0.0
    gamma_girder_self_weight: float = 1.0
    gamma_wet_deck: float = 1.0
    gamma_formwork: float = 1.0
    gamma_construction_live: float = 1.0
    factor_basis: str = "Project-defined construction ULS factors"
    factors_confirmed: bool = False

    @property
    def is_unshored(self) -> bool:
        return str(self.construction_support).strip().casefold() == "unshored"

    def as_metadata(self) -> dict[str, Any]:
        return {
            "construction_support": self.construction_support,
            "include_girder_self_weight": self.include_girder_self_weight,
            "include_wet_deck": self.include_wet_deck,
            "include_formwork": self.include_formwork,
            "formwork_line_load_kN_m": self.formwork_line_load_kN_m,
            "include_construction_live_load": self.include_construction_live_load,
            "construction_live_load_kN_m": self.construction_live_load_kN_m,
            "gamma_girder_self_weight": self.gamma_girder_self_weight,
            "gamma_wet_deck": self.gamma_wet_deck,
            "gamma_formwork": self.gamma_formwork,
            "gamma_construction_live": self.gamma_construction_live,
            "factor_basis": self.factor_basis,
            "factors_confirmed": self.factors_confirmed,
        }


@dataclass(frozen=True)
class ConstructionULSComponent:
    label: str
    unfactored_kN_m: float
    factor: float

    @property
    def factored_kN_m(self) -> float:
        return self.unfactored_kN_m * self.factor

    def as_row(self) -> dict[str, Any]:
        return {
            "Component": self.label,
            "Unfactored w (kN/m)": self.unfactored_kN_m,
            "ULS factor": self.factor,
            "Factored w (kN/m)": self.factored_kN_m,
        }


@dataclass(frozen=True)
class ConstructionULSDemand:
    components: tuple[ConstructionULSComponent, ...]
    settings: BeamGirderConstructionULSSettings
    span_length_m: float
    warnings: tuple[str, ...] = ()

    @property
    def unfactored_total_kN_m(self) -> float:
        return sum(item.unfactored_kN_m for item in self.components)

    @property
    def factored_total_kN_m(self) -> float:
        return sum(item.factored_kN_m for item in self.components)

    @property
    def factors_ready(self) -> bool:
        return bool(self.settings.factors_confirmed)

    @property
    def structural_route_ready(self) -> bool:
        return self.settings.is_unshored

    @property
    def acceptance_ready(self) -> bool:
        return self.structural_route_ready and self.factors_ready and self.factored_total_kN_m > 0.0

    @property
    def status(self) -> str:
        if not self.structural_route_ready:
            return "BLOCKED"
        if not self.factors_ready:
            return "REVIEW"
        if self.factored_total_kN_m <= 0.0:
            return "BLOCKED"
        return "READY"

    def component_rows(self) -> list[dict[str, Any]]:
        rows = [component.as_row() for component in self.components]
        rows.append(
            {
                "Component": "TOTAL",
                "Unfactored w (kN/m)": self.unfactored_total_kN_m,
                "ULS factor": None,
                "Factored w (kN/m)": self.factored_total_kN_m,
            }
        )
        return rows


def _nonnegative(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(number, 0.0)


def _positive_factor(value: Any, default: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0.0 else default


def construction_uls_settings_from_mapping(mapping: Mapping[str, Any] | None) -> BeamGirderConstructionULSSettings:
    data = dict(mapping or {})
    default = BeamGirderConstructionULSSettings()
    support = str(data.get("construction_support", default.construction_support) or default.construction_support).strip()
    if support not in {"Unshored", "Shored"}:
        support = default.construction_support
    return BeamGirderConstructionULSSettings(
        construction_support=support,
        include_girder_self_weight=bool(data.get("include_girder_self_weight", default.include_girder_self_weight)),
        include_wet_deck=bool(data.get("include_wet_deck", default.include_wet_deck)),
        include_formwork=bool(data.get("include_formwork", default.include_formwork)),
        formwork_line_load_kN_m=_nonnegative(data.get("formwork_line_load_kN_m"), default.formwork_line_load_kN_m),
        include_construction_live_load=bool(data.get("include_construction_live_load", default.include_construction_live_load)),
        construction_live_load_kN_m=_nonnegative(data.get("construction_live_load_kN_m"), default.construction_live_load_kN_m),
        gamma_girder_self_weight=_positive_factor(data.get("gamma_girder_self_weight"), default.gamma_girder_self_weight),
        gamma_wet_deck=_positive_factor(data.get("gamma_wet_deck"), default.gamma_wet_deck),
        gamma_formwork=_positive_factor(data.get("gamma_formwork"), default.gamma_formwork),
        gamma_construction_live=_positive_factor(data.get("gamma_construction_live"), default.gamma_construction_live),
        factor_basis=str(data.get("factor_basis", default.factor_basis) or default.factor_basis).strip(),
        factors_confirmed=bool(data.get("factors_confirmed", default.factors_confirmed)),
    )


def build_construction_uls_demand(
    *,
    system: BeamGirderSystemSettings,
    settings: BeamGirderConstructionULSSettings,
    precast_area_mm2: float,
    deck_thickness_mm: float,
) -> ConstructionULSDemand:
    """Build component line loads for the pre-composite construction stage."""

    components: list[ConstructionULSComponent] = []
    warnings: list[str] = []

    if settings.include_girder_self_weight:
        self_weight = girder_self_weight_kN_m(precast_area_mm2, system.concrete_unit_weight_kN_m3)
        if self_weight > 0.0:
            components.append(
                ConstructionULSComponent(
                    "Precast girder self-weight",
                    self_weight,
                    settings.gamma_girder_self_weight,
                )
            )
        else:
            warnings.append("Precast girder self-weight could not be generated because gross area is not positive.")

    if settings.include_wet_deck:
        wet_deck = wet_topping_load_kN_m(
            deck_thickness_mm,
            system.effective_tributary_width_m,
            system.concrete_unit_weight_kN_m3,
        )
        if wet_deck > 0.0:
            components.append(ConstructionULSComponent("Wet CIP deck", wet_deck, settings.gamma_wet_deck))
        else:
            warnings.append("Wet CIP deck load could not be generated because deck thickness/tributary width is not positive.")

    if settings.include_formwork and settings.formwork_line_load_kN_m > 0.0:
        components.append(
            ConstructionULSComponent(
                "Formwork / SIP forms",
                settings.formwork_line_load_kN_m,
                settings.gamma_formwork,
            )
        )

    if settings.include_construction_live_load and settings.construction_live_load_kN_m > 0.0:
        components.append(
            ConstructionULSComponent(
                "Construction live load",
                settings.construction_live_load_kN_m,
                settings.gamma_construction_live,
            )
        )

    if not settings.is_unshored:
        warnings.append(
            "Shored construction is selected. Automatic non-composite girder demand is blocked because shore reactions/load sharing require a project construction model."
        )
    if not settings.factors_confirmed:
        warnings.append(
            "Construction ULS factors are not engineer-confirmed. Generated factored actions remain REVIEW and must not be used for PASS/FAIL."
        )

    return ConstructionULSDemand(
        components=tuple(components),
        settings=settings,
        span_length_m=float(system.span_length_m),
        warnings=tuple(warnings),
    )


def construction_uls_station_rows(
    demand: ConstructionULSDemand,
    *,
    extra_stations_m: Iterable[float] | None = None,
    divisions: int = 40,
) -> list[dict[str, Any]]:
    """Return station ULS resultants for simple-span unshored construction.

    The rows follow the Beam/Girder ULS table convention: positive Mux is
    sagging and Vuy follows the existing simple-span sign convention.
    """

    if not demand.structural_route_ready or demand.factored_total_kN_m <= 0.0:
        return []
    stations = default_sls_station_grid(demand.span_length_m, extra_stations_m=extra_stations_m, divisions=divisions)
    w = demand.factored_total_kN_m
    rows: list[dict[str, Any]] = []
    for x_m in stations:
        rows.append(
            {
                "Active": True,
                "Station x (m)": float(x_m),
                "Case Name": CONSTRUCTION_ULS_CASE_NAME,
                "Mux": simple_span_udl_moment_kNm(w, x_m, demand.span_length_m),
                "Vuy": simple_span_udl_shear_kN(w, x_m, demand.span_length_m),
                "Tu": 0.0,
                "Muy": 0.0,
                "Vux": 0.0,
                "Nu": 0.0,
                "Note": "Auto Construction ULS · non-composite precast girder · simple-span UDL",
            }
        )
    return rows
