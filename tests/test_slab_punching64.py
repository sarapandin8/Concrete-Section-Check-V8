"""Independent US/SI examples, perimeter geometry and conservative-demand gates."""
from copy import deepcopy
import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_punching64 as p, slab_shear64 as code, slab_aashto63 as accepted
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_shell56_geometry import SlabGeometry
from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
from test_slab_shell56 import steel,model_state


def area(x=5.,y=5.,l=300.,b=300.,vu=None,name='P1'):
    return dict(zip(p.COLUMNS,[name,x,y,l,b,vu]))


def mesh(q=lambda x,y:(10.,20.)):
    elements={};corners=[];forces=[]
    for i in range(10):
        for j in range(10):
            e=f'{i}:{j}'
            xy=np.array([[i,j],[i+1,j],[i+1,j+1],[i,j+1]],float)
            elements[e]=np.column_stack((xy,np.zeros(4)))
            for k,(x,y) in enumerate(xy):
                joint=str(k)
                corners.append({'Area':'A','AreaElem':e,'Joint':joint,'Thickness (mm)':350.,'X (m)':x,'Y (m)':y})
                vx,vy=q(x,y)
                for step,scale in [('Max',1.),('Min',-.6)]:
                    forces.append({'AreaElem':e,'Joint':joint,'OutputCase':'U1A','StepType':step,
                        'Vx':vx*scale,'Vy':vy*scale,INCLUDED:True})
    axes={'A':{'long':np.array([1.,0.,0.]),'up':np.array([0.,0.,1.])}}
    return {'geometry':SlabGeometry(pd.DataFrame(corners),elements,axes),
        'steel':steel(),'rows':pd.DataFrame(forces),'supports':[]}


@pytest.mark.parametrize('beta',[1.,2.,4.,10.])
def test_source_equation_matches_independent_us_example(beta):
    # Same section in US customary units: fc=5 ksi, dv=10 in, b0=100 in.
    vn_kip=min(.063+.126/beta,.126)*math.sqrt(5)*100*10
    r=p.resistance(5*6.894757293,beta,100*25.4,10*25.4)
    assert r['Vn (kN)']==pytest.approx(vn_kip*4.4482216152605,rel=2e-10)
    assert r['phiVn (kN)']==pytest.approx(.9*vn_kip*4.4482216152605,rel=2e-10)


def test_hand_perimeters_interior_edge_and_corner_exclude_free_edges():
    bounds=(0,0,10,10);dv=.2
    interior=p.critical_perimeters(bounds,(4.85,4.85,5.15,5.15),dv)[0]
    assert interior['type']=='Interior' and interior['length_m']==pytest.approx(2.)
    # Even though the closed offset contour fits, the three-sided path is shorter.
    edge=p.critical_perimeters(bounds,(.15,4.85,.45,5.15),dv)[0]
    assert edge['type']=='Left edge' and edge['length_m']==pytest.approx(1.6)
    corner=p.critical_perimeters(bounds,(.05,.05,.35,.35),dv)[0]
    assert corner['type']=='Left-bottom corner' and corner['length_m']==pytest.approx(.9)


def test_constant_shear_bound_and_depth_read_existing_geometry_without_mesh_vs():
    base=mesh();r=p.calculate(base,[area()]);row=r['rows'].iloc[0]
    dv=.9*(350-64);side=.3+dv/1000
    # Integral of |Qn| = 2 side Vx + 2 side Vy; signed resultant would be zero.
    assert row['dv (mm)']==pytest.approx(dv)
    assert row['b0 (mm)']==pytest.approx(4*side*1000)
    assert row['Vu (kN)']==pytest.approx(2*side*(10+20))
    assert row.Status=='PASS (sufficient)'
    base['steel']=steel(area=4000)
    doubled=p.calculate(base,[area()])['rows'].iloc[0]
    assert doubled['phiVn (kN)']==row['phiVn (kN)']


def test_affine_field_upper_bound_exceeds_independent_divergence_result():
    # div Q = 2 + 3 = 5 kN/m2 over the enclosed control area.
    r=p.calculate(mesh(lambda x,y:(2*(x-5),3*(y-5))),[area()])
    row=r['rows'].iloc[0];side=.3+row['dv (mm)']/1000
    actual=5*side**2
    assert row['Vu (kN)']>=actual>0


def test_fe_boundary_cut_is_not_added_twice_and_global_rotation_preserves_result():
    base=mesh();definition=area(x=5.5,y=5.5,l=742.6,b=742.6)
    first=p.calculate(base,[definition])['rows'].iloc[0]
    # dv=257.4mm, so the critical box lies exactly on the 5/6m mesh edges.
    assert first['b0 (mm)']==pytest.approx(4000.)
    assert first['Vu (kN)']==pytest.approx(60.)
    angle=.41;rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    for e,xyz in base['geometry'].elements.items():xyz[:,:2]=xyz[:,:2]@rotation.T
    base['geometry'].parent_axes['A']['long']=np.r_[rotation[:,0],0.]
    point=np.array([5.5,5.5])@rotation.T
    second=p.calculate(base,[area(x=point[0],y=point[1],l=742.6,b=742.6)])['rows'].iloc[0]
    assert second['D/C']==pytest.approx(first['D/C'])


