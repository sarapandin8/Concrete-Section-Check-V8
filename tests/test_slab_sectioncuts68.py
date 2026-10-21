"""Independent analytic checks of selected signed native-result line cuts."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.analysis.slab_sectioncuts68 import CutSource, ACTIONS
from test_slab_aashto63 import cut_fixture


def case(name='U1A', step=1.):
    return {'OutputCase':name, 'StepType':'Max', 'StepNum':step}


def test_signed_bilinear_line_integral_matches_closed_form_for_each_case():
    rows, geometry, _ = cut_fixture()
    # f(x,y)=j+2x+4y+3xy integrates to j+.8+3.12 at x=.4, y=.2..1.
    for j, action in enumerate(ACTIONS):
        rows[action] += 3*rows['X (m)']*rows['Y (m)']
    source = CutSource(rows, geometry)
    for name, offset in [('U1A',0.), ('U2A',100.)]:
        result = source.integrate('Longitudinal', .4, .2, 1., case(name))
        assert result['Source coverage'] and result['Width (m)']==pytest.approx(.8)
        for j, action in enumerate(ACTIONS):
            expected = offset+j+.8+5.2*.6
            assert result[action]==pytest.approx(expected)
            assert result[action+' integral']==pytest.approx(.8*expected)
        assert result['Status']=='REVIEW'


def test_absolute_integral_discloses_signed_cancellation_instead_of_peak_smoothing():
    rows, geometry, _ = cut_fixture()
    rows['Vx'] = 2*rows['Y (m)']-1
    result = CutSource(rows, geometry).integrate('Longitudinal', .5, 0., 1., case())
    assert result['Vx integral']==pytest.approx(0.)
    assert result['Vx absolute integral']==pytest.approx(.5)
    assert result['Status']=='REVIEW'


def two_cells(overlap=False):
    rows, geometry, supports = cut_fixture()
    other = rows.copy()
    other.AreaElem='B-1'
    other[ACTIONS] += 1000.
    other['X (m)'] += 0. if overlap else 1.
    corners = geometry.corners.copy()
    corners.AreaElem='B-1'
    corners['X (m)'] += 0. if overlap else 1.
    geometry.corners=pd.concat((geometry.corners,corners),ignore_index=True)
    return pd.concat((rows,other),ignore_index=True), geometry, supports


def test_both_sides_of_shared_fe_edge_keep_discontinuity_without_double_counting():
    rows, geometry, _ = two_cells()
    source = CutSource(rows, geometry)
    minus=source.integrate('Longitudinal',1.,0.,1.,case(),side='Minus')
    plus=source.integrate('Longitudinal',1.,0.,1.,case(),side='Plus')
    assert minus['Source coverage'] and plus['Source coverage']
    assert minus['Nx']==pytest.approx(4.)
    assert plus['Nx']==pytest.approx(1002.)
    assert minus['Available width (m)']==plus['Available width (m)']==1.


@pytest.mark.parametrize('mode', ['excluded','missing','nonfinite'])
def test_unavailable_nonzero_weight_source_invalidates_whole_cut(mode):
    rows, geometry, _=cut_fixture()
    mask=rows.Joint.eq('a')&rows.OutputCase.eq('U1A')
    if mode=='excluded':
        rows.loc[mask,INCLUDED]=False
        rows.loc[mask,ACTIONS]=1e12
    elif mode=='missing':
        rows=rows.loc[~mask]
    else:
        rows.loc[mask,'Vx']=np.nan
    result=CutSource(rows,geometry).integrate('Longitudinal',.4,0.,1.,case())
    assert result['Geometric coverage'] and not result['Source coverage']
    assert all(np.isnan(result[c]) for c in ACTIONS)
    assert all(np.isnan(result[c+' integral']) for c in ACTIONS)


def test_zero_weight_excluded_corners_do_not_invalidate_real_boundary_cut():
    rows,geometry,_=cut_fixture()
    rows.loc[rows['X (m)'].eq(1.),INCLUDED]=False
    rows.loc[~rows[INCLUDED],ACTIONS]=np.nan
    source=CutSource(rows,geometry)
    result=source.integrate('Longitudinal',0.,0.,1.,case(),side='Plus')
    assert result['Source coverage'] and result['Nx']==pytest.approx(2.)
    absent_side=source.integrate('Longitudinal',0.,0.,1.,case(),side='Minus')
    assert not absent_side['Source coverage'] and np.isnan(absent_side['Nx'])


def test_partial_or_overlapping_geometry_cannot_be_normalized_to_numeric_capacity():
    rows,geometry,_=cut_fixture()
    partial=CutSource(rows,geometry).integrate('Longitudinal',.4,0.,1.2,case())
    assert partial['Available width (m)']==pytest.approx(1.)
    assert not partial['Source coverage'] and np.isnan(partial['Nx'])
    rows,geometry,_=two_cells(overlap=True)
    overlapping=CutSource(rows,geometry).integrate('Longitudinal',.4,0.,1.,case())
    assert not overlapping['Geometric coverage'] and np.isnan(overlapping['Nx'])


def test_rotated_geometry_preserves_physical_direction_and_does_not_mutate_inputs():
    rows,geometry,supports=cut_fixture()
    before=rows.copy(deep=True)
    reference=CutSource(rows,geometry).integrate('Transverse',.5,0.,1.,case())
    angle=.37
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    for frame in (rows,geometry.corners):
        frame[['X (m)','Y (m)']]=frame[['X (m)','Y (m)']].to_numpy()@rotation.T
    geometry.parent_axes['A']['long']=[*rotation[:,0],0.]
    result=CutSource(rows,geometry).integrate('Transverse',.5,0.,1.,case())
    for action in ACTIONS:
        assert result[action]==pytest.approx(reference[action])
    pd.testing.assert_frame_equal(rows[ACTIONS],before[ACTIONS])


def test_window_stops_at_physical_contact_boundaries_and_reports_actual_width():
    rows,geometry,supports=cut_fixture()
    source=CutSource(rows,geometry)
    inside=source.window('Longitudinal',[.5,.1],supports)
    assert inside['reaction_footprint'] and inside['a']==0. and inside['b']==.3
    outside=source.window('Longitudinal',[.5,.3],supports)
    assert not outside['reaction_footprint'] and outside['a']==.3
    assert outside['b']==pytest.approx(.8)
    clipped=source.window('Longitudinal',[.5,.9],supports)
    assert clipped['b']==1. and clipped['b']-clipped['a']==pytest.approx(.6)
    # A cut along the actual contact face belongs to the face, not the
    # contact interior, consistently with native/face scope classification.
    face=source.window('Transverse',[.5,.3],supports)
    assert not face['reaction_footprint']


def test_case_step_integrity_duplicate_keys_and_unsupported_cells_are_explicit():
    rows,geometry,_=cut_fixture()
    rows.StepNum=np.nan
    source=CutSource(rows,geometry)
    assert source.integrate('Longitudinal',.5,0.,1.,case(step=np.nan))['Source coverage']
    assert not source.integrate('Longitudinal',.5,0.,1.,case('missing',step=np.nan))['Source coverage']
    duplicate=pd.concat((rows,rows.iloc[[0]]),ignore_index=True)
    with pytest.raises(ValueError,match='unique'):
        CutSource(duplicate,geometry).integrate('Longitudinal',.5,0.,1.,case(step=np.nan))
    skew=deepcopy(geometry)
    skew.corners.loc[0,'X (m)']=.1
    with pytest.raises(ValueError,match='rectangular'):
        CutSource(rows,skew)
