"""Independent mechanics, topology, reference prestress and input safety.

These certify software behaviour of the declared idealization, not the actual
joint, cracked-concrete law, bond-slip properties or production resistance.
"""
from copy import deepcopy
from dataclasses import replace
import json
import math
from unittest.mock import patch,MagicMock

import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from shapely.geometry import Polygon,box

from concrete_pmm_pro.analysis import igird_joint37_model as jm,igird_joint37_solver as js
from concrete_pmm_pro.analysis.igird_joint37_detail import audit
from concrete_pmm_pro.io.project_io import project_from_session_state,project_to_json,project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui import igird_joint37 as ui,igird_station36 as station,igird_flexure_workspace as fw,analysis_page as ap
from test_igird_csiref26 import seed,bound_row


def arguments():
    girder=box(-200,-500,200,500);slab=box(-400,500,400,800)
    bars=[{'label':f'bar {x}/{y}','kind':'ordinary','x_mm':x,'y_mm':y,'area_mm2':math.pi*16**2/4,
        'capacity_N':math.pi*16**2/4*390.,'development':{'db_mm':16.,'Es_MPa':200000.}} for x,y in [(-140,-440),(140,-440),(-140,440),(140,440)]]
    inventory=[{'label':layer,'kind':'ordinary','y_mm':y,'x_mm':0.,'area_mm2':area,'capacity_N':area*390.,
        'development':{'db_mm':16.,'Es_MPa':200000.}} for layer,y,area in [('top',742.,800.),('bottom',558.,1000.)]]
    params={'deck_long_rebar_top_spacing_mm':200.,'deck_long_rebar_bottom_spacing_mm':150.}
    return {'girder':girder,'slab':slab,'origin':{'target_y_mm':0.,'target_local3_mm':0.},'girder_fc':45.,'slab_fc':35.,
        'girder_E':32000.,'slab_E':28000.,'hoop':{'cover_mm':40.,'Diameter_mm':12.,'Spacing_mm':100.,'fy_MPa':390.},
        'bars':bars,'slab_longitudinal':jm.expand_slab_layers(params,inventory,left_mm=-400.,right_mm=400.),
        'transverse':{layer:{'Diameter_mm':12.,'Spacing_mm':150.,'Clear_cover_mm':66.,'fy_MPa':390.} for layer in ('top','bottom')},
        'detail':{'row_spacing_mm':120.,'girder_ld_available_mm':800.,'slab_ldh_available_mm':200.,'hook_inside_bend_mm':72.,'hook_tail_mm':200.},
        'dowel':{'Diameter_mm':12.,'Spacing_mm':100.,'fy_MPa':390.,'Legs':2.},'contact_width_mm':400.,'mu':1.,'interface_cap_MPa':10.5,'nominal':True}


@pytest.fixture(scope='module')
def assembly():return jm.build(**arguments())


def axial(*,prestressed=True):
    # Four equal corner tension springs, plus one concrete compression spring.
    # Independent solution under axial loading uses the single common strain.
    xy=[(-100,-100),(-100,100),(100,-100),(100,100),(0,0)]
    nodes=np.array([(L,y,z) for L in (0,1000) for y,z in xy],float);B=np.zeros((30,5))
    for i in range(5):B[3*i,i]=1.;B[3*(i+5),i]=-1.
    trace={'nominal':True,'pitch_mm':500.,'origin':{'target_y_mm':0.},'girder_polygon_xy_mm':[(-100,-100),(-100,100),(100,100),(100,-100)],'mu':1.}
    return jm.Model(nodes,['girder']*10,sparse.csr_matrix(B),np.array([[0,1e6]]*4+[[-1e6,0.]],float),sparse.csr_matrix((0,5)),np.array([]),[],
        ['s1','s2','s3','s4','concrete'],['prestress' if prestressed else 'ordinary']*4+['concrete'],np.array([2e4]*4+[8e4]),
        np.array([1000.]*4+[0.]) if prestressed else np.zeros(5),
        [{'i':i,'j':i+5,'length_mm':1000.,'kind':'prestress' if i<4 and prestressed else 'concrete','component':'girder'} for i in range(5)],
        list(range(15)),list(range(5,10)),[],[],trace)


