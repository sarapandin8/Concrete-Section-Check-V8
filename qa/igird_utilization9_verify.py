"""Reproduce threshold-pattern continuity with actual hypothetical QA solvers.

This is not a reconstruction or design approval of the user's PDF project.
Run from the project root: python qa/igird_utilization9_verify.py
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, 'tests')
import pandas as pd
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_case_review import controlling_result, summary_record
from concrete_pmm_pro.ui.igird_torsion_utilization import make_torsion_utilization_figure
from test_igird_uls7_concurrent_vt import ready_state
from test_igird_uls6_torsion_general_procedure import _demand, _route

out = Path('qa/evidence/igird_utilization9/station_patterns')
out.mkdir(parents=True, exist_ok=True)
records = []
for member, small in [('Left Exterior Girder', {12: 20., 13: 17., 14: 23., 20: .02}),
                      ('Interior Girder 2', {5: 1.58})]:
    state = ready_state()
    source_rows = []
    for case, factor in [('ULS1', 1.), ('ULS2', .65)]:
        for x in range(21):
            tu = small.get(x, 350. * math.sin((x+1)*.2)) * factor
            if x == 0:
                tu = 0.
            row = _demand(x=x, tu=tu, vu=400.*factor, mux=500.).iloc[0].to_dict()
            row['Case Name'] = member+' / '+case
            source_rows.append(row)
    source = pd.DataFrame(source_rows)
    result = mr.calculate_member(state, source, check_name='Torsion', route=_route())
    assert not result.get('error')
    checks, diagram = result['torsion_check_df'], result['torsion_diagram_capacity_df']
    original = deepcopy(result)
    before = summary_record(controlling_result(checks, 'Torsion'))
    with patch.object(ap, '_beam_uls_igird_torsion_result_for_row', side_effect=AssertionError('Review solver')):
        for case in (member+' / ULS1', member+' / ULS2', None):
            selected = source if case is None else source.loc[source['Case Name'].eq(case)]
            checked = checks if case is None else checks.loc[checks['Case'].eq(case)]
            stored = diagram if case is None else diagram.loc[diagram['Case'].eq(case)]
            fig = make_torsion_utilization_figure(selected, checked, diagram=stored,
                source_context_df=source, member_name=member, case=case,
                code_label='QA hypothetical inputs · AASHTO LRFD 9th Edition', span_m=20.)
            audit = pd.DataFrame(fig.layout.meta['torsion_utilization_audit'])
            assert audit['Availability'].eq('AVAILABLE').all(), audit.loc[audit.Availability.eq('UNAVAILABLE')].to_dict('records')
            assert not audit['Curve gap'].any()
            for x in small:
                at_x = audit.loc[audit['Station x (m)'].eq(x)]
                assert at_x['Threshold status'].eq('BELOW THRESHOLD').all()
                assert at_x['Original maximum check D/C'].isna().all()
                assert at_x['Strength utilization |Tu|/phiTn'].gt(0).all()
            stem = member.lower().replace(' ', '_')+'_'+('all_cases' if case is None else case.rsplit(' / ',1)[1].lower())
            fig.write_json(out/(stem+'.plotly.json'))
            fig.write_image(out/(stem+'.png'), width=1440, height=560, scale=2)
            audit.to_csv(out/(stem+'.station_audit.csv'), index=False)
        unknown = diagram.copy(deep=True)
        unknown.loc[unknown['Governing x'].eq('9.000 m'), 'φTn kN-m'] = float('nan')
        fig = make_torsion_utilization_figure(source, checks, diagram=unknown,
            member_name=member, code_label='QA hypothetical missing-cache test', span_m=20.)
        blue = next(trace for trace in fig.data if trace.name == 'Strength |Tu|/φTn')
        assert math.isnan(blue.y[list(blue.x).index(9.)]) and blue.connectgaps is False
        assert fig.layout.meta['unavailable_capacity'][0]['x_m'] == 9.
        stem = member.lower().replace(' ', '_')+'_missing_capacity'
        fig.write_image(out/(stem+'.png'), width=1440, height=560, scale=2)
        fig.write_json(out/(stem+'.plotly.json'))
    for key, value in result.items():
        if isinstance(value, pd.DataFrame):
            pd.testing.assert_frame_equal(value, original[key], check_exact=True)
    assert summary_record(controlling_result(checks, 'Torsion')) == before
    prefix = member.lower().replace(' ', '_')
    source.to_csv(out/(prefix+'.source_actions.csv'), index=False)
    checks.to_csv(out/(prefix+'.original_checks.csv'), index=False)
    diagram.to_csv(out/(prefix+'.cached_diagram.csv'), index=False)
    records.append({'member': member, 'cases': 2, 'stations_per_case': 21,
        'below_threshold_stations': list(small), 'original_control': before,
        'strength_ratios_continuous': True, 'missing_capacity_gap_retained': True,
        'original_results_preserved': True, 'review_solver_calls': 0})
evidence = {'release': 'IGIRDER.UTILIZATION9', 'status': 'PASS',
    'scope': 'Hypothetical calculated QA model, not the user project', 'checks': records,
    'export_size_px': [2880, 1120]}
(out/'station_pattern_verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(evidence, ensure_ascii=False))
