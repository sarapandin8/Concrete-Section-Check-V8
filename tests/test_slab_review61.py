"""Numerical and safety invariants of read-only spatial review."""
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from concrete_pmm_pro.analysis import slab_shell56 as engine,slab_review61 as review
from concrete_pmm_pro.analysis.slab_code57 import strip_references,controlling_checks
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED,REASON
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope
from concrete_pmm_pro.visualization.slab_review61 import plan


def grid(*,spike=True,two_cases=False):
    corners=[];elements={}
    for x in range(4):
        for y in range(4):
            e=f'E{x}-{y}';p=np.array([[x,y,0],[x+1,y,0],[x+1,y+1,0],[x,y+1,0]],float);elements[e]=p
            for a in p:corners.append({'Area':'1','AreaElem':e,'Joint':f'J{int(a[0])}-{int(a[1])}',
                'X (m)':a[0],'Y (m)':a[1],'Z (m)':0.,'Thickness (mm)':350.})
    geo=SimpleNamespace(corners=pd.DataFrame(corners),elements=elements,parent_axes={'1':{'long':[1.,0.,0.]}})
    f=geo.corners.copy();f['OutputCase']='U2A';f['StepType']='Min';f['CaseType']='Combination'
    for a,v in zip(review.ACTIONS,[0.,0.,0.,1.,1.,0.,10.,0.]):f[a]=v
    if spike:f.loc[f.Joint.eq('J2-2'),'Vx']=1000.
    if two_cases:
        q=f.copy();q['OutputCase']='U1A';q['Vx']=10.;f=pd.concat([f,q],ignore_index=True)
    for raw,a in zip(['F11','F22','F12','M11','M22','M12','V13','V23'],review.ACTIONS):f[raw]=f[a]
    f[INCLUDED]=True;f[REASON]='';f['Bearing end-zone']=''
    steel=engine.SlabSteel(area=np.full(4,1340.),fy=np.full(4,390.),centre=np.array([64.,64.,48.,48.]),diameter=np.full(4,16.),spacing=np.full(4,150.),fc=35.)
    checks=engine.section_check(f['Thickness (mm)'].to_numpy(),f[review.ACTIONS[:3]].to_numpy(),f[review.ACTIONS[3:6]].to_numpy(),f[review.ACTIONS[6:]].to_numpy(),steel)
    refs=strip_references(f['Thickness (mm)'].to_numpy(),f[review.ACTIONS[:3]].to_numpy(),f[review.ACTIONS[3:6]].to_numpy(),steel)
    f=pd.concat([f,checks,refs],axis=1);f['Controlling check']=controlling_checks(f)
    return {'rows':f,'geometry':geo,'steel':steel,'fingerprint':'test-inputs','connections':{'lines':pd.DataFrame(columns=['Connection','X1 (m)','Y1 (m)','X2 (m)','Y2 (m)'])},'status':'Preview FAIL'}


def test_whole_joint_vector_is_omitted_only_in_flagged_case_and_source_is_unchanged():
    r=grid(two_cases=True);before=r['rows'].copy(deep=True);mask,ledger=review.peak_screen(r)
    assert mask.sum()==4 and set(ledger.OutputCase)=={'U2A'} and ledger.iloc[0]['Neighbour count']==8
    assert ledger.iloc[0]['Ratio to median']==100
    s=review.calculate(r);mapped=review.map_result(r,s,review.FILTERED)
    assert not mapped['rows'].loc[mask,INCLUDED].any()
    assert mapped['rows'].loc[mapped['rows'].OutputCase.eq('U1A'),INCLUDED].all()
    np.testing.assert_allclose(mapped['rows'][review.ACTIONS],before[review.ACTIONS]);pd.testing.assert_frame_equal(r['rows'],before)
    assert mapped['status']=='REVIEW REQUIRED' and r['status']=='Preview FAIL'


def test_single_element_peak_at_shared_joint_flags_all_records():
    r=grid(spike=False);indices=r['rows'].index[r['rows'].Joint.eq('J2-2')];r['rows'].loc[indices[0],'Vx']=1000.
    mask,ledger=review.peak_screen(r);assert mask.sum()==4 and ledger.iloc[0]['Magnitude (kN/m)']==1000


def test_no_recursive_trimming_of_new_secondary_peaks():
    r=grid();r['rows'].loc[r['rows'].Joint.eq('J2-3'),'Vx']=100.
    mask,_=review.peak_screen(r);assert set(r['rows'].loc[mask,'Joint'])=={'J2-2'}


def test_flat_cluster_and_smooth_gradient_are_not_isolated_peaks():
    r=grid(spike=False);r['rows']['Vx']=10+r['rows']['X (m)'];assert not review.peak_screen(r)[0].any()
    q=r['rows'];q['Vx']=10.;q.loc[q['X (m)'].between(1,3)&q['Y (m)'].between(1,3),'Vx']=1000.
    assert not review.peak_screen(r)[0].any()