def joint_patch():
    """Two developed leg springs + compression/friction at z=±50 mm.

    Rigid slab cut and fixed girder face: |T|max=a(F−opening/2), or
    a(F−P/(2mu)) at zero opening and equal longitudinal contact shears.
    This independent small model avoids calibrating the prism mesh to a job.
    """
    positions=[(0,0,-50),(0,0,50),(0,100,-50),(0,100,50)]
    nodes=np.array(positions+positions,float);cols=[];bounds=[];kinds=[];stiff=[];elements=[];contacts=[];dowels=[];rows=[]
    for side in range(2):
        ids=[]
        for kind,unit,lo,hi,k in [('contact_normal',[0,1,0],-1e6,0,1e6),('dowel',[0,1,0],0,1000,2e4),
                                 ('contact_shear',[1,0,0],-1e6,1e6,1e4),('contact_shear',[0,0,1],-1e6,1e6,1e4)]:
            col=np.zeros(24);col[3*side:3*side+3]=unit;col[3*(side+4):3*(side+4)+3]=-np.array(unit)
            ids.append(len(cols));cols.append(col);bounds.append((lo,hi));kinds.append(kind);stiff.append(k)
            elements.append({'i':side,'j':side+4,'component':'joint','kind':kind,'length_mm':0.})
        n,t,qx,qz=ids
        contacts.append({'plane':0,'x_mm':nodes[side,2],'normal':n,'qx':qx,'qz':qz,'area_mm2':1000.,'girder_node':side,'slab_node':side+4})
        dowels.append({'plane':0,'leg':side+1,'element':t,'area_mm2':math.pi*12**2/4,'single_leg_capacity_N':1000.,'girder_node':side,'slab_node':side+4})
        for facet in range(8):rows.append((n,qx,qz,(facet+.5)*math.pi/4))
    A=np.zeros((len(rows),len(cols)))
    for i,(n,qx,qz,angle) in enumerate(rows):A[i,n]=math.cos(math.pi/8);A[i,qx]=math.cos(angle);A[i,qz]=math.sin(angle)
    trace={'nominal':True,'pitch_mm':100.,'origin':{'target_y_mm':0.},'girder_polygon_xy_mm':[(-50,0),(50,0),(50,100),(-50,100)],
        'U_geometry':{'db_mm':12.},'mu':1.,'concrete_factor':1.,'slab_fc_MPa':35.}
    return jm.Model(nodes,['girder']*4+['slab']*4,sparse.csr_matrix(np.array(cols).T),np.array(bounds,float),sparse.csr_matrix(A),np.zeros(len(A)),
        ['friction']*len(A),[f'm{i}' for i in range(len(cols))],kinds,np.array(stiff),np.zeros(len(cols)),elements,list(range(12)),list(range(4,8)),contacts,dowels,trace)


def test_canonical_constrained_triangulation_preserves_nonconvex_area_and_input_order_invariance():
    polygon=Polygon([(0,0),(300,0),(300,100),(100,100),(100,300),(0,300)])
    points=[(50,50),(60,200),(200,50),(0,150),(100,150)]
    a,t,l=jm.triangulation(polygon,points)
    b,u,k=jm.triangulation(Polygon(list(polygon.exterior.coords)[::-1]),points[::-1])
    np.testing.assert_array_equal(a,b);assert t==u and l==k
    assert sum(Polygon(a[list(tri)]).area for tri in t)==pytest.approx(50000.)
    assert all(polygon.covers(Polygon(a[list(tri)])) for tri in t)


