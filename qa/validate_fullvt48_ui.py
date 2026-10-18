"""Actual app.py Calculate and stored-model UI verification on source JSON rows.

Software/UI verification, not structural validation. The UI fixture uses the
four original U2A vectors, including the below-threshold regression and a smaller-Tu V–T governor. Full-bank replay is verified separately.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import logging
import math
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for name in ('streamlit', 'streamlit.runtime.scriptrunner_utils.script_run_context'):
    logging.getLogger(name).setLevel(logging.ERROR)
logging.getLogger('streamlit.deprecation_util').disabled = True
import pandas as pd
from streamlit.testing.v1 import AppTest
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.girder_load_bank import BANK_KEY, ACTIVE_KEY, activate_member
from concrete_pmm_pro.io.girder_csi_import import source_info
from concrete_pmm_pro.ui import analysis_page as ap, igird_composite_steel45 as model
from concrete_pmm_pro.ui import igird_member_results as members, igird_modeltn47 as view


def ok(app):
    assert not app.exception, [x.message for x in app.exception]


def primary_tables(app):
    return [x.value for x in app.dataframe if 'Model Tn · U + slab (kN-m)' in x.value.columns]


def near(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-7), (a, b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.project.read_bytes()
    project = json.loads(raw)
    state = {}
    apply_project_to_session_state(project_from_json(raw.decode()), state)
    original_params = deepcopy(state['section_parameters'])
    original_interface = deepcopy(state['beam_girder_interface_shear_settings'])
    bank = pd.DataFrame(project['metadata']['workflow_load_tables'][BANK_KEY])
    selected = bank.loc[bank.apply(lambda r: (source_info(r) or {}).get('row') in {491,556,167,237}
        and (source_info(r) or {}).get('case') == 'U2A', axis=1)].copy()
    assert len(selected) == 4
    assert set(pd.to_numeric(selected['Station x (m)'])) == {1.,2.,18.}
    # Actual original source vectors only, with unchanged section/material/steel.
    # Reduce UI fixture rows to make the verification portable and fast.
    state[BANK_KEY] = selected.copy(deep=True)
    state['beam_uls_loads_table'] = selected.iloc[[0]].copy(deep=True)
    activate_member(state, str(selected.iloc[0]['Girder']))
    records = []
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=180)
    for key, value in state.items():
        app.session_state[key] = deepcopy(value)
    app.session_state['_nav_active_workspace'] = 'Analysis'
    with patch.object(model, 'calculate', wraps=model.calculate) as calculate:
        app.run()
        ok(app)
        for check in ('Shear','Torsion', 'Shear + Torsion'):
            next(x for x in app.radio if x.label == 'ULS check to calculate').set_value(check).run()
            ok(app)
            calls_before = calculate.call_count
            next(x for x in app.button if x.label.startswith('Calculate '+check+' — all')).click().run()
            ok(app)
            assert calculate.call_count == calls_before + 2
            frames = primary_tables(app)
            assert len(frames) >= 3, 'Collection overview and both member primary tables required'
            overview = frames[0]
            assert len(overview) == 2
            expected = {'BOBJ1 / Interior Girder 2': (263.88290334163923, 1.5543380512524256),
                'BOBJ1 / Left Exterior Girder': (242.42663752937884, .9382797423910947)}
            for _, row in overview.iterrows():
                tn, dc = expected[row['Girder']]
                near(row['Model Tn · U + slab (kN-m)'], tn)
                near(row['Model nominal V–T D/C'], dc)
                assert row['Status'] == 'MODEL REVIEW'
            expanders = [x.label for x in app.expander]
            assert expanders.count(view.REFERENCE_LABEL) == 2
            assert 'Reference summary — I-girder hoop / code route' in expanders
            cache = app.session_state[members.CACHE_KEY]
            for name in expected:
                entry = cache[name][check]
                assert model.KEY not in entry['result']
                saved = app.session_state[model.RUNTIME_KEY].get(str(entry['input_hash']))
                assert saved is not None
                calculation = saved['rows'][0]['calculation']
                assert calculation['accepted_Tn_kNm'] is None
                source = saved['rows'][0]
                near(source['actions']['tu_Nmm']/1e6, source['source_CSI']['Tu'])
                assert source['torsion_reference']['T shift applied'] is False
            design = app.session_state[ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY][check]
            assert model.KEY not in design
            calls_after = calculate.call_count
            app.run()
            ok(app)
            assert calculate.call_count == calls_after
            records.append({'check': check, 'primary_table_rows': overview.to_dict('records'),
                'model_calculation_calls': calls_after-calls_before,
                'render_rerun_added_solver_calls': 0, 'reference_panels': 2,
                'exceptions': 0, 'primary_model_status': 'MODEL REVIEW'})
            print('PASS app.py:', check, 'primary U/slab Tn, reference panels, no redraw solver', flush=True)
        assert app.session_state['section_parameters'] == original_params
        assert app.session_state['beam_girder_interface_shear_settings'] == original_interface
    # Component verification: no new buttons or checkboxes in the model view.
    snapshot = app.session_state[model.RUNTIME_KEY].get(str(cache[next(iter(expected))][check]['input_hash']))
    stored = args.output/'fullvt48_stored_snapshot.json'
    stored.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    script = f'''import json
from pathlib import Path
from concrete_pmm_pro.ui.igird_modeltn47 import render
render(json.loads(Path({str(stored)!r}).read_text()))
'''
    with patch.object(model, 'calculate', side_effect=AssertionError('Render must not solve')):
        component = AppTest.from_string(script, default_timeout=30).run()
        ok(component)
    assert len(component.button) == len(component.checkbox) == 0
    assert args.project.read_bytes() == raw
    audit = {'status': 'PASS', 'release': view.VIEW_VERSION,
        'source_file': args.project.name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_bank_rows': len(bank), 'UI_fixture_original_source_rows': len(selected),
        'UI_fixture_selection': 'Four original U2A vectors: Excel rows 491,556,167,237; full-bank replay verified separately',
        'source_file_unchanged': True, 'section_and_interface_inputs_unchanged': True,
        'model_controls_added': {'buttons': 0, 'checkboxes': 0}, 'actual_app_Calculate': records,
        'browser_screenshot_QA': 'Not performed; no browser binary is installed',
        'structural_validation': 'Not established; review model equations and limits unchanged'}
    (args.output/'fullvt48_project_ui_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    print('PASS: source JSON and section inputs unchanged; model is not a production resistance.', flush=True)


if __name__ == '__main__':
    main()
