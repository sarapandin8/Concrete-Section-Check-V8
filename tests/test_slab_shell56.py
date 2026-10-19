"""Independent section examples, tensor/geometry checks and calculation-only UI."""
from copy import deepcopy
import math

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_shell56_geometry import inverse_quad, local_axes, steel_axis_forces, recover, GeometryError
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY
from concrete_pmm_pro.io.project_io import apply_project_to_session_state
from concrete_pmm_pro.core.project import ProjectModel
from concrete_pmm_pro.core.analysis import AnalysisModeSettings
from test_slab_shell55 import fixtures, upload


def steel(area=1000., centres=(64.,64.,48.,48.)):
    return engine.SlabSteel(np.full(4,area),np.full(4,390.),np.array(centres),np.full(4,16.),np.full(4,150.),35.)


def check(n=(0.,0.,0.), m=(0.,0.,0.), v=(0.,0.), *, h=350., reinforcement=None):
    return engine.section_check(np.array([h]),np.array([n]),np.array([m]),np.array([v]),reinforcement or steel()).iloc[0]


@pytest.mark.parametrize("direction,index",[(0,1),(1,3)])
@pytest.mark.parametrize("sign",[-1,1])
def test_uniaxial_bending_matches_independent_rectangular_force_couple(direction,index,sign):
    moment=[0.,0.,0.];moment[direction]=sign*40
    r=check(m=moment)
    # A 1 m strip: tie Rd=0.9*1000*390=351 kN; concrete design stress
    # 0.7*0.45*35=11.025 MPa. Solve C=T and M=T*(d-a/2) by hand.
    depth=350-([64,48][direction]);a=351000/(11.025*1000)
    resistance=351*(depth-a/2)/1000
    assert r['Field D/C']==pytest.approx(40/resistance,rel=1e-10)
    compression_index=index-1 if sign>0 else index
    tension_index=index if sign>0 else index-1
    assert r[engine.GROUPS[compression_index]+' force (N/mm)']==pytest.approx(0,abs=1e-9)
    assert r[engine.GROUPS[tension_index]+' force (N/mm)']>0
    assert r['Equilibrium residual']<1e-12


def test_uniaxial_tension_is_shared_by_the_two_physical_mats():
    r=check(n=(100,0,0))
    assert r['Top longitudinal force (N/mm)']==pytest.approx(50)
    assert r['Bottom longitudinal force (N/mm)']==pytest.approx(50)
    assert r['Concrete D/C']==0


def test_axial_compression_does_not_invent_tensile_bar_credit():
    r=check(n=(-100,0,0))
    assert r['Top longitudinal force (N/mm)']==0
    assert r['Bottom longitudinal force (N/mm)']==0
    assert r['Cx top (N/mm)']==pytest.approx(50)
    assert r['Cx bottom (N/mm)']==pytest.approx(50)


@pytest.mark.parametrize('sign',[-1,1])
def test_pure_membrane_shear_matches_45_degree_compression_field(sign):
    r=check(n=(0,0,sign*60))
    for g in engine.GROUPS:
        assert r[g+' force (N/mm)']==pytest.approx(30)
    assert r['q top (N/mm)']==pytest.approx(sign*30)
    assert r['q bottom (N/mm)']==pytest.approx(sign*30)


def test_six_resultants_reconstruct_with_asymmetric_real_bar_heights():
    s=steel(centres=(64.,72.,48.,55.))
    n=np.array([[120.,-310.,68.],[-300.,-150.,-90.],[0,0,0]])
    m=np.array([[40.,-32.,15.],[-80.,45.,-26.],[0,0,60.]])
    result=engine.section_check(np.full(3,350.),n,m,np.zeros((3,2)),s)
    for row_number,r in result.iterrows():
        a=r['Face depth (mm)'];zt=175-a/2;zb=-175+a/2
        q=np.array([r['q top (N/mm)'],r['q bottom (N/mm)']])
        reconstructed_n=[];reconstructed_m=[]
        for j,d in ((0,'x'),(2,'y')):
            t=np.array([r[engine.GROUPS[j]+' force (N/mm)'],r[engine.GROUPS[j+1]+' force (N/mm)']])
            c=np.array([r['C'+d+' top (N/mm)'],r['C'+d+' bottom (N/mm)']])+abs(q)
            # Independent physical lever arms, not engine.z().
            zsteel=np.array([175-s.centre[j],-175+s.centre[j+1]])
            reconstructed_n.append(t.sum()-c.sum())
            reconstructed_m.append(-(zsteel@t-np.array([zt,zb])@c)/1000)
        reconstructed_n.append(q.sum())
        reconstructed_m.append(-(zt*q[0]+zb*q[1])/1000)
        np.testing.assert_allclose(reconstructed_n,n[row_number],atol=1e-8)
        np.testing.assert_allclose(reconstructed_m,m[row_number],atol=1e-8)