def test_excluded_neighbours_cannot_supply_opposing_pair():
    r=grid();q=r['rows'];q[INCLUDED]=False;q.loc[(q['X (m)']>=2)&(q['Y (m)']>=2),INCLUDED]=True
    assert not review.peak_screen(r)[0].any()


def test_dc_and_steel_strength_do_not_change_peak_labels():
    a=grid();b=deepcopy(a)
    for c in b['rows']:
        if 'D/C' in c:b['rows'][c]=1e20
    b['steel'].fy[:]=1.;ma,la=review.peak_screen(a);mb,lb=review.peak_screen(b)
    pd.testing.assert_series_equal(ma,mb);pd.testing.assert_frame_equal(la,lb)


def test_quadrature_integrates_constant_and_linear_fields():
    p=np.array([[0,0],[4,0],[3,2],[0,2]],float);w=review.quad_weights(p)
    assert w.sum()==pytest.approx(7) and np.all(w>0) and w@p[:,0]==pytest.approx(37/3)
    np.testing.assert_allclose(review.quad_weights([[0,0],[2,0],[2,1],[0,1]]),.5)
    with pytest.raises(ValueError,match='Degenerate / folded'):review.quad_weights([[0,0],[1,1],[0,1],[1,0]])


def test_zone_means_preserve_case_signs_and_recalculate_with_minimum_thickness():
    r=grid(spike=False,two_cases=True);f=r['rows'];f['Mx']=20*(f['X (m)']-2)
    f.loc[f.OutputCase.eq('U1A'),'Mx']+=100;f['Ny']=2*f['X (m)']+f['Y (m)'];f['Thickness (mm)']=300+10*f['Y (m)']
    r['geometry'].corners['Thickness (mm)']=300+10*r['geometry'].corners['Y (m)']
    z,layout,_,source=review.zone_means(r,pd.Series(False,index=f.index));assert len(z)==8 and len(layout)==4
    for _,row in z.iterrows():
        y=row['Y (m)'];assert row['Sample area coverage']==pytest.approx(1) and row['Ny']==pytest.approx(4+y)
        assert row['Mx']==pytest.approx(0 if row.OutputCase=='U2A' else 100)
        assert row['Thickness (mm)']==pytest.approx(300+10*(y-.5))
        e=engine.section_check(np.array([row['Thickness (mm)']]),row[review.ACTIONS[:3]].to_numpy(float)[None,:],row[review.ACTIONS[3:6]].to_numpy(float)[None,:],row[review.ACTIONS[6:]].to_numpy(float)[None,:],r['steel'])
        assert row['N–M field D/C']==pytest.approx(e.iloc[0]['N–M field D/C']) and row['Status']=='REVIEW'
        assert bool(row['Sign change Mx'])==(row.OutputCase=='U2A')
    assert source[review.WEIGHT].sum()==pytest.approx(32)


def test_omitted_area_is_visible_and_raw_peak_actions_remain_available():
    s=review.calculate(grid());z=s['zone_rows'];assert z['Sample area coverage'].min()<1
    assert z['Sample area coverage'].max()<=1+1e-12 and s['source'][review.PEAK].sum()==4
    assert np.isfinite(s['source'].loc[s['source'][review.PEAK],'Vx']).all() and s['status']=='REVIEW REQUIRED'


def test_crossing_connection_blocks_zone_only():
    r=grid();r['connections']['lines']=pd.DataFrame([{'Connection':'Diaphragm','X1 (m)':2.,'Y1 (m)':0.,'X2 (m)':2.,'Y2 (m)':4.}]);s=review.calculate(r)
    assert 'crosses a girder / diaphragm' in s['zone_error'] and s['excluded_records']==4
    with pytest.raises(ValueError,match='crosses'):review.map_result(r,s,review.ZONES)
    assert review.map_result(r,s,review.FILTERED)['status']=='REVIEW REQUIRED'


def test_stale_study_never_replaces_nominal_results():
    r=grid();s=review.calculate(r);state={review.RESULT_KEY:s,engine.RESULT_KEY:r}
    assert review.current(state,r) is s and review.current(state,{**r,'fingerprint':'new'}) is None and state[engine.RESULT_KEY] is r


def test_zone_envelope_has_one_aggregate_per_case_and_full_geometry():
    r=grid();s=review.calculate(r);mapped=review.map_result(r,s,review.ZONES);env=element_envelope(mapped,view='N–M field')
    assert len(env)==4 and not env['Map incomplete'].any() and len(r['geometry'].corners)==64
    fig=plan(r,s,basis=review.ZONES,view='N–M field')
    assert fig.layout.meta['design_acceptance'] is False and any(t.name.startswith('Study max') for t in fig.data)


def test_missing_source_corner_cannot_be_hidden_by_zone_mean():
    r=grid(spike=False);r['rows']=r['rows'].iloc[1:].reset_index(drop=True);s=review.calculate(r)
    assert s['zone_rows']['Source incomplete'].any()
    env=element_envelope(review.map_result(r,s,review.ZONES),view='N–M field')
    assert env['Map incomplete'].any() and env.loc[env['Map incomplete'],'Map D/C'].isna().all()
