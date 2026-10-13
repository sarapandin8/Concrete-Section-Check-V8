"""Simple end dimensions with optional source-axis and engineering review inputs."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import igird_end_sections as ends
from concrete_pmm_pro.visualization import create_section_preview

PREFIX = "igird_end18_"  # Keep accepted widget state and saved dimensions compatible.


def _initial_coordinate_mode(raw, span):
    """Infer only unchanged full-span legacy coordinates; retain custom/invalid ones."""
    mode = raw.get("coordinate_mode")
    if mode in ("span", "custom"):
        return mode
    try:
        left = float(raw.get("left_end_x_m", 0.0))
        right = float(raw.get("right_end_x_m", span))
        return "span" if left == 0.0 and right == span else "custom"
    except (TypeError, ValueError):
        return "custom"


def _use_loads_span(span):
    # Widget callbacks run before the next render, including the coordinate widgets.
    st.session_state[PREFIX + "use_loads_span"] = True
    st.session_state[PREFIX + "left_end_x_m"] = 0.0
    st.session_state[PREFIX + "right_end_x_m"] = span


def _render_review(config):
    labels = {
        "load_reference_confirmed": "Force reference checked for the local section",
        "hoop_confirmed": "End hoops and perimeter bars checked against drawing",
        "d_region_confirmed": "Bearing, anchorage and D-region reviewed separately",
    }
    with st.expander("Engineering review"):
        st.caption("These declarations record completed reviews. They are optional for calculating section capacities.")
        for key, label in labels.items():
            config[key] = st.checkbox(label, key=PREFIX + key)
        st.caption("Force reference: imported Mux/Nu must use the local section centroid. End hoops must match the actual solid/taper section. Bearing, prestress transfer and anchorage require separate checks.")
    pending = sum(not config[key] for key in labels)
    if pending:
        st.caption(f"Engineering review: {pending} item(s) pending. Capacities can be calculated; passing results retain REVIEW until the applicable reviews are complete.")
    else:
        st.caption("Engineering review declarations saved. Separate end-region checks are outside the section-capacity calculation.")


def render_inputs(params, geometry):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.section_builder import _commercial_panel_title_html

    raw = dict((st.session_state.get("section_parameters") or {}).get(ends.SETTINGS_KEY) or {})
    span = ap._beam_uls_span_length_from_state(st.session_state, is_building=False)
    bounds = ap._beam_uls_section_bounds(geometry)
    height = bounds[3] - bounds[1]
    defaults = {
        "enabled": False, "left_solid_m": 1.5, "right_solid_m": 1.5,
        "left_taper_m": .25, "right_taper_m": .25,
        "width_mm": bounds[2] - bounds[0], "chamfer_mm": 0.0,
        "left_end_x_m": 0.0, "right_end_x_m": span,
        "hoop_confirmed": False, "d_region_confirmed": False,
        "load_reference_confirmed": False,
    }
    same_ends = raw.get("same_ends", (
        raw.get("left_solid_m", 1.5) == raw.get("right_solid_m", 1.5)
        and raw.get("left_taper_m", .25) == raw.get("right_taper_m", .25)
    ))
    widget_defaults = {
        **defaults, "same_ends": same_ends,
        "use_loads_span": _initial_coordinate_mode(raw, span) == "span",
    }
    if raw != st.session_state.get(PREFIX + "source"):
        for key, value in widget_defaults.items():
            st.session_state[PREFIX + key] = raw.get(key, value)
    for key, value in widget_defaults.items():
        st.session_state.setdefault(PREFIX + key, raw.get(key, value))

    with st.container(border=True):
        st.markdown(_commercial_panel_title_html("Solid End Sections", "ENDSIMPLE22", "Along Girder", "ULS"), unsafe_allow_html=True)
        enabled = st.checkbox("Enable solid precast end sections", key=PREFIX + "enabled")
        config = {**defaults, **raw, "enabled": enabled}
        if enabled:
            inputs, preview = st.columns([1, 1], gap="medium")
            with inputs:
                config["same_ends"] = st.checkbox("Same dimensions at both ends", key=PREFIX + "same_ends")
                if config["same_ends"]:
                    config["left_solid_m"] = st.number_input(
                        "Solid length at each end (m)", min_value=0.0, step=.1,
                        format="%.3f", key=PREFIX + "left_solid_m",
                        help="Length of the full rectangular section at EACH end. The transition length is additional.",
                    )
                    config["left_taper_m"] = st.number_input(
                        "Transition length at each end (m)", min_value=0.0, step=.05,
                        format="%.3f", key=PREFIX + "left_taper_m",
                        help="Additional length changing linearly from the rectangle to the I-section. Enter 0 for an abrupt change.",
                    )
                    for name in ("solid_m", "taper_m"):
                        config["right_" + name] = config["left_" + name]
                        st.session_state[PREFIX + "right_" + name] = config["right_" + name]
                else:
                    left, right = st.columns(2)
                    for col, side in ((left, "left"), (right, "right")):
                        with col:
                            config[side + "_solid_m"] = st.number_input(
                                side.title() + " solid length (m)", min_value=0.0,
                                step=.1, format="%.3f", key=PREFIX + side + "_solid_m",
                            )
                            config[side + "_taper_m"] = st.number_input(
                                side.title() + " transition length (m)", min_value=0.0,
                                step=.05, format="%.3f", key=PREFIX + side + "_taper_m",
                            )
                config["width_mm"] = st.number_input(
                    "Solid-end width (mm)", min_value=1.0, step=10.0,
                    key=PREFIX + "width_mm", help="Actual rectangle width from the drawing. Initially uses the widest I-girder flange.",
                )
                st.caption(f"Solid rectangle: {config['width_mm']:,.0f} × {height:,.0f} mm. Height comes from the precast girder; deck thickness is separate.")

                with st.expander("More end-section options"):
                    use_span = st.checkbox(
                        "Use full Loads span for girder ends", key=PREFIX + "use_loads_span",
                        help="Use x = 0 and x = L only when these match the actual precast cut ends on the Loads axis. Otherwise enter custom end coordinates.",
                    )
                    config["coordinate_mode"] = "span" if use_span else "custom"
                    if use_span:
                        config["left_end_x_m"], config["right_end_x_m"] = 0.0, span
                        st.caption(f"Automatic coordinates: 0.000 to {span:.3f} m. They follow the Loads span when it changes.")
                    else:
                        for side in ("left", "right"):
                            key = side + "_end_x_m"
                            config[key] = st.number_input(
                                side.title() + " physical end x in Loads (m)", min_value=0.0,
                                step=.025, format="%.3f", key=PREFIX + key,
                            )
                    config["chamfer_mm"] = st.number_input(
                        "Solid-end corner chamfer (mm)", min_value=0.0, step=5.0,
                        key=PREFIX + "chamfer_mm",
                    )
                    st.caption("End coordinates use the existing Loads axis. Strand development starts at the actual cut ends; imported forces and deck-bar coordinates are preserved.")
                qualifier = "from Loads span" if config["coordinate_mode"] == "span" else "custom coordinates"
                st.caption(f"Girder ends: x = {config['left_end_x_m']:.3f} to {config['right_end_x_m']:.3f} m ({qualifier}). These must match the actual cut ends.")
                _render_review(config)

            params[ends.SETTINGS_KEY] = config
            candidate = {**dict(st.session_state), "section_preset_key": "parametric_i_girder", "section_parameters": params}
            with preview:
                try:
                    profile = ends.profile(candidate, geometry, span)
                    key = PREFIX + "preview_x"
                    if not profile.left_x_m <= st.session_state.get(key, profile.left_x_m) <= profile.right_x_m:
                        st.session_state[key] = profile.left_x_m
                    st.session_state.setdefault(key, profile.left_x_m)
                    x = st.slider("Preview section at Loads x (m)", profile.left_x_m, profile.right_x_m, step=.025, format="%.3f", key=key)
                    local, trace = ends.section_at(geometry, profile, x)
                    bv = ap._beam_uls_web_width_mm(local)[0]
                    st.caption(f"{trace['Section region']} · bv ≈ {bv:,.0f} mm · Acp = {trace['Section Acp mm2']/1e6:.4f} m²")
                    fig = create_section_preview(local, [], dimension_label_mode="symbol_value")
                    fig.update_layout(height=340)
                    st.plotly_chart(fig, use_container_width=True, key=PREFIX + "preview")
                    with st.expander("Section ranges along girder"):
                        regions = [
                            {"Loads x start (m)": a, "Loads x end (m)": b, "Section": profile.location((a + b) / 2)[0]}
                            for a, b in zip(profile.boundaries, profile.boundaries[1:]) if b > a
                        ]
                        st.dataframe(pd.DataFrame(regions), hide_index=True, use_container_width=True)
                except (ValueError, TypeError, KeyError) as exc:
                    st.error(str(exc))
                    if not 0 <= config["left_end_x_m"] < config["right_end_x_m"] <= span:
                        st.caption(f"Current end coordinates: {config['left_end_x_m']:.3f} / {config['right_end_x_m']:.3f} m; Loads span: {span:.3f} m. Enter the actual cut ends under More end-section options.")
                        st.button("Use Loads span for girder ends", key=PREFIX + "reset_span", on_click=_use_loads_span, args=(span,))
                    st.caption("Fix the dimensions or coordinates above before calculating ULS capacities.")
            st.info("Recalculate ULS after editing. End geometry is used for strength checks. Bearing and anchorage checks remain separate; SLS and FE stiffness/self-weight still use the uniform section.")
        else:
            params[ends.SETTINGS_KEY] = config
            st.caption("Uniform I-section along the girder. Enable to enter the solid ends from the drawing.")
    st.session_state[PREFIX + "source"] = dict(config)