def test_load_scaling_and_more_steel_give_consistent_uniaxial_capacity():
    a,b=check(m=(50,0,0)),check(m=(100,0,0))
    assert b['Field D/C']==pytest.approx(2*a['Field D/C'])
    c=check(m=(100,0,0),reinforcement=steel(area=1500))
    assert c['Field D/C']<b['Field D/C']


def test_temperature_minimum_reference_and_high_fy_cap():
    # AASHTO 5.10.6, b→infinity: h=12 in, fy=60 ksi → 0.13 in²/ft.
    result=engine.temperature_minimum(np.array([304.8]),np.array([60*6.894757293]*4))
    np.testing.assert_allclose(result,.13*645.16/304.8*1000)
    lower=engine.temperature_minimum(np.array([50.]),np.full(4,390.))
    np.testing.assert_allclose(lower,.11*645.16/304.8*1000)
    np.testing.assert_allclose(engine.temperature_minimum(np.array([350.]),np.full(4,1000.)),
                               engine.temperature_minimum(np.array([350.]),np.full(4,75*6.894757293)))


def test_zero_actions_keep_minimum_steel_check_and_do_not_require_a_shear_strain():
    r=check()
    assert r['Shear D/C']==0 and r['Status']=='Preview PASS'
    assert r['Top longitudinal D/C']>0
    assert r['Top longitudinal Strength D/C']==0


def test_added_shear_longitudinal_tie_is_not_omitted_or_phi_counted_twice():
    r=check(v=(20,0))
    assert r['Top longitudinal shear tie (N/mm)']==pytest.approx(20/.9)
    assert r['Bottom longitudinal shear tie (N/mm)']==pytest.approx(20/.9)
    assert r['Top transverse shear tie (N/mm)']==0
    diagonal=check(v=(20,20))
    assert diagonal['Top longitudinal shear tie (N/mm)']==pytest.approx(math.sqrt(800)/.9)
    assert diagonal['Top transverse shear tie (N/mm)']==pytest.approx(math.sqrt(800)/.9)


def test_shear_applicability_failure_never_becomes_preview_pass():
    r=check(n=(7000,0,0),v=(1,0),reinforcement=steel(area=10000,centres=(100,100,60,60)))
    assert math.isnan(r['Shear D/C']) and r['Status']=='REVIEW'


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf')])
def test_unknown_actions_are_not_zero(bad):
    with pytest.raises((ValueError,TypeError)):
        check(m=(bad,0,0))


def test_overlapping_mats_and_invalid_material_are_blocked():
    with pytest.raises(ValueError,match='overlap'):
        check(h=130)
    with pytest.raises(ValueError,match='positive'):
        engine.SlabSteel(np.zeros(4),np.ones(4),np.ones(4),np.ones(4),np.ones(4),35.)


def test_random_signed_force_fields_keep_equilibrium_and_exclude_parallel_face_tension():
    rng=np.random.default_rng(56)
    rows=engine.section_check(rng.uniform(200,400,500),rng.uniform(-900,500,(500,3)),
        rng.uniform(-200,200,(500,3)),rng.uniform(-30,30,(500,2)),steel())
    assert rows['Equilibrium residual'].max()<1e-10
    for d,g in [('x',0),('y',2)]:
        for face,i in [('top',g),('bottom',g+1)]:
            assert not ((rows[f'C{d} {face} (N/mm)']>1e-7) & (rows[engine.GROUPS[i]+' force (N/mm)']>1e-7)).any()


def test_general_quadrilateral_thickness_uses_original_corner_order():
    p=np.array([[0,0,0],[2,0,0],[1.5,1,0],[0,1,0]],float)
    weights=np.array([.21,.09,.21,.49])  # u=.3, v=.7
    recovered=inverse_quad(p,weights@p)
    np.testing.assert_allclose(recovered,weights,atol=1e-12)
    assert recovered@np.array([200,350,300,250])==pytest.approx(259.)