def test_exceeded_envelope_is_review_but_actual_factored_exceedance_is_fail():
    base=mesh(lambda x,y:(5000.,5000.))
    automatic=p.calculate(base,[area()])['rows'].iloc[0]
    assert automatic['D/C']>1 and automatic.Status=='REVIEW'
    direct=p.calculate(base,[area(vu=2000)])['rows'].iloc[0]
    assert direct['D/C']>1 and direct.Status=='FAIL'
    direct=p.calculate(base,[area(vu=10)])['rows'].iloc[0]
    assert direct.Status=='PASS' and direct['Vu (kN)']==10


@pytest.mark.parametrize('bad',['excluded','missing','step','duplicate','nan','inf'])
def test_unqualified_source_never_becomes_automatic_numeric_punching(bad):
    base=mesh();before=base['rows'].copy(deep=True)
    # The chosen patch lies inside four FEs adjoining (5,5).
    mask=base['rows'].AreaElem.eq('4:4') & base['rows'].Joint.eq('2')
    if bad=='excluded':base['rows'].loc[mask,INCLUDED]=False
    elif bad=='missing':base['rows']=base['rows'].loc[~mask]
    elif bad=='step':base['rows']=base['rows'].loc[~(mask&base['rows'].StepType.eq('Min'))]
    elif bad=='duplicate':
        removed=base['rows'].loc[~(mask&base['rows'].StepType.eq('Min'))]
        base['rows']=pd.concat((removed,base['rows'].loc[mask&base['rows'].StepType.eq('Max')]))
    else:base['rows'].loc[mask&base['rows'].StepType.eq('Min'),'Vx']=np.nan if bad=='nan' else np.inf
    source=base['rows'].copy(deep=True)
    row=p.calculate(base,[area()])['rows'].iloc[0]
    assert row.Status=='REVIEW' and pd.isna(row['D/C']) and pd.isna(row['Vu (kN)'])
    pd.testing.assert_frame_equal(base['rows'],source)
    # An independently known design force is not a reconstruction of bad nodes.
    assert p.calculate(base,[area(vu=10)])['rows'].iloc[0].Status=='PASS'


@pytest.mark.parametrize('bad',['thickness','slope','hole','support','overlap','outside'])
def test_special_geometry_requires_review_even_with_known_design_force(bad):
    base=mesh();areas=[area(vu=10)]
    if bad=='thickness':base['geometry'].corners.loc[lambda f:f.AreaElem.eq('4:4'),'Thickness (mm)']=300.
    elif bad=='slope':base['geometry'].parent_axes['A']['up']=np.array([0,.01,.99995])
    elif bad=='hole':del base['geometry'].elements['0:0']
    elif bad=='support':base['supports']=[{'a':np.array([0.,5.]),'b':np.array([10.,5.]),'half_width':.1}]
    elif bad=='overlap':areas.append(area(x=5.1,vu=10,name='P2'))
    else:areas=[area(x=0,vu=10)]
    rows=p.calculate(base,areas)['rows']
    assert rows.Status.eq('REVIEW').all() and rows['D/C'].isna().all()


def test_no_invented_load_area_and_invalid_input_is_actionable():
    assert p.calculate(mesh(),[])['status']=='NOT CALCULATED'
    assert p.normalise(pd.DataFrame(columns=p.COLUMNS))==[]
    for a in [area(l=-1),area(x=np.inf),area(vu=-1),area(b=None)]:
        with pytest.raises(ValueError):p.normalise([a])


def test_punching_changes_reuse_accepted_oneway_only_while_base_is_current():
    state=model_state();baseline=accepted.calculate(state)
    state['project_metadata']={p.CONFIG_KEY:{'version':1,'areas':[area(x=.5,y=.5,vu=10)]}}
    with patch.object(accepted,'calculate',side_effect=AssertionError('base reran')):
        first=code.calculate(state,reuse=baseline)
        assert first['base_reused']
        pd.testing.assert_frame_equal(first['summary'],baseline['summary'])
    state[code.RESULT_KEY]=first
    assert code.current(state) is first
    state['project_metadata'][p.CONFIG_KEY]['areas'][0]['L (mm)']=400
    assert code.current(state) is None
    with patch.object(accepted,'calculate',wraps=accepted.calculate) as solver:
        code.calculate(state,reuse=baseline);assert solver.call_count==0
        state['section_parameters']['deck_long_rebar_top_spacing_mm']=250
        code.calculate(state,reuse=baseline);assert solver.call_count==1


def test_project_json_retains_area_inputs_and_never_saves_runtime_results():
    state=model_state();areas=[area(x=.5,y=.5,vu=10)]
    state['project_metadata']={p.CONFIG_KEY:{'version':1,'areas':areas}}
    state[code.RESULT_KEY]=code.calculate(state)
    encoded=project_to_json(project_from_session_state(state))
    assert code.RESULT_KEY not in encoded and 'base_result' not in encoded
    restored={code.RESULT_KEY:{'old':True}}
    apply_project_to_session_state(project_from_json(encoded),restored)
    assert p.config(restored)==areas and code.RESULT_KEY not in restored
