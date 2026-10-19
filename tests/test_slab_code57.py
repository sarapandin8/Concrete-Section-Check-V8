"""Independent RC-strip numbers and guards against replacing coupled demand."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_code57 import (
    strip_references, controlling_checks, check_breakdown, source_check_ledger,
    FLEXURE_VIEW, MINIMUM_VIEW,
)
from concrete_pmm_pro.visualization.slab_shell56 import element_envelope, plan_figure
from concrete_pmm_pro.io.slab_shell_import import BANK_KEY
from test_slab_shell56 import steel, model_state


def reference(n=(0.,0.,0.), m=(0.,0.,0.), reinforcement=None, h=350.):
    return strip_references(np.array([h]),np.array([n]),np.array([m]),reinforcement or steel()).iloc[0]


@pytest.mark.parametrize('direction,index',[(0,1),(1,3)])
@pytest.mark.parametrize('sign',[-1,1])
def test_rectangular_strip_matches_independent_nominal_force_couple(direction,index,sign):
    m=np.zeros(3);m[direction]=40*sign
    row=reference(m=m)
    chosen=index if sign>0 else index-1
    group=engine.GROUPS[chosen]
    # Independently evaluate the singly reinforced 1 m section in SI units.
    depth=350-(64 if direction==0 else 48)
    a=1000*390/(.85*35*1000)
    nominal=1000*390*(depth-a/2)/1e6
    assert row[group+' reference phiMn (kN·m/m)']==pytest.approx(.9*nominal)
    assert row[group+' reference D/C']==pytest.approx(40/(.9*nominal))
    assert row[group+' minimum sufficient D/C']==pytest.approx(1.33*40/(.9*nominal))
    assert row['Minimum sufficient screen status']=='Sufficient screen PASS'


def test_actual_four_covers_give_different_top_bottom_code_capacities():
    s=steel(centres=(60.,80.,45.,55.))
    row=reference(reinforcement=s)
    assert row['Top longitudinal reference phiMn (kN·m/m)']>row['Bottom longitudinal reference phiMn (kN·m/m)']
    assert row['Top transverse reference phiMn (kN·m/m)']>row['Bottom transverse reference phiMn (kN·m/m)']


@pytest.mark.parametrize('n',[(.001,0,0),(-.001,0,0),(0,.001,0),(0,0,-.001)])
def test_any_nonzero_membrane_component_keeps_reference_unavailable(n):
    row=reference(n=n,m=(1,0,0))
    assert not row['Code reference membrane-free']
    assert pd.isna(row['Code flexure reference D/C'])
    assert pd.isna(row['Minimum sufficient screen D/C'])
    assert row['Minimum sufficient screen status']=='REVIEW'
    assert 'coupled' in row['Code reference reason']
    assert row['Bottom longitudinal reference phiMn (kN·m/m)']>0  # independent N=0 property only


def test_failed_stronger_minimum_branch_is_review_not_a_code_failure():
    r=reference(m=(90,0,0))
    assert r['Code flexure reference D/C']<1
    assert r['Minimum sufficient screen D/C']>1
    assert r['Minimum sufficient screen status']=='REVIEW'
    assert 'lesser Mcr' in r['Code reference reason']


def test_overreinforced_mat_cannot_use_fixed_phi_nine_as_qualified_capacity():
    row=reference(m=(40,0,0),reinforcement=steel(area=20000))
    assert pd.isna(row['Bottom longitudinal reference phiMn (kN·m/m)'])
    assert pd.isna(row['Code flexure reference D/C'])
    assert row['Code flexure reference status']=='REVIEW'


def test_high_strength_uses_ksi_stress_block_breakpoints():
    s=steel();s=engine.SlabSteel(s.area,s.fy,s.centre,s.diameter,s.spacing,12*6.894757293)
    row=reference(m=(10,0,0),reinforcement=s)
    alpha=.85-.02*(12-10)
    a=1000*390/(alpha*s.fc*1000)
    expected=.9*1000*390*(286-a/2)/1e6
    assert row['Bottom longitudinal reference phiMn (kN·m/m)']==pytest.approx(expected)


def test_wood_armer_is_applied_to_the_concurrent_moment_triad():
    r=reference(m=(10,-20,-7))
    for group,demand in zip(engine.GROUPS,[0,17,27,0]):
        assert r[group+' reference D/C']==pytest.approx(demand/r[group+' reference phiMn (kN·m/m)'])


def test_reference_computation_never_mutates_actions_or_provided_steel():
    s=steel();n=np.zeros((2,3));m=np.array([[10,20,7],[50,-30,-12.]])
    before=(n.copy(),m.copy(),s.area.copy())
    strip_references(np.full(2,350.),n,m,s)
    for old,new in zip(before,(n,m,s.area)):np.testing.assert_array_equal(old,new)


def test_each_check_keeps_own_source_and_counts_unique_elements():
    r=engine.calculate(model_state());rows=r['rows'].copy()
    rows['Concrete D/C']=.2;rows['Shear D/C']=.1
    rows.loc[0,'Concrete D/C']=8.;rows.loc[1,'Shear D/C']=9.
    rows.loc[2,'Shear D/C']=np.nan
    rows.loc[3,'Shear D/C']=5.  # same element is not counted twice
    summary=check_breakdown(rows).set_index('Check')
    assert summary.loc['Concrete compression','Peak D/C']==8.
    assert summary.loc['One-way shear','Peak D/C']==9.
    assert summary.loc['One-way shear','AreaElem']==rows.loc[1,'AreaElem']
    assert summary.loc['One-way shear','Exceeded elements']==1
    assert summary.loc['One-way shear','Review elements']==1
    assert controlling_checks(rows)[0]=='Concrete compression'
    assert controlling_checks(rows)[1]=='One-way shear'
    ledger=source_check_ledger(rows.loc[2]).set_index('Check')
    assert ledger.loc['One-way shear','Status']=='REVIEW'
    rows['Shear D/C']=np.nan
    summary=check_breakdown(rows).set_index('Check')
    assert summary.loc['One-way shear','Status']=='REVIEW' and pd.isna(summary.loc['One-way shear','Peak D/C'])


def test_all_membrane_loaded_elements_are_grey_in_code_reference_views():
    r=engine.calculate(model_state())
    for view in (FLEXURE_VIEW,MINIMUM_VIEW):
        envelope=element_envelope(r,view=view)
        assert envelope['Map D/C'].isna().all()
        figure=plan_figure(r,view=view)
        assert any(t.name=='Review / missing' for t in figure.data)
        assert not any(str(t.name).startswith('Gov.') for t in figure.data)


def test_reference_only_data_does_not_inflate_main_as_or_field_dc():
    r=engine.calculate(model_state())
    rows=r['rows'];s=r['steel']
    independent=engine.section_check(rows['Thickness (mm)'].to_numpy(),rows[['Nx','Ny','Nxy']].to_numpy(),
        rows[['Mx','My','Mxy']].to_numpy(),rows[['Vx','Vy']].to_numpy(),s)
    np.testing.assert_allclose(rows['Field D/C'],independent['Field D/C'])
    for group in engine.GROUPS:
        np.testing.assert_allclose(rows[group+' As required (mm²/m)'],independent[group+' As required (mm²/m)'])
    assert len(r['check_summary'])==8
    assert r['reference_counts']=={'REVIEW':r['source_rows']}


def test_zero_actions_identify_shrinkage_without_calling_it_a_steel_strength_failure():
    state=model_state()
    state[BANK_KEY].tables['forces'][['F11','F22','F12','M11','M22','M12','V13','V23']]=0.
    for face in ('top','bottom'):
        state['section_parameters'][f'deck_long_rebar_{face}_diameter_mm']=8.
        state['section_parameters'][f'deck_long_rebar_{face}_spacing_mm']=100.
        state['beam_girder_interface_shear_settings']['dowel_connection']['slab_transverse_mesh'][face].update(Diameter_mm=8.,Spacing_mm=100.)
    r=engine.calculate(state)
    assert set(r['rows']['Controlling check'])=={'Shrinkage minimum'}
    table=r['check_summary'].set_index('Check')
    assert table.loc['Bottom longitudinal','Peak D/C']==0.
    assert table.loc['Shrinkage minimum','Peak D/C']>0.