def test_rotated_axes_and_normal_reversal_transform_both_tensors_correctly():
    original=pd.DataFrame([dict(Area='1',F11=10.,F22=20.,F12=3.,M11=4.,M22=-7.,M12=2.,V13=5.,V23=6.)])
    rotation=np.array([[0,1],[-1,0]])
    transformed=steel_axis_forces(original,{'1':{'rotation':rotation,'normal_sign':1}}).iloc[0]
    np.testing.assert_allclose(transformed[['Nx','Ny','Nxy']].to_numpy(float),[20,10,-3])
    np.testing.assert_allclose(transformed[['Mx','My','Mxy']].to_numpy(float),[-7,4,-2])
    flip=steel_axis_forces(original,{'1':{'rotation':np.diag([1,-1]),'normal_sign':-1}}).iloc[0]
    np.testing.assert_allclose(flip[['Mx','My','Mxy']].to_numpy(float),[-4,7,2])
    np.testing.assert_allclose(original[['M11','M22','M12']].iloc[0].to_numpy(),[4,-7,2])


def model_state():
    data=fixtures()
    data['flags'][0].update(StartSta=0.,EndSta=1.)
    # A second straight parent Area supplies station progression.
    data['flags'].append({**data['flags'][0],'Area':2,'StartSta':1.,'EndSta':2.})
    for key in ('thickness','sections','axes','advanced'):
        data[key].append({**data[key][0],'Area':2})
    new_ids=['A','B','C','D']
    data['parents'].append(dict(Area=2,NumJoints=4,**{f'Joint{i}':j for i,j in enumerate(new_ids,1)}))
    data['elements'].append(dict(AreaElem='2-1',AreaObject=2,**{f'ElemJt{i}':j for i,j in enumerate(new_ids,1)}))
    for j,x,y in zip(new_ids,[1,2,2,1],[0,0,1,1]):
        data['nodes'].append(dict(JointElem=j,GlobalX=x,GlobalY=y,GlobalZ=0))
        data['joints'].append(dict(Joint=j,GlobalX=x,GlobalY=y,GlobalZ=0))
    first=deepcopy(data['forces']);data['forces']=[]
    for area,elem,corners in [(1,'1-1',['~1','2','3','4']),(2,'2-1',new_ids)]:
        data['forces'] += [{**row,'Area':area,'AreaElem':elem,'Joint':j} for row in first for j in corners]
    package=parse_files([upload(data)])
    assert package.ready,package.errors
    p={'Tslab_mm':350.,'deck_fc_MPa':35.,'deck_long_rebar_fy_MPa':390.}
    for face in ('top','bottom'):
        p.update({f'deck_long_rebar_{face}_diameter_mm':16.,f'deck_long_rebar_{face}_spacing_mm':150.})
    cfg={'slab_transverse_mesh':{face:dict(Diameter_mm=16.,Spacing_mm=150.,Clear_cover_mm=40.,fy_MPa=390.) for face in ('top','bottom')}}
    state={}
    apply_project_to_session_state(ProjectModel(analysis_mode_settings=AnalysisModeSettings(member_type='beam_girder'),
        section_parameters=p),state)
    state['beam_girder_interface_shear_settings']={'dowel_connection':cfg}
    state[BANK_KEY]=package
    return state


def test_complete_source_scan_preserves_case_steps_corners_and_endpoints():
    state=model_state();source=state[BANK_KEY].tables['forces'].copy(deep=True)
    result=engine.calculate(state)
    assert result['source_rows']==64 and not result['incomplete']
    assert set(result['rows']['OutputCase'])=={'U1A','U1B','U2A','U2B'}
    assert set(result['rows']['StepType'])=={'Max','Min'}
    assert result['rows'].loc[result['rows']['X (m)']==0,'Field D/C'].gt(0).all()
    assert len(result['summary'])==4
    pd.testing.assert_frame_equal(source,state[BANK_KEY].tables['forces'])
    state[engine.RESULT_KEY]=result
    assert engine.current(state) is result
    state['slab_shell55_view']='Top longitudinal'
    state['slab_shell55_case']='U1A'
    assert engine.current(state) is result
    state['section_parameters']['H_mm']=9000  # girder dimensions do not alter a fixed shell import
    assert engine.current(state) is result
    state['section_parameters']['deck_long_rebar_top_spacing_mm']=200
    assert engine.current(state) is None


def test_missing_bar_or_unsupported_code_does_not_get_an_inferred_strength():
    state=model_state();state['section_parameters']['deck_long_rebar_top_diameter_mm']=None
    with pytest.raises(ValueError,match='diameter'):
        engine.steel_from_state(state)
    state=model_state();state['project_code_edition']='AASHTO LRFD 8th Edition'
    with pytest.raises(ValueError,match='9th Edition'):
        engine.steel_from_state(state)


def test_missing_station_alignment_is_actionable_not_assumed_global_x():
    state=model_state();state[BANK_KEY].tables['flags']=state[BANK_KEY].tables['flags'].drop(columns=['StartSta'])
    with pytest.raises(GeometryError,match='StartSta'):
        recover(state[BANK_KEY])
