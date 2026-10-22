"""Run the adopted-force bound against the project JSON and four native files."""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY
from concrete_pmm_pro.analysis import slab_top65 as top, slab_punching78 as bound
from concrete_pmm_pro.visualization.slab_punching78 import figure


def run(project, exports, output):
    started = time.monotonic()
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')), state)
    files = []
    for path in exports:
        f = BytesIO(path.read_bytes()); f.name = path.name; files.append(f)
    package = parse_files(files)
    assert package.ready, package.errors
    state[BANK_KEY] = package; state[PENDING_KEY] = package.signature
    source_before = package.tables['forces'].copy(deep=True)
    result = top.calculate(state)
    for key in ('rows', 'summary', 'support_faces', 'exclusion_counts'):
        pd.testing.assert_frame_equal(result[key], result['base_result'][key], check_exact=True)
    pd.testing.assert_frame_equal(package.tables['forces'], source_before, check_exact=True)
    t = time.monotonic(); check = bound.calculate(result); bound_seconds = time.monotonic()-t
    pd.testing.assert_frame_equal(check['rows'], result['punching_screen78']['rows'], check_exact=True)
    output.mkdir(parents=True, exist_ok=True)
    fig = figure(result)
    fig.write_image(str(output/'Actual_Punching78_Plan.png'), width=1440, height=780)
    fig.write_image(str(output/'Actual_Punching78_Plan.svg'), width=1440, height=780)
    (output/'Actual_Punching78_Plan.json').write_text(fig.to_json(), encoding='utf-8')
    check['summary'].to_csv(output/'Actual_Punching78_Summary.csv', index=False)
    check['rows'].to_csv(output/'Actual_Punching78_Sources.csv', index=False)
    (output/'Actual_Top_Slab_Report.zip').write_bytes(top.report_zip(result))
    record = {**bound.report_payload(check), 'governing': check['governing'],
        'imported_force_records': len(package.tables['forces']), 'slab_records': len(result['rows']),
        'retained_design_records': result['design_rows'], 'core_checks_unchanged': True,
        'source_forces_unchanged': True, 'bound_seconds': bound_seconds,
        'total_seconds': time.monotonic()-started,
        'input_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, *exports]}}
    (output/'Actual_Verification.json').write_text(json.dumps(record, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k != 'input_hashes'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--exports', type=Path, nargs=4, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.project, a.exports, a.output)
