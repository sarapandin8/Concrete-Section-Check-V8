"""Verify the supplied project, arithmetic and read-only actual app review."""
from copy import deepcopy
from contextlib import ExitStack
import argparse
import hashlib
import json
import logging
import math
from pathlib import Path
import pickle
import sys
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import apply_project_to_session_state, project_from_json
from concrete_pmm_pro.io.girder_load_bank import ACTIVE_KEY, BANK_KEY, save_active
from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
from concrete_pmm_pro.ui.igird_case_review import ALL_CASES
from concrete_pmm_pro.ui.igird_vt_workspace import make_overview_figure

parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
parser.add_argument('--baseline', required=True)
parser.add_argument('--seed', required=True)
args = parser.parse_args()
assert not Path(args.seed).resolve().is_relative_to(ROOT)
logging.getLogger('streamlit').setLevel(logging.ERROR)
raw = Path(args.project).read_bytes()
state = {}
apply_project_to_session_state(project_from_json(raw.decode()), state)
before = pickle.loads(Path(args.baseline).read_bytes())
route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
inputs = mr.member_inputs(state)
results = {}
records = []
comparisons = 0
max_error = 0.
for member, rows in inputs.items():
    pd.testing.assert_frame_equal(rows, before['inputs'][member])
    result = mr.calculate_member(state, rows, check_name='Shear + Torsion', route=route)
    results[member] = result
    for key, value in result.items():
        if isinstance(value, pd.DataFrame):
            pd.testing.assert_frame_equal(value, before['results'][member][key], check_exact=True)
    frame = result['combined_vt_df']
    for _, r in frame.iterrows():
        phi, fy, dv, bv, fc = (r[k] for k in ('φ','fy MPa','dv mm','bw mm',"f'c MPa"))
        eps = max(0., min(.006, r['εs raw']))
        beta = 4.8/(1+750*eps)
        theta = 29+3500*eps
        cot = 1/math.tan(math.radians(theta))
        vu = abs(r['Vu kN'])*1000
        tu = abs(r['Tu kN-m'])*1e6 if r['Threshold status']=='DESIGN REQUIRED' else 0.
        at = tu/(phi*2*r['Ao mm2']*fy*cot) if tu else 0.
        vc = .0316*beta*math.sqrt(fc/6.894757293168)*(bv/25.4)*(dv/25.4)*4448.2216152605
        avmin = .0316*math.sqrt(fc/6.894757293168)*(bv/25.4)/(fy/6.894757293168)*25.4
        av = max(0., (vu/phi-vc)/(fy*dv*cot))
        req = max(av,avmin)+2*at
        provided = r['Provided transverse mm2/mm']
        vs = min(max(0.,provided-2*at)*fy*dv*cot,vu/phi)
        torsion_force = .45*r['ph mm']*tu/(2*r['Ao mm2']*phi) if tu else 0.
        force = max(0., abs(r['Mu kN-m'])*1e6/(phi*dv)-.5*r['Nu app kN']*1000/phi
            +cot*math.hypot(vu/phi-.5*vs, torsion_force))
        expected = {'β':beta,'θ deg':theta,'Vc kN':vc/1000,'At torsion req mm2/mm':at,
            'Combined transverse req mm2/mm':req,'Vs used kN':vs/1000,
            'Longitudinal required kN':force/1000,
            'Longitudinal D/C value':force/((r['As fy kN']+r['Aps fps kN'])*1000),
            'Transverse D/C value':req/provided,'Stress D/C value':vu/(phi*.25*fc*bv*dv),
            'Spacing D/C':r['Spacing mm']/r['s max mm']}
        for key, value in expected.items():
            error = abs(value-r[key])/max(1.,abs(value))
            max_error = max(max_error,error)
            assert math.isclose(value,r[key],rel_tol=1e-8,abs_tol=1e-8), (member,key,value,r[key])
            comparisons += 1
    fig = make_overview_figure(rows,frame,check_name='Shear + Torsion',code_label='AASHTO',span_m=20.)
    overview = next(t for t in fig.data if t.name=='Max D/C')
    for x, y in zip(overview.x, overview.y):
        local = frame[frame['Governing x'].eq(f'{x:.3f} m')]
        assert math.isclose(y,local['Overall D/C value'].max(),rel_tol=1e-12)
    gov = ap._beam_uls_governing_combined_vt_row(frame)
    records.append({'member':member,'rows':len(frame),'overview_points':len(overview.x),
        'statuses':frame.Status.value_counts().to_dict(),'governing':{k:gov[k] for k in
        ('Governing x','Zone','Spacing mm','Overall D/C value','Transverse D/C value','Longitudinal D/C value')},
        'source_review_rows':int(frame['Source coupling'].eq('ENVELOPE — REVIEW').sum())})
    print(member+': exact baseline equality and independent arithmetic passed.',flush=True)
