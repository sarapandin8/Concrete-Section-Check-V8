"""Regression tests for the independently audited N-M / V separation."""
import math

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope, view_column
from test_slab_shell56 import check, steel, model_state


def test_user_source_vector_equilibrates_without_the_withdrawn_shear_addition():
    # User JSON32 + native XLSX: element 1698-5, joint 826, U2A / Max.
    # Values are source actions, not rounded screenshots or mocked outputs.
    provided=np.array([math.pi*16**2/4/200*1000,*([math.pi*16**2/4/150*1000]*3)])
    s=engine.SlabSteel(provided,np.full(4,390.),np.array([64.,64.,48.,48.]),
                       np.full(4,16.),np.array([200.,150.,150.,150.]),35.)
    h=350.;n=(500.81,203.16,427.96);m=(444.6896,126.6933,55.9607)
    r=check(n=n,m=m,v=(2920.98,1283.56),reinforcement=s)
    a=r['Face depth (mm)'];zt,zb=h/2-a/2,-h/2+a/2
    # Hand force/moment equilibrium with the actual physical bar lever arms.
    qtop=(-1000*m[2]-zb*n[2])/(zt-zb);qbot=n[2]-qtop
    bottom_tension=(1000*m[0]+zt*(n[0]+abs(qtop)+abs(qbot))
                    -zt*abs(qtop)-zb*abs(qbot))/(zt+111.)
    assert r['Bottom longitudinal force (N/mm)']==pytest.approx(bottom_tension)
    assert r['Bottom longitudinal As required (mm²/m)']==pytest.approx(bottom_tension/(.9*390)*1000)
    assert r['N–M field D/C']==pytest.approx(5.1037097565,rel=1e-9)
    assert r['Bottom longitudinal As required (mm²/m)']==pytest.approx(6841.0782195,rel=1e-9)
    assert pd.isna(r['Shear D/C']) and pd.isna(r['Shear phiVc (kN/m)'])
    assert r['Combined N–M–V status']=='REVIEW'
    assert r['Equilibrium residual']<1e-12


def test_shear_does_not_change_any_selected_nm_stress_field_or_steel_requirement():
    n=(-100.,-60.,12.);m=(30.,-20.,7.)
    base=check(n=n,m=m)
    keys=['N–M field D/C','Face depth (mm)','Concrete D/C','q top (N/mm)',
          'q bottom (N/mm)','Cx top (N/mm)','Cy bottom (N/mm)']
    for g in engine.GROUPS:keys += [g+' force (N/mm)',g+' As required (mm²/m)']
    for v in ((2.,3.),(200.,-300.),(-2000.,3000.)):
        changed=check(n=n,m=m,v=v)
        np.testing.assert_array_equal(changed[keys].to_numpy(float),base[keys].to_numpy(float))
        assert changed['Combined N–M–V status']=='REVIEW'


def test_independent_shear_depth_is_not_artificially_shrunk_by_nm_face_search():
    # Strong compression needs a thick N-M face, but the separate section
    # screen is not allowed to inherit a fictitiously tiny core depth.
    s=steel()
    r=check(n=(-2500,-2500,0),v=(100,0),reinforcement=s)
    assert r['Face depth (mm)']>80
    assert r['Shear dv (mm)']==pytest.approx(.9*(350-64))
    # Independent AASHTO simplified beta=2 section component, SI conversion.
    vc=.0316*math.sqrt(35/6.894757293)*6.894757293*2*(.9*286)
    assert r['Shear phiVc (kN/m)']==pytest.approx(.9*vc)
    assert r['Shear D/C']==pytest.approx(100/(.9*vc))
    assert r['Combined N–M–V status']=='REVIEW'


def test_missing_shear_keeps_nm_available_but_can_never_return_combined_pass():
    r=check(n=(7000,0,0),v=(1,0),reinforcement=steel(area=10000,centres=(100,100,60,60)))
    assert r['N–M field status']=='Preview PASS'
    assert pd.isna(r['Shear D/C'])
    assert r['Status']=='REVIEW'
    assert r['Combined N–M–V status']=='REVIEW'


def test_nm_map_can_show_computed_fields_without_hiding_interaction_review():
    result=engine.calculate(model_state())
    assert view_column('N–M field')=='N–M field D/C'
    selected=element_envelope(result,view='N–M field')
    assert selected['Map D/C'].notna().all()
    assert selected['Combined N–M–V status'].eq('REVIEW').all()
    assert result['nm_governing']['N–M field D/C']==result['rows']['N–M field D/C'].max()
    assert not any('shear tie (N/mm)' in c for c in result['rows'])


def test_audit_version_invalidates_previous_field_results():
    state=model_state();result=engine.calculate(state)
    state[engine.RESULT_KEY]=result
    assert engine.current(state) is result
    result['fingerprint']='previous-version-fingerprint'
    assert engine.current(state) is None