def test_no_concrete_bridge_and_no_rigid_slab_boundary_bypass(assembly):
    m=assembly
    assert all(m.components[i//3]=='girder' for i in m.fixed_dofs)
    assert all(m.components[i]=='girder' for i in m.end_nodes)
    assert all(m.components[e['i']]==m.components[e['j']] for e in m.elements if e['kind']=='concrete')
    for contact in m.contacts:
        i,j=contact['girder_node'],contact['slab_node']
        assert i!=j and m.components[i]=='girder' and m.components[j]=='slab'
        np.testing.assert_allclose(m.nodes[i],m.nodes[j],atol=1e-8)


def test_nonoverlapping_concrete_and_interface_tributaries_reconstruct_real_volumes(assembly):
    t=assembly.trace;L=2*t['pitch_mm']
    assert t['concrete_volumes_mm3']==pytest.approx({'girder':400*1000*L,'slab':800*300*L})
    assert t['contact_area_mm2']==pytest.approx(400*L)
    assert t['concrete_cell_count']==t['prismatic_cells']


def test_U_is_continuous_with_two_crossings_and_no_double_leg_supply(assembly):
    m=assembly;db=12.;asbar=math.pi*db**2/4
    assert len(m.dowels)==6
    assert sum(d['area_mm2'] for d in m.dowels)==pytest.approx(2*asbar*400/100)
    assert {d['leg'] for d in m.dowels}=={1,2}
    assert len([k for k in m.kinds if k=='dowel'])>6 # actual bends and embedded segments
    cross=[e for e in m.elements if e['kind']=='dowel' and e['component']=='joint']
    assert len(cross)==6 and all(e['length_mm']==pytest.approx(24.) for e in cross)
    path=m.trace['U_path_xy_mm'];radius=42.
    assert max(p[1] for p in path)==pytest.approx(500+200-6)
    assert min(p[1] for p in path)==pytest.approx(500-800-radius)


def test_turning_off_U_removes_the_entire_physical_path_and_preserves_girder_hoops(assembly):
    cut=jm.without(assembly,'dowel')
    for i,kind in enumerate(assembly.kinds):
        if kind=='dowel':assert tuple(cut.bounds[i])==(0.,0.)
        else:np.testing.assert_array_equal(cut.bounds[i],assembly.bounds[i])
    np.testing.assert_array_equal(cut.A.toarray(),assembly.A.toarray())


def test_slab_entry_torque_requires_U_and_shares_mesh_and_friction(assembly):
    m=jm.slab_entry(assembly);h=[0,0,0,1e6,0,0]
    no=js.limit(jm.without(m,'dowel'),h);full=js.limit(m,h);less=js.limit(jm.without(m,'slab_transverse'),h)
    assert no['ready'] and no['model_T_limit_Nmm']==pytest.approx(0.,abs=1e-5)
    assert full['ready']
    assert less['ready'] and less['model_T_limit_Nmm']<=full['model_T_limit_Nmm']+1e-5
    assert all(c['friction_circle_ratio'] is None or c['friction_circle_ratio']<=1+1e-7 for c in full['interface']['contacts'])
    for key in ('accepted_phiTn_Nmm','accepted_VT_factor','full_composite_Tn_Nmm'):assert full[key] is None


@pytest.mark.parametrize('opening',[0.,250.,1500.])
def test_two_leg_joint_roll_and_opening_share_the_same_tension_supply(opening):
    m=joint_patch();r=js.limit(m,[0,opening,0,1e6,0,0]);assert r['ready'],r
    assert r['model_T_limit_Nmm']==pytest.approx(100*(1000-opening/2),abs=1e-5)
    assert js.limit(jm.without(m,'dowel'),[0,0,0,1e6,0,0])['model_T_limit_Nmm']==pytest.approx(0.,abs=1e-6)


@pytest.mark.parametrize('P',[0.,500.,1000.,1500.])
def test_joint_shear_and_torsion_compete_for_the_same_clamping_force(P):
    r=js.limit(joint_patch(),[P,0,0,1e6,0,0]);assert r['ready'],r
    assert r['model_T_limit_Nmm']==pytest.approx(100*(1000-P/2),abs=1e-5)
    assert all(c['friction_circle_ratio'] is None or c['friction_circle_ratio']<=1+1e-7 for c in r['interface']['contacts'])


def test_compatible_opening_and_sticking_slip_match_independent_spring_solutions():
    m=joint_patch();opened=js.compatible_state(m,[0,400,0,0,0,0]);assert opened['ready'],opened
    for c in opened['interface']['contacts']:
        assert c['model_opening_mm']==pytest.approx(.01,abs=1e-7)
        assert c['compression_N']==pytest.approx(0.,abs=1e-4)
    stick=js.compatible_state(m,[200,-400,0,0,0,0]);assert stick['ready'],stick
    for c in stick['interface']['contacts']:
        assert c['model_opening_mm']==pytest.approx(-.0002,abs=1e-7)
        assert c['model_slip_mm']==pytest.approx(.01,abs=1e-7)


def test_physical_reflection_reverses_torsion_without_changing_resistance(assembly):
    m=jm.slab_entry(assembly);mirror=m.nodes.copy();mirror[:,2]*=-1
    signs=np.tile([1.,1.,-1.],len(m.nodes));B=sparse.diags(signs)@m.B
    reflected=replace(m,nodes=mirror,B=B)
    a=js.limit(m,[0,0,0,1e6,0,0]);b=js.limit(reflected,[0,0,0,-1e6,0,0])
    assert a['ready'] and b['ready'] and a['model_T_limit_Nmm']==pytest.approx(b['model_T_limit_Nmm'],rel=1e-8)


def test_six_actions_and_free_bodies_are_reconstructed_independently(assembly):
    h=[100.,100.,50.,1e4,1e4,2e4];original=h.copy()
    r=js.limit(assembly,h,mode='VT_ray')
    assert r['ready'] and h==original
    rebuilt=r['checks']['rebuilt_wrench_N_Nmm'];factor=r['model_VT_factor']
    assert rebuilt==pytest.approx([h[0],h[1]*factor,h[2]*factor,h[3]*factor,h[4],h[5]],abs=1e-5)
    for field in ('equilibrium_relative','resource_relative','global_relative','slab_freebody_relative','duality_relative','dual_stationarity_relative'):assert r['checks'][field]<2e-7
    assert all(item['source'].startswith('JOINT37') for item in r['interface']['plane_wrenches'])


def test_nominal_factors_cannot_be_applied_twice_or_reduce_initial_Pe(assembly):
    f=jm.factored(assembly)
    np.testing.assert_array_equal(f.initial,assembly.initial)
    for i,kind in enumerate(assembly.kinds):
        factor=.7 if kind in ('concrete','contact_normal') else .9
        np.testing.assert_allclose(f.bounds[i],factor*assembly.bounds[i])
    for a,b in zip(assembly.dowels,f.dowels):assert b['single_leg_capacity_N']==pytest.approx(.9*a['single_leg_capacity_N'])
    with pytest.raises(ValueError):jm.factored(f)
    assert js.compatible_state(f,[0]*6)['status']=='NOMINAL MATERIAL MODEL REQUIRED'


@pytest.mark.parametrize('P',[0.,1000.])
def test_post_loss_Pe_is_self_equilibrated_without_second_shortening_loss_or_external_Nu(P):
    r=js.compatible_state(axial(),[P,0,0,0,0,0]);assert r['ready'],r
    assert r['prestress_reference']['maximum_Pe_error_N']<1e-6
    expected_extension=P/(4*20000.+80000.)
    assert r['node_displacements_mm'][5][0]==pytest.approx(expected_extension,abs=1e-9)
    expected=[1000+20000*expected_extension]*4+[-4000+80000*expected_extension]
    assert r['forces_N']==pytest.approx(expected,abs=1e-6)
    assert sum(r['forces_N'])==pytest.approx(P,abs=1e-6)
    assert r['checks']['energy_duality_relative']<1e-8 and r['checks']['compatibility_relative']<1e-8


def test_elastic_compatible_strains_match_the_independent_parallel_spring_solution():
    r=js.compatible_state(axial(prestressed=False),[4000.,0,0,0,0,0]);assert r['ready'],r
    assert r['forces_N'][:4]==pytest.approx([1000.]*4,abs=1e-6)
    assert r['forces_N'][4]==pytest.approx(0.,abs=1e-6)
    assert r['node_displacements_mm'][5][0]==pytest.approx(.05,abs=1e-8)
    total=np.array(r['total_extensions_mm']);elastic=np.array(r['elastic_extensions_mm']);plastic=np.array(r['plastic_extensions_mm'])
    np.testing.assert_allclose(total,elastic+plastic,atol=1e-8)


def test_known_Pe_over_ceiling_and_infeasible_actions_do_not_become_zero_results():
    m=axial();bad=m.bounds.copy();bad[0,1]=500.
    r=js.compatible_state(replace(m,bounds=bad),[0.]*6)
    assert not r['ready'] and r['status']=='PRESTRESS REFERENCE BLOCKED'
    u=js.compatible_state(axial(prestressed=False),[1e12,0,0,0,0,0])
    assert not u['ready'] and 'forces_N' not in u


def test_mesh_builder_retains_known_Pe_even_if_a_development_ceiling_is_inconsistent():
    args=arguments();bar=args['bars'][0]
    bar.update(kind='prestress',fpe_MPa=1000.,capacity_N=10.)
    bar['development']['transfer_factor']=1.
    model=jm.build(**args)
    ids=[i for i,k in enumerate(model.kinds) if k=='prestress']
    assert len(ids)==2 and all(model.initial[i]==pytest.approx(bar['area_mm2']*1000.) for i in ids)
    with patch.object(js,'_energy_state',side_effect=AssertionError('Inconsistent Pe reference must not be solved')):
        r=js.compatible_state(model,[0.]*6)
    assert not r['ready'] and r['status']=='PRESTRESS REFERENCE BLOCKED'


@pytest.mark.parametrize('value',[None,True,float('nan'),float('inf')])
def test_unknown_numeric_values_cannot_be_assumed_zero(value):
    with pytest.raises(ValueError):js.wrench([0,0,value,0,0,0])


def test_actual_common_web_has_no_A_default_that_resolves_the_given_intersection():
    bar={'label':'web DB16','kind':'ordinary','x_mm':50.,'y_mm':0.,'development':{'db_mm':16.}}
    r=audit(girder=box(-100,-750,100,750),bars=[bar],hoop={'cover_mm':40,'Diameter_mm':12},
        detail={'row_spacing_mm':100,'girder_ld_available_mm':1400,'slab_ldh_available_mm':200,'hook_inside_bend_mm':72,'hook_tail_mm':200},db_mm=12,web_width_mm=200)
    assert r['A_bend_minimum_mm']==84 and r['A_web_cover_maximum_mm']==108
    assert r['A_necessary_feasible_intervals_mm']==[]
    # Independent inequality: to clear bar x=50 by 14 mm, A<=72 or A>=128.
    assert 72<84<=108<128
    assert r['U_intersections'][0]['U_clear_gap_mm']==pytest.approx(-14.)
    assert r['no_silent_relocation']


def test_slab_equivalent_area_is_conserved_when_the_strip_count_is_not_an_integer():
    rows=[{'label':'top','x_mm':0.,'y_mm':100.,'area_mm2':1234.,'capacity_N':43210.},
          {'label':'bottom','x_mm':0.,'y_mm':10.,'area_mm2':987.,'capacity_N':12345.}]
    out=jm.expand_slab_layers({'deck_long_rebar_top_spacing_mm':200.,'deck_long_rebar_bottom_spacing_mm':150.},rows,left_mm=-625,right_mm=625)
    for prefix,row in zip(('top','bottom'),rows):
        selected=[b for b in out if b['label'].startswith(prefix)]
        assert sum(b['area_mm2'] for b in selected)==pytest.approx(row['area_mm2'])
        assert sum(b['capacity_N'] for b in selected)==pytest.approx(row['capacity_N'])
        assert len({b['x_mm'] for b in selected})>1


def test_new_research_settings_do_not_stale_production_or_persist_numerical_results():
    state=seed();rows=pd.DataFrame([bound_row()]);route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    old=fw.fingerprints(state,rows,route=route);r=ui.fingerprint(state,rows,route=route)
    state['project_metadata'][ui.KEY]={'enabled':True}
    assert fw.fingerprints(state,rows,route=route)==old and ui.fingerprint(state,rows,route=route)!=r
    state[fw.CACHE_KEY]={'joint37_research':{'numerical_force_witness_must_not_persist':123.}}
    text=project_to_json(project_from_session_state(state))
    assert 'numerical_force_witness_must_not_persist' not in text
    restored={};apply_project_to_session_state(project_from_json(text),restored)
    assert ui.settings(restored)=={'enabled':True}


def test_disabled_review_and_missing_source_never_invoke_the_solver():
    state=seed();rows=pd.DataFrame([bound_row()]);route=ap._beam_uls_strength_route_from_state(state,is_bridge=True,is_building=False)
    with patch.object(js,'limit',side_effect=AssertionError('Not authorized by current inputs')):
        assert not ui.calculate(state,rows,route=route,station=None)['enabled']
        state['project_metadata'][station.KEY]={'enabled':True}
        assert ui.calculate(state,rows,route=route,station=None)['status']=='MODEL BLOCKED'


@pytest.mark.parametrize('audit_hash,withheld',[('current',True),('stale',False)])
def test_current_geometry_conflicts_withhold_older_core_values_without_rerunning_or_mutating(audit_hash,withheld):
    from contextlib import nullcontext
    screen=MagicMock();screen.expander.side_effect=lambda *a,**k:nullcontext()
    item={'model_T_limit_Nmm':123e6,'status':'MODEL REVIEW ONLY'}
    stored={'fingerprint':'station','status':'MODEL REVIEW ONLY','source':{'member':'girder','case':'ULS','step':'Max','location_type':'Before','x_m':1.},
        'selection':{'selection':'Selected |Tu|','eligible':1},'source_actions':{},'transported_actions':{},
        'pure_torsion_without_prestress':deepcopy(item),'pure_torsion':deepcopy(item),'actual_five_actions':deepcopy(item),
        'closure_status':'UNESTABLISHED','u_dowel_anchorage':{},'longitudinal_inventory':[],'slab_mesh':[],
        'reference':{},'confirmation_status':{}}
    original=deepcopy(stored)
    joint={'status':'INPUT GEOMETRY REVIEW','fingerprint':audit_hash}
    with patch.object(station,'st',screen),patch.object(station,'settings',return_value={'enabled':True}), \
         patch.object(station,'fingerprint',return_value='station'),patch.object(ui,'fingerprint',return_value='current'), \
         patch.object(station,'figure',return_value=None),patch.object(js,'limit',side_effect=AssertionError('Read-only review')) as solve:
        station.render_result({},pd.DataFrame(),stored,route={},joint_review=joint)
    result_frame=screen.dataframe.call_args_list[1].args[0]
    assert result_frame['Model limit (kN·m)'].isna().all()==withheld
    assert all('WITHHELD' in s for s in result_frame['Status'])==withheld
    published=screen.json.call_args.args[0]
    assert ('pure_torsion' not in published)==withheld
    assert solve.call_count==0 and stored==original
