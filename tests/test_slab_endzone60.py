"""Inclusive end-to-bearing exclusions, independent of actions and D/C."""
from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED, REASON, END_REASON, annotate, layout
from concrete_pmm_pro.analysis.slab_shell56_geometry import recover
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope, plan_figure
from test_slab_connections59 import connected_state


def end_state():
    state=connected_state()
    state['igird_shear_support_settings']={'locations_confirmed':True,'offset_reference':'centerline',
        'left_offset_m':.25,'right_offset_m':.35,'left_bearing_length_mm':0.,'right_bearing_length_mm':0.}
    return state


def test_end_zone_uses_existing_bearing_reference_and_includes_both_boundaries_full_width():
    state=end_state(); package=state[BANK_KEY]
    con=layout(package,recover(package),state)
    ends=con['end_zones']
    assert ends['active'] and ends['reference']=='centerline'
    assert ends['zones'][0]['To station (m)']==.25
    assert ends['zones'][1]['From station (m)']==1.65
    # Y=1000 deliberately lies far from every girder line: the end zone is
    # applied over the complete width, not merely near girder intersections.
    frame=pd.DataFrame({'X (m)':[0,.25,.25001,.25005,1.,1.64995,1.65,2.], 'Y (m)':[1000.]*8})
    result=annotate(frame,con)
    assert result[INCLUDED].tolist()==[False,False,False,True,True,True,False,False]
    assert result.loc[1,END_REASON]=='Left end to bearing'
    assert result.loc[6,END_REASON]=='Right end to bearing'


def test_engine_never_solves_end_nodes_and_retains_raw_source_coverage():
    state=end_state(); source=state[BANK_KEY].tables['forces'].copy(deep=True)
    with patch.object(engine,'section_check',wraps=engine.section_check) as solver:
        result=engine.calculate(state)
    assert result['source_rows']==64 and result['design_rows']==16 and result['excluded_rows']==48
    assert result['bearing_excluded_rows']==32
    assert sum(len(c.args[0]) for c in solver.call_args_list)==16
    kept=result['rows'].loc[result['rows'][INCLUDED]]
    np.testing.assert_allclose(kept['X (m)'],1.)
    assert result['rows'].loc[~result['rows'][INCLUDED],'Field D/C'].isna().all()
    assert result['coverage']['Missing records'].sum()==0
    assert result['coverage']['Excluded records'].sum()==48
    pd.testing.assert_frame_equal(source,state[BANK_KEY].tables['forces'])


def test_arbitrarily_large_end_actions_cannot_control_nominal_envelope():
    state=end_state(); first=engine.calculate(state)
    other=deepcopy(state)
    end_joints=set(first['rows'].loc[first['rows'][END_REASON].ne(''),'Joint'])
    actions=['F11','F22','F12','M11','M22','M12','V13','V23']
    f=other[BANK_KEY].tables['forces']; f.loc[f.Joint.isin(end_joints),actions]=1e12
    second=engine.calculate(other)
    pd.testing.assert_frame_equal(first['summary'],second['summary'])
    pd.testing.assert_frame_equal(first['check_summary'],second['check_summary'])
    assert first['status']==second['status']
    assert second['rows'].loc[second['rows'][END_REASON].ne(''),'Field D/C'].isna().all()


def test_unconfirmed_bearings_do_not_create_guessed_end_limits():
    state=end_state(); state['igird_shear_support_settings']['locations_confirmed']=False
    package=state[BANK_KEY]; con=layout(package,recover(package),state)
    assert not con['end_zones']['active']
    assert engine.calculate(state)['design_rows']==32


def test_bearing_changes_invalidate_result_and_inside_face_is_not_mislabeled_as_centerline():
    state=end_state(); state[engine.RESULT_KEY]=engine.calculate(state)
    assert engine.current(state) is state[engine.RESULT_KEY]
    state['igird_shear_support_settings']['left_offset_m']=.30
    assert engine.current(state) is None
    state['igird_shear_support_settings']['offset_reference']='inside_face'
    package=state[BANK_KEY]; con=layout(package,recover(package),state)
    assert con['end_zones']['reference']=='inside_face'
    assert con['end_zones']['zones'][0]['To station (m)']==.30


def test_rotated_end_planes_use_longitudinal_station_not_global_x():
    theta=np.deg2rad(29.); direction=np.array([np.cos(theta),np.sin(theta)])
    normal=np.array([-direction[1],direction[0]])
    origin=3.; p=np.array([(origin+s)*direction+10*normal for s in [0,.25,.5,1.65,2.]])
    con={'lines':pd.DataFrame(columns=['Connection','X1 (m)','Y1 (m)','X2 (m)','Y2 (m)']),
         'end_zones':{'active':True,'longitudinal':direction.tolist(),'origin_s_m':origin,
            'zones':[{'Side':'Left','From station (m)':0.,'To station (m)':.25},
                     {'Side':'Right','From station (m)':1.65,'To station (m)':2.}]}}
    out=annotate(pd.DataFrame(p,columns=['X (m)','Y (m)']),con)
    assert out[INCLUDED].tolist()==[False,False,True,False,False]


def test_invalid_offsets_cannot_silently_exclude_an_entire_span():
    state=end_state(); state['igird_shear_support_settings']['left_offset_m']=2.
    with pytest.raises(ValueError,match='bearing offsets'):
        engine.calculate(state)


def test_end_polygons_are_visible_and_never_create_false_missing_corner_coverage():
    result=engine.calculate(end_state())
    selected=element_envelope(result,view='N–M field')
    assert not selected['Map incomplete'].any()
    fig=plan_figure(result,view='N–M field')
    assert any(t.name=='Excluded end zones' for t in fig.data)
    gov=next(t for t in fig.data if t.name.startswith('Gov.'))
    assert gov.x[0]==1.
