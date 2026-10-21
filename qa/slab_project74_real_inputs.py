"""Verify four native CSI exports survive Project JSON in a fresh process.

Use --calculate for a full comparison to the accepted REVIEW68 CSV evidence.
The generated project is a private QA artifact, not a replacement user model.
"""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from concrete_pmm_pro.io import slab_project74 as archive, slab_shell_import as source
from concrete_pmm_pro.io.project_io import (apply_project_to_session_state, project_from_json,
    project_from_session_state, project_to_json)


def hashes(package):
    return {name: {"rows": len(frame), "columns": list(frame.columns),
        "dtypes": list(map(str, frame.dtypes)),
        "sha256": hashlib.sha256(frame.to_csv(index=False, float_format='%.17g', na_rep='<NULL>').encode()).hexdigest()}
        for name, frame in package.tables.items()}


def read_project(path):
    state = {}
    with patch.object(source, 'parse_files', side_effect=AssertionError('Excel was required after restore')):
        apply_project_to_session_state(project_from_json(path.read_text()), state)
    assert source.current_package(state) is not None
    return state


def fresh_process(project, output):
    state = read_project(project)
    package = source.current_package(state)
    proof = {'ready_without_excel': True, 'tables': hashes(package), 'signature': list(package.signature),
        'units': package.units, 'force_rows': package.summary['force_rows'],
        'slab_force_rows': package.summary['slab_force_rows'], 'case_rows': package.summary['case_rows'].to_dict('records')}
    output.write_text(json.dumps(proof, indent=2))


def run(project, exports, output, *, calculate=False):
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text()), state)
    uploads = []
    for path in exports:
        stream = BytesIO(path.read_bytes());stream.name = path.name;uploads.append(stream)
    package = source.parse_files(uploads)
    assert package.ready, package.errors
    state[source.BANK_KEY] = package;state[source.PENDING_KEY] = package.signature
    print('Read four native export sets; records:', package.summary['force_rows'], flush=True)
    started = time.monotonic()
    saved = project_to_json(project_from_session_state(state))
    save_seconds = time.monotonic() - started
    saved_path = output/'Project_with_shell_inputs.json'
    saved_path.write_text(saved)
    started = time.monotonic()
    loaded = read_project(saved_path)
    load_seconds = time.monotonic() - started
    restored = source.current_package(loaded)
    for name, frame in package.tables.items():
        pd.testing.assert_frame_equal(frame, restored.tables[name], check_exact=True)
    assert package.units == restored.units and package.signature == restored.signature
    assert package.sources == restored.sources and package.notes == restored.notes
    # A second save must reuse the identical input archive without accumulating data.
    started = time.monotonic()
    second = project_from_session_state(loaded)
    warm_save_seconds = time.monotonic() - started
    assert second.metadata[archive.METADATA_KEY] == json.loads(saved)['metadata'][archive.METADATA_KEY]
    subprocess.run([sys.executable, str(Path(__file__).resolve()), '--restore-only', str(saved_path),
        '--output', str(output/'Fresh_process.json')], check=True, capture_output=True, text=True, timeout=120)
    child = json.loads((output/'Fresh_process.json').read_text())
    assert child['tables'] == hashes(package) and child['signature'] == list(package.signature)
    assert child['units'] == package.units
    from concrete_pmm_pro.analysis.slab_shell56_geometry import recover
    from concrete_pmm_pro.analysis.slab_connections59 import layout
    geometry, restored_geometry = recover(package), recover(restored)
    for name in geometry.elements:
        np.testing.assert_array_equal(geometry.elements[name], restored_geometry.elements[name])
    for name in geometry.parent_axes:
        for axis in ('long', 'transverse'):
            np.testing.assert_array_equal(geometry.parent_axes[name][axis], restored_geometry.parent_axes[name][axis])
    connections, restored_connections = layout(package, geometry, state), layout(restored, restored_geometry, loaded)
    pd.testing.assert_frame_equal(connections['lines'], restored_connections['lines'], check_exact=True)
    assert connections['end_zones'] == restored_connections['end_zones']
    evidence = {'milestone': archive.VERSION,
        'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, *exports]},
        'exact_round_trip_all_tables': True, 'units_sources_notes_and_signatures_preserved': True,
        'force_and_geometry_values_preserved_exactly': True,
        'shell_axes_girder_and_bearing_geometry_preserved': True,
        'fresh_process_without_excel': child['ready_without_excel'], 'tables': hashes(package),
        'source_force_records': package.summary['force_rows'], 'slab_force_records': package.summary['slab_force_rows'],
        'source_cases': package.summary['cases'], 'project_json_bytes': len(saved.encode()),
        'raw_shell_archive_bytes': second.metadata[archive.METADATA_KEY]['raw_bytes'],
        'first_save_seconds': save_seconds, 'validate_and_restore_seconds': load_seconds,
        'warm_project_construction_seconds': warm_save_seconds,
        'archive_stable_after_second_save': True, 'resistance_results_persisted': False}
    if calculate:
        from concrete_pmm_pro.analysis import slab_review68 as review
        result = review.calculate(loaded)
        baseline = Path(__file__).resolve().parents[1]/'qa/evidence/slab_print72/native'
        audit = result['code_review']
        comparisons = {}
        for name, frame in [('Check_Summary', result['summary']), ('Four_Mats', result['mat_envelopes']),
            ('Source_Coverage', result['coverage']), ('Exclusions', result['exclusion_counts']),
            ('Code_Eligibility', audit['eligibility']), ('Governing_Vectors', audit['governing_vectors']),
            ('Selected_Section_Cuts', audit['section_cuts'])]:
            data = frame.to_csv(index=False).encode('utf-8-sig')
            assert data == (baseline/(name+'.csv')).read_bytes(), name
            comparisons[name] = {'byte_identical_to_PRINT72': True, 'sha256': hashlib.sha256(data).hexdigest()}
        evidence['recalculation_csv_comparisons'] = comparisons
        evidence['calculated_source_rows'] = result['source_rows']
        evidence['calculated_design_rows'] = result['design_rows']
        evidence['calculated_status'] = result['status']
    evidence['seconds'] = time.monotonic()-start
    (output/'Real_Input_Verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in evidence.items() if k not in ('tables', 'source_hashes', 'recalculation_csv_comparisons')}, indent=2), flush=True)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path)
    parser.add_argument('--exports', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--calculate', action='store_true')
    parser.add_argument('--restore-only', type=Path)
    args = parser.parse_args()
    if args.restore_only:
        fresh_process(args.restore_only, args.output)
    else:
        if not args.project or not args.exports:parser.error('--project and --exports are required')
        run(args.project, args.exports, args.output, calculate=args.calculate)
