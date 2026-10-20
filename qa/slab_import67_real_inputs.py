"""Verify native static CSI import against the unchanged source workbook.

Run with the actual four export sets. Optional --calculate checks downstream
compatibility; it neither qualifies the train load nor certifies deck design.
"""
from io import BytesIO
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import openpyxl

from concrete_pmm_pro.io import slab_shell_import as source


def run(exports, output, *, project=None):
    started = time.monotonic()
    files = []
    for path in exports:
        upload = BytesIO(path.read_bytes())
        upload.name = path.name
        files.append(upload)
    package = source.parse_files(files)
    assert package.ready, (package.errors, [s.title for s in package.missing])
    imported = package.tables['forces']
    # Read the native headers directly. This route does not use TableSpec or
    # the importer to reconstruct expected components or step identities.
    checked = 0
    headers = None
    raw_step_values = set()
    for path in exports:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book:
                rows = sheet.iter_rows(values_only=True)
                first = next(rows, ())
                if not first or str(first[0]).strip() != 'TABLE:  Element Forces - Area Shells':
                    continue
                headers = list(next(rows))
                next(rows)  # original CSI units row
                indices = [headers.index(c) for c in source.FORCES]
                native_values = []
                native_keys = []
                for row in rows:
                    if not any(v is not None for v in row) or str(row[0] or '').upper().startswith('END TABLE'):
                        continue
                    native_values.append([row[i] for i in indices])
                    native_keys.append([source.identifier(row[headers.index(c)])
                        for c in ('Area', 'AreaElem', 'Joint', 'OutputCase')])
                    step = source.identifier(row[headers.index('StepType')]) if 'StepType' in headers else ''
                    raw_step_values.add(step)
                np.testing.assert_array_equal(imported[list(source.FORCES)].to_numpy(float), np.array(native_values, float))
                np.testing.assert_array_equal(imported[['Area', 'AreaElem', 'Joint', 'OutputCase']].to_numpy(), np.array(native_keys))
                checked += len(native_values)
        finally:
            book.close()
    assert checked == len(imported) and headers is not None
    assert set(imported.StepType) == raw_step_values
    verification = {
        'milestone': source.VERSION, 'ready': package.ready, 'errors': package.errors,
        'source_headers': headers, 'StepType_header_exported': 'StepType' in headers,
        'all_eight_actions_preserved_exactly': True, 'all_native_record_keys_preserved': True,
        'native_records_checked': checked, 'step_values': sorted(raw_step_values),
        'summary': {k: v for k, v in package.summary.items() if k != 'case_rows'},
        'case_rows': package.summary['case_rows'].to_dict('records'),
        'notes': package.notes, 'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in exports},
        'force_multiplier': 1., 'full_deck_acceptance': False,
    }
    if project is not None:
        from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
        from concrete_pmm_pro.analysis import slab_design66 as design
        state = {}
        apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')), state)
        state[source.BANK_KEY] = package
        state[source.PENDING_KEY] = package.signature
        result = design.calculate(state)
        slab = imported.loc[imported.Area.isin(set(result['geometry'].corners.Area))].reset_index(drop=True)
        np.testing.assert_array_equal(result['rows'][list(source.FORCES)].to_numpy(), slab[list(source.FORCES)].to_numpy())
        assert result['rows'].StepType.eq('').all() if 'StepType' not in headers else True
        verification['downstream_calculation'] = {
            'engine': design.VERSION, 'source_rows': result['source_rows'],
            'design_rows': result['design_rows'], 'actions_preserved': True,
            'source_cases_preserved': sorted(result['rows'].OutputCase.unique()) == package.summary['cases'],
            'component_status': result['component_status'], 'status': result['status'],
        }
        verification['project_sha256'] = hashlib.sha256(project.read_bytes()).hexdigest()
    verification['seconds'] = time.monotonic() - started
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(verification, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in verification.items() if k not in ('source_headers', 'source_hashes', 'notes')}, ensure_ascii=False, indent=2))
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exports', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args()
    run(args.exports, args.output, project=args.project)
