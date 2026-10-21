"""Reproduce the supplied stage curves and audit new criteria from a project.

Only input JSON is read. Runtime analysis results are never saved back into it.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

from streamlit.testing.v1 import AppTest


def run(project,output):
    root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(root)]
    from concrete_pmm_pro.serviceability import girder_deflect69 as engine
    from concrete_pmm_pro.visualization.girder_deflect69 import figure
    code=f'''from pathlib import Path
import streamlit as st
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui.analysis_page import build_girder_service_stress_basis_options,_analysis_mode_from_session,_girder_deflection_curve_rows,_girder_sls_span_length_from_session,_girder_deflection_summary_rows
from concrete_pmm_pro.serviceability import girder_deflect69 as engine
apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
mode=_analysis_mode_from_session()
bases=build_girder_service_stress_basis_options(st.session_state['section_geometry'],st.session_state['section_parameters'],member_type=mode.member_type)
source=_girder_deflection_curve_rows(basis_options=bases)
span=_girder_sls_span_length_from_session([])
st.session_state['qa_before']=_girder_deflection_summary_rows(source,limit_mm=span*1000/360)
st.session_state[engine.RESULT_KEY]=engine.calculate(st.session_state,source,span)
'''
    test=AppTest.from_string(code,default_timeout=120).run(timeout=120)
    assert not test.exception,[e.message for e in test.exception]
    result=test.session_state[engine.RESULT_KEY]
    before=test.session_state['qa_before']
    output.mkdir(parents=True,exist_ok=True)
    source=result['source_audit']
    peaks=source.groupby(['Stage','Curve'],sort=False)['Deflection (mm)'].agg(['min','max']).reset_index()
    for name,frame in [('Before_Legacy_Summary',before),('Current_Checks',result['summary']),('Generated_Source_Audit',source),('Source_Peaks',peaks)]:
        frame.to_csv(output/(name+'.csv'),index=False,encoding='utf-8-sig')
    plots={}
    for stage in ['Transfer stage','Construction stage','Service stage']:
        fig=figure(result,stage)
        assert list(fig.layout.xaxis.range)==[0,result['span_m']]
        plots[stage]={'trace_names':[t.name for t in fig.data],'x_range':list(fig.layout.xaxis.range),'limit_targets':fig.layout.meta['limit_applies_to']}
    verification={'milestone':engine.VERSION,'project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),
        'project_inputs_modified':False,'generated_stage_curve_formula_changes':False,
        'before':json.loads(before.to_json(orient='records')),'current':json.loads(result['summary'].to_json(orient='records')),
        'source_peaks':json.loads(peaks.to_json(orient='records')),'live_available':result['live_available'],
        'span_m':result['span_m'],'limit_mm':result['limit_mm'],'limit_basis':result['limit_basis'],
        'status':result['status'],'full_deflection_acceptance':False,'plots':plots,
        'known_model_qualifications':['Constant EI and midspan equivalent Pe retained','Stage-dependent Ec, Pe(x), end-section EI, creep/shrinkage and cracked stiffness are not certified by this preview']}
    (output/'Real_Project_Verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2,allow_nan=False))
    (output/'SLS_DEFLECT69_Audit.zip').write_bytes(engine.report_zip(result))
    print(peaks.to_string(index=False),flush=True)
    print(result['summary'].to_string(index=False),flush=True)
    print('Actual project: source curves preserved; status '+result['status'],flush=True)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.project,args.output)