save_active(state)
state[mr.CACHE_KEY] = {n:{'Shear + Torsion':{'input_hash':mr.result_hash(state,rows,
    check_name='Shear + Torsion',route=route),'result':results[n]}} for n,rows in inputs.items()}
active = state[ACTIVE_KEY]
ap._beam_uls_store_manual_result(state,'Shear + Torsion',
    input_hash=mr.result_hash(state,inputs[active],check_name='Shear + Torsion',route=route),result=results[active])
state['_nav_active_workspace'] = 'Analysis'
state['beam_girder_uls_lazy_check'] = 'Shear + Torsion'
at = AppTest.from_file(str(ROOT/'app.py'),default_timeout=120)
for k,v in state.items(): at.session_state[k] = deepcopy(v)
figures = []
render = ap._render_beam_uls_browser_plotly_figure
def capture(fig, **kwargs):
    figures.append(deepcopy(fig))
    return render(fig, **kwargs)
def run():
    figures.clear()
    at.run(timeout=120)
    assert not at.exception, [e.message for e in at.exception]
    components = [f for f in figures if any(t.name=='Spacing D/C' for t in f.data)]
    assert len(components)==2, [f.layout.title.text for f in figures]
    for fig in components:
        assert any(t.name=='Shear limit D/C' for t in fig.data)
        assert not any('Veff' in str(t.name) for t in fig.data)
def selector(member):
    return next(s for s in at.selectbox if s.label=='Load case to review — '+member)
with ExitStack() as stack:
    stack.enter_context(patch.object(ap,'_render_beam_uls_browser_plotly_figure',capture))
    for owner,name in ((mr,'calculate_member'),(ap,'_beam_uls_calculate_selected_check')):
        stack.enter_context(patch.object(owner,name,side_effect=AssertionError('Review cannot calculate')))
    run()
    keys = (ACTIVE_KEY,BANK_KEY,'beam_uls_loads_table',mr.CACHE_KEY,ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY)
    original = {k:pickle.dumps(at.session_state[k]) for k in keys}
    for member in inputs: selector(member).set_value(ALL_CASES)
    run()
    for member in inputs:
        selector(member).set_value(str(inputs[member]['Case Name'].iloc[0]))
    run()
    for member in inputs: selector(member).set_value(ALL_CASES)
    run()
    for k,v in original.items(): assert pickle.dumps(at.session_state[k])==v,k
buttons = {b.key for b in at.button if b.key}
buttons.update(item.proto.id.split('-',2)[-1] for widget in ('download_button','file_uploader') for item in at.get(widget))
checkpoint = {k:v for k,v in at.session_state.filtered_state.items() if k not in buttons and '__nav_button__' not in k}
Path(args.seed).write_bytes(pickle.dumps(checkpoint))
assert Path(args.project).read_bytes()==raw
out = ROOT/'qa/evidence/igird_vtchart16'
out.mkdir(parents=True,exist_ok=True)
(out/'project_app_checks.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest(),
    'baseline_result_frames_exactly_equal':True,'members':records,'arithmetic_comparisons':comparisons,
    'maximum_scaled_arithmetic_error':max_error,'arithmetic_scope':'Independent substitution with stored geometry, strain and developed resistance; supplied zero-Vp project only.',
    'app_review_modes':['automatic','all','single','all'],'review_solver_calls':0,
    'inputs_and_result_caches_unchanged':True,'source_json_unchanged':True},indent=2)+'\n')
print('Actual app: automatic/all/single review passed without solver calls or input/cache mutations.',flush=True)
