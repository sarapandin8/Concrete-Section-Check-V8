"""Local imported thickness is paired with force; no global thin-zone penalty."""
import numpy as np
import pytest

from concrete_pmm_pro.analysis import slab_punching78 as local
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from test_slab_punching78 import base


@pytest.mark.parametrize('h', [200., 250., 312.5, 350.])
def test_local_depth_and_capacity_match_the_same_native_point(base, h):
    f = base['rows']; first = f.iloc[0]
    mask = f.AreaElem.eq(first.AreaElem)&f.Joint.eq(first.Joint)
    f.loc[mask, 'Thickness (mm)'] = h
    g = base['geometry'].corners
    g.loc[g.AreaElem.eq(first.AreaElem)&g.Joint.eq(first.Joint), 'Thickness (mm)'] = h
    result = local.calculate(base)
    checked = result['rows'].loc[result['rows'].AreaElem.eq(first.AreaElem)&result['rows'].Joint.eq(first.Joint)]
    dv = max(.9*(h-64), .72*h)
    expected = .9*.063*np.sqrt(35/6.894757293)*6.894757293*dv
    np.testing.assert_allclose(checked['dv (mm)'], dv)
    np.testing.assert_allclose(checked['phi v dv (kN/m)'], expected)
    np.testing.assert_allclose(checked['Local D/C'], 5/expected)
    np.testing.assert_allclose(checked['Resistance thickness (mm)'], h)


def test_thick_region_is_not_given_200mm_resistance_and_variable_depth_remains_review(base):
    f = base['rows']; first = f.iloc[0]
    mask = f.AreaElem.eq(first.AreaElem)&f.Joint.eq(first.Joint)
    f.loc[mask, 'Thickness (mm)'] = 200.
    g = base['geometry'].corners
    g.loc[g.AreaElem.eq(first.AreaElem)&g.Joint.eq(first.Joint), 'Thickness (mm)'] = 200.
    r = local.calculate(base)
    thick = r['rows'].loc[r['rows']['Thickness (mm)'].eq(350.)]
    np.testing.assert_allclose(thick['dv (mm)'], 257.4)
    assert r['status']=='REVIEW' and r['variable_depth']
    assert not r['global_minimum_depth_applied']
    assert not r['full_deck_acceptance']


def test_invalid_local_depth_blocks_that_source_without_changing_other_resistance(base):
    f = base['rows']; first = f.iloc[0]
    mask = f.AreaElem.eq(first.AreaElem)&f.Joint.eq(first.Joint)
    f.loc[mask, 'Thickness (mm)'] = 50.
    r = local.calculate(base)
    bad = r['rows'].loc[r['rows'].AreaElem.eq(first.AreaElem)&r['rows'].Joint.eq(first.Joint)]
    assert bad['Local D/C'].isna().all() and not bad[INCLUDED].any()
    assert r['source_incomplete'] and r['status']=='REVIEW'
