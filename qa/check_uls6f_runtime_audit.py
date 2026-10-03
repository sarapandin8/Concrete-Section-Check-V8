"""Check the running production Torsion renderer's stored/chart evidence."""
import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.ui.analysis_page import _make_beam_uls_torsion_capacity_figure
at=AppTest.from_file(str(ROOT/'qa/igird_uls6f_runtime.py'),default_timeout=40).run()
assert not at.exception
next(b for b in at.button if b.label=='Calculate Torsion').click().run()
assert not at.exception
entry=at.session_state['_beam_girder_uls_manual_calculation_cache']['Torsion']
active=at.session_state['beam_uls_loads_table'];df=entry['torsion_check_df']
fig=_make_beam_uls_torsion_capacity_figure(active,df,code_label='AASHTO LRFD 9th Edition',boundary_capacity_df=entry['torsion_boundary_capacity_df'])
trace=next(t for t in fig.data if t.name=='±φTn' and t.showlegend is not False)
plot={float(x):float(y) for x,y in zip(trace.x,trace.y)}
audit={float(str(r['Governing x']).split()[0]):float(r['φTn kN-m']) for r in df.to_dict('records')}
assert list(sorted(plot))==[float(x) for x in range(21)]
assert all(math.isfinite(v) and math.isclose(v,audit[x],rel_tol=1e-12) for x,v in plot.items())
assert entry['torsion_coverage_summary']['covered_stations']==21
ready={'stations':len(plot),'all_finite':True,'chart_equals_stored_audit':True,'phiTn_kNm_by_x':plot,'coverage':entry['torsion_coverage_summary']}
next(c for c in at.checkbox if c.label=='QA: make Z3 not-ready').check().run()
next(b for b in at.button if b.label=='Calculate Torsion').click().run()
assert not at.exception
entry=at.session_state['_beam_girder_uls_manual_calculation_cache']['Torsion']
fig=_make_beam_uls_torsion_capacity_figure(active,entry['torsion_check_df'],code_label='AASHTO LRFD 9th Edition',boundary_capacity_df=entry['torsion_boundary_capacity_df'])
trace=next(t for t in fig.data if t.name=='±φTn' and t.showlegend is not False)
gaps=[float(x) for x,y in zip(trace.x,trace.y) if not math.isfinite(float(y))]
assert 10.0 in gaps and all(6.0<=x<=14.0 for x in gaps)
result={'ready':ready,'missing_zone':{'real_gap_stations':gaps,'coverage':entry['torsion_coverage_summary']},'exceptions':0}
(ROOT/'qa/uls6f_runtime_audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print('ULS6F runtime chart/audit: 21 finite physical stations; values equal; deliberate gap preserved; zero app exceptions.')
