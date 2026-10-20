"""Reproduce TOP65 with Project JSON and the same four complete CSI exports.

No equivalent UDL is fabricated: this records the supplied package as imported
analysis. Rerun with the user's new CSI exports to assess the new loading model.
"""
from pathlib import Path
import argparse
import hashlib
from io import BytesIO
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from concrete_pmm_pro.analysis import slab_top65 as top
from concrete_pmm_pro.analysis.slab_connections59 import INCLUDED
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY, FORCES
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES
from concrete_pmm_pro.visualization import slab_top65 as plots


def run(project, exports, output, *, render=False):
    started = time.monotonic()
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')), state)
    files = []
    for path in exports:
        file = BytesIO(path.read_bytes())
        file.name = path.name
        files.append(file)
    package = parse_files(files)
    if not package.ready:
        raise ValueError(f'Import unavailable: {package.errors}; {[x.title for x in package.missing]}')
    state[BANK_KEY] = package
    state[PENDING_KEY] = package.signature
    result = top.calculate(state)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [('Check_Summary', result['summary']), ('Four_Mats', result['mat_envelopes']),
                       ('Clear_Spacing', result['clear_spacing']), ('Source_Coverage', result['coverage']),
                       ('Exclusion_Counts', result['exclusion_counts']), ('Code_Coverage', result['code_coverage'])]:
        data.to_csv(output/('TOP65_'+name+'.csv'), index=False, encoding='utf-8-sig')
    native = package.tables['forces'].loc[package.tables['forces'].Area.isin(set(result['geometry'].corners.Area))].reset_index(drop=True)
    rows = result['rows']
    preserved = bool(np.array_equal(native[list(FORCES)].to_numpy(), rows[list(FORCES)].to_numpy()))
    assert preserved
    keys = ['Area', 'AreaElem', 'Joint', 'OutputCase', 'StepType']
    assert native[keys].equals(rows[keys])
    assert rows.loc[~rows[INCLUDED], [c for c, _ in top.VIEWS.values()]].isna().all().all()
    rendered = []
    if render:
        for view in ('Direct N–M · transverse', 'Shear · transverse', 'Shear · longitudinal'):
            adapted = top.map_adapter(result, view)
            stem = 'NM_transverse' if view.startswith('Direct') else 'Shear_'+view.rsplit(' ', 1)[-1]
            for mode, figure in [('Plan', plots.plan(result, adapted, view, ALL_CASES)),
                                 ('Profile', plots.profile(adapted, view, ALL_CASES))]:
                path = output/('TOP65_'+stem+'_'+mode+'.png')
                figure.write_image(str(path), width=1440, height=720, scale=1)
                rendered.append(path.name)
    provenance = {'version': top.VERSION, 'code': result['code'],
        'source_rows': result['source_rows'], 'design_rows': result['design_rows'],
        'geometry_excluded_rows': result['geometry_excluded_rows'], 'peak_excluded_rows': result['peak_excluded_rows'],
        'summary': json.loads(result['summary'].to_json(orient='records')),
        'four_mats': json.loads(result['mat_envelopes'].to_json(orient='records')),
        'all_eight_native_actions_preserved': preserved, 'all_native_keys_preserved': True,
        'excluded_rows_have_no_numeric_resistance_checks': True,
        'source_actions_multiplier': 1., 'ballast_in_resistance': False,
        'load_basis': result['load_basis'], 'load_basis_status': result['load_basis_status'],
        'punching_status': result['punching']['status'], 'full_deck_acceptance': False,
        'component_status': result['component_status'], 'status': result['status'],
        'input_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, *exports]},
        'calculation_seconds': result['top65_seconds'],
        'base_section_seconds': result['seconds'],
        'total_including_import_seconds': time.monotonic()-started, 'rendered_charts': rendered}
    (output/'TOP65_Verification.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2, allow_nan=False))
    (output/'TOP65_Compact_Report.zip').write_bytes(top.report_zip(result))
    print(json.dumps({k: provenance[k] for k in ('version', 'source_rows', 'design_rows', 'component_status', 'punching_status', 'calculation_seconds')}, indent=2))
    print(result['mat_envelopes'].to_string(index=False))
    return state, result, provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--exports', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    run(args.project, args.exports, args.output, render=args.render)
