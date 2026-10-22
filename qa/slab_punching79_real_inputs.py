"""Actual native thickness, unchanged CSI actions and comparison with release 78."""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY
from concrete_pmm_pro.analysis import slab_top65 as top, slab_punching78 as local
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
    screen = result['punching_screen78']
    rows = screen['rows']
    np.testing.assert_array_equal(rows['Resistance thickness (mm)'], rows['Thickness (mm)'])
    t = time.monotonic(); check = local.calculate(result); seconds = time.monotonic()-t
    pd.testing.assert_frame_equal(check['rows'], rows, check_exact=True)
    old_dir = Path(__file__).resolve().parent/'evidence/slab_punch78'
    before = pd.read_csv(old_dir/'Actual_Punching78_Sources.csv',
        dtype={k:str for k in local.KEYS}, float_precision='round_trip')
    old = json.loads((old_dir/'Actual_Verification.json').read_text())
    columns = ['Thickness (mm)', 'Qx bound (kN/m)', 'Qy bound (kN/m)', 'Q bound (kN/m)',
        'Source allowed', 'Support contact', 'Complete saved steps', 'Design included']
    pd.testing.assert_frame_equal(rows.set_index(local.KEYS)[columns].sort_index(),
        before.set_index(local.KEYS)[columns].sort_index(), check_exact=True)
    previous_point = rows.loc[np.isclose(rows['X (m)'], old['governing']['X (m)']) &
        np.isclose(rows['Y (m)'], old['governing']['Y (m)']) &
        rows.OutputCase.eq(old['governing']['OutputCase']) & rows['Local D/C'].notna()]
    output.mkdir(parents=True, exist_ok=True)
    fig = figure(result)
    fig.write_image(str(output/'Actual_Punching79_Plan.png'), width=1440, height=780)
    fig.write_image(str(output/'Actual_Punching79_Plan.svg'), width=1440, height=780)
    (output/'Actual_Punching79_Plan.json').write_text(fig.to_json(), encoding='utf-8')
    screen['summary'].to_csv(output/'Actual_Punching79_Summary.csv', index=False)
    rows.to_csv(output/'Actual_Punching79_Sources.csv', index=False)
    (output/'Actual_Top_Slab_Report.zip').write_bytes(top.report_zip(result))
    record = {**local.report_payload(screen), 'governing': screen['governing'],
        'previous_global_minimum_max_dc': old['max_dc'],
        'local_index_at_previous_governing_point': float(previous_point['Local D/C'].max()),
        'imported_force_records': len(package.tables['forces']), 'slab_records': len(result['rows']),
        'retained_design_records': result['design_rows'], 'core_checks_unchanged': True,
        'source_forces_and_masks_unchanged_from_78': True, 'local_index_seconds': seconds,
        'every_resistance_uses_same_corner_thickness': True, 'total_seconds': time.monotonic()-started,
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
