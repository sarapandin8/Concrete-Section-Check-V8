"""Reproduce real project precast stages and both native CSI SLS envelopes."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
from streamlit.testing.v1 import AppTest


def run(project, workbook, output):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from concrete_pmm_pro.serviceability import girder_deflect70 as engine
    from concrete_pmm_pro.visualization.girder_deflect70 import figure
    code = f'''from pathlib import Path
import streamlit as st
from concrete_pmm_pro.io.project_io import project_from_json,apply_project_to_session_state
from concrete_pmm_pro.ui.analysis_page import build_girder_service_stress_basis_options,_analysis_mode_from_session,_girder_deflection_curve_rows,_girder_sls_span_length_from_session
from concrete_pmm_pro.io.girder_deflect70 import parse_workbook,BANK_KEY
from concrete_pmm_pro.serviceability import girder_deflect70 as engine
apply_project_to_session_state(project_from_json(Path({str(project.resolve())!r}).read_text()),st.session_state)
mode=_analysis_mode_from_session()
bases=build_girder_service_stress_basis_options(st.session_state['section_geometry'],st.session_state['section_parameters'],member_type=mode.member_type)
source=_girder_deflection_curve_rows(basis_options=bases)
span=_girder_sls_span_length_from_session([])
path=Path({str(workbook.resolve())!r})
st.session_state[BANK_KEY]=parse_workbook(path.read_bytes(),path.name)
st.session_state[engine.RESULT_KEY]=engine.calculate(st.session_state,source,span)
'''
    app = AppTest.from_string(code, default_timeout=120).run(timeout=120)
    assert not app.exception, [e.message for e in app.exception]
    result = app.session_state[engine.RESULT_KEY]
    service = result['summary'].loc[lambda f: f.Check.eq('Imported SLS envelope |WebTop Vert|')]
    np.testing.assert_allclose(service['Demand (mm)'], [9.227, 9.160], atol=1e-10)
    np.testing.assert_allclose(service['x (m)'], [10.45714] * 2)
    stage = result['summary'].iloc[:2]
    np.testing.assert_allclose(stage['Demand (mm)'], [18.754023847928803, 13.82028268843323])
    output.mkdir(parents=True, exist_ok=True)
    for name, key in [('Checks', 'summary'), ('CSI_Service_Source', 'service_audit'), ('Calculated_Stage_Source', 'source_audit'), ('Curves', 'curves')]:
        result[key].to_csv(output / (name + '.csv'), index=False, encoding='utf-8-sig')
    plots = []
    for stage_name, girder in [(engine.STAGES[0], None), (engine.STAGES[1], None),
                               *[(engine.STAGES[2], g) for g in result['girders']]]:
        plot = figure(result, stage_name, girder)
        assert list(plot.layout.xaxis.range) == [0, 20]
        plots.append({'stage': stage_name, 'girder': girder, 'title': plot.layout.title.text,
            'traces': [t.name for t in plot.data], 'x_range': list(plot.layout.xaxis.range)})
    evidence = {'milestone': engine.VERSION,
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, workbook]},
        'input_files_modified': False, 'native_WebTop_Vert_rows': len(result['service_audit']),
        'girder_names': result['girders'], 'max_service_abs_mm': service['Demand (mm)'].tolist(),
        'governing_x_m': service['x (m)'].tolist(), 'project_limit_mm': result['limit_mm'],
        'service_utilization': service.Utilization.tolist(), 'service_status': service.Status.tolist(),
        'transfer_construction_camber_mm': stage['Demand (mm)'].tolist(),
        'service_generated_curve_added': False, 'camber_or_dynamic_factor_added_to_import': False,
        'full_deflection_acceptance': False, 'plots': plots}
    (output / 'Real_Input_Verification.json').write_text(json.dumps(evidence, indent=2))
    (output / 'SLS_DEFLECT70_Audit.zip').write_bytes(engine.report_zip(result))
    print(json.dumps(evidence, indent=2), flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.project, args.workbook, args.output)
