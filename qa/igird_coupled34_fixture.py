"""SYNTHETIC research hypothesis for software QA; never a user-model update.

Existing geometry, steel, load rows and force-reference snapshots stay intact.
These U-detail / closure values are deliberately hypothetical and unvalidated.
"""
from copy import deepcopy


def configure_hypothesis(state):
    from concrete_pmm_pro.ui import analysis_page as ap,igird_coupled_model as ui
    cfg={"enabled":True,"closure_db_mm":12.,"closure_spacing_mm":150.,"lap_available_mm":900.,
        "closure_detail":"continuous closed unit with verified 135-degree torsion anchorage",
        "drawing_reference":"SYNTHETIC QA — no actual shop-drawing or structural validation","action_rows":[]}
    metadata=deepcopy(state.get("project_metadata") or {});metadata[ui.KEY]=cfg
    interface=ap._igird_interface_shear_settings_from_state(state)
    interface["dowel_zones"]=[{"Zone":"SYNTHETIC QA dowels","x_start_m":0.,"x_end_m":20.,
        "Diameter_mm":12.,"Legs":2,"Spacing_mm":150.,"fy_MPa":390.}]
    interface["dowel_connection"].update(row_spacing_mm=100.,slab_ldh_available_mm=250.,hook_tail_mm=200.,
        hook_inside_bend_mm=72.,cover_required_mm=40.,girder_ld_available_mm=1000.,coating="uncoated",anchorage_region="interior")
    state[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]=interface
    metadata[ap._IGIRDER_INTERFACE_SHEAR_SETTINGS_KEY]=interface
    state["project_metadata"]=metadata

