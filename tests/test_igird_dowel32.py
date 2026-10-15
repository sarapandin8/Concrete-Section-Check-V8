"""Input/figure agreement, live edits and no implicit geometry acceptance."""
from copy import deepcopy
from unittest.mock import patch
import xml.etree.ElementTree as ET

from streamlit.testing.v1 import AppTest

from concrete_pmm_pro.analysis import igird_dowel_joint as joint
from concrete_pmm_pro.visualization.igird_dowel_detail import (
    DIMENSION_GUIDE, dimension_label, u_dowel_detail_svg,
)


def test_drawing_refs_match_the_existing_engine_fields_without_a_schema_change():
    assert [key for key,*_ in DIMENSION_GUIDE] == list(joint.DIMENSIONS)
    assert [ref for _,ref,*_ in DIMENSION_GUIDE] == list("ABCDEF")
    for key,ref,label,_ in DIMENSION_GUIDE:
        assert dimension_label(key) == f"{ref} · {label}"


def test_unknown_geometry_stays_unknown_and_svg_cannot_echo_user_markup():
    cfg = {key: None for key in joint.DIMENSIONS}
    cfg["cover_required_mm"] = 50
    cfg["row_spacing_mm"] = '<script>alert(1)</script>'
    before = deepcopy(cfg)
    svg = u_dowel_detail_svg(cfg,section_params={"Tslab_mm":350,"D1_mm":1500})
    root = ET.fromstring(svg)
    assert cfg == before and "<script>" not in svg
    assert root.attrib["role"] == "img"
    assert "Not entered" in svg and "50 mm" in svg
    assert "not to scale" in svg and "actual cover is checked separately" in svg
    assert "PASS" not in svg and "<style" not in svg
    # Critical endpoints are explained, rather than silently changing the
    # solver's definition of ldh, straight tails or straight bonded length.
    description = root.find("{http://www.w3.org/2000/svg}desc").text
    for phrase in ("OUTSIDE", "bend tangent", "Full diameter", "exclude the return bend"):
        assert phrase in description


SCRIPT = '''
import streamlit as st
from concrete_pmm_pro.analysis.igird_dowel_joint import KEY,MODE,DIMENSIONS
from concrete_pmm_pro.ui.igird_dowel_joint import render_settings
if 'cfg' not in st.session_state:
    st.session_state['cfg']={KEY:{'mode':MODE,**{k:None for k in DIMENSIONS}}}
st.session_state['cfg'].update(render_settings(st.session_state['cfg'],
    section_params={'Tslab_mm':350,'D1_mm':1500,'deck_long_rebar_top_cover_mm':50}))
'''


def test_dimension_form_rerun_preserves_actual_unknowns_and_never_solves():
    with patch.object(joint,"solve_mechanism",side_effect=AssertionError("Viewing a guide cannot calculate")):
        app = AppTest.from_string(SCRIPT,default_timeout=60).run()
        assert not app.exception and not app.button
        saved = deepcopy(app.session_state['cfg'])
        assert saved[joint.KEY]['cover_required_mm'] == 50
        assert all(saved[joint.KEY][k] is None for k in joint.DIMENSIONS if k!='cover_required_mm')
        assert len([m for m in app.markdown if 'data-dowel-guide=' in m.value]) == 1
        editor = next(node for node in app.dataframe if str(node.key).startswith('input30_dimensions_'))
        assert editor.value['Dimension'].tolist() == [dimension_label(k) for k in joint.DIMENSIONS]
        app.run()
        assert not app.exception and app.session_state['cfg'] == saved


def test_edit_updates_figure_labels_immediately_without_filling_other_lengths():
    app = AppTest.from_string(SCRIPT,default_timeout=60).run()
    editor = next(node for node in app.dataframe if str(node.key).startswith('input30_dimensions_'))
    app.session_state[editor.key] = {'edited_rows':{0:{'Value mm':80.},1:{'Value mm':280.}},
        'added_rows':[],'deleted_rows':[]}
    app.run()
    assert not app.exception
    cfg = app.session_state['cfg'][joint.KEY]
    assert cfg['row_spacing_mm'] == 80 and cfg['slab_ldh_available_mm'] == 280
    assert cfg['hook_tail_mm'] is cfg['girder_ld_available_mm'] is None
    svg = next(m.value for m in app.markdown if 'data-dowel-guide=' in m.value)
    assert '80 mm' in svg and '280 mm' in svg
    app.run()
    assert not app.exception and app.session_state['cfg'][joint.KEY] == cfg
