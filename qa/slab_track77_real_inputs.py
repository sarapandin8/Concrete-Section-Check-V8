"""Verify the project track geometry using its JSON and four unchanged CSI exports.

No train-load equivalence or local punching PASS is fabricated. The before/after
comparison proves that the project geometry setting preserves all slab source
records, derived section checks, support-face samples and numerical summaries.
"""
from pathlib import Path
import argparse
import hashlib
from io import BytesIO
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from concrete_pmm_pro.analysis import slab_top65 as top, slab_track77 as track
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.io.slab_shell_import import parse_files, BANK_KEY, PENDING_KEY
from concrete_pmm_pro.visualization.slab_track77 import figure


def run(project, exports, output):
    started = time.monotonic()
    state = {}
    apply_project_to_session_state(project_from_json(project.read_text(encoding='utf-8')), state)
    files = []
    for path in exports:
        file = BytesIO(path.read_bytes()); file.name = path.name; files.append(file)
    package = parse_files(files)
    if not package.ready:
        raise ValueError(package.errors)
    state[BANK_KEY] = package
    state[PENDING_KEY] = package.signature
    track.save(state, {'enabled': False})
    before = top.calculate(state)
    t = time.monotonic()
    track.save(state, {'enabled': True, 'width_m': 2., 'depth_mm': 300.,
                      'count': 2, 'spacing_m': 5., 'offset_m': 0., 'exclude_flange': True})
    after = top.calculate(state, reuse=before['shear_result'])
    seconds = time.monotonic()-t
    for key in ('rows', 'summary', 'support_faces', 'mat_envelopes', 'exclusion_counts'):
        pd.testing.assert_frame_equal(before[key], after[key], check_exact=True)
    assert after['accepted_result_reused']
    assert after['punching']['rows'].empty and after['punching']['status'] == 'NOT CALCULATED'
    distribution = after['track_distribution']
    output.mkdir(parents=True, exist_ok=True)
    distribution['tracks'].to_csv(output/'Track_Strips.csv', index=False)
    distribution['elements'].to_csv(output/'Exact_Element_Fractions.csv', index=False)
    fig = figure(after)
    assert not any(t.name in ('D/C scale', 'Review / missing') for t in fig.data)
    assert fig.layout.meta['color_is_utilization'] is False
    fig.write_image(str(output/'Actual_Track45_Plan.png'), width=1440, height=780, scale=1)
    fig.write_image(str(output/'Actual_Track45_Plan.svg'), width=1440, height=780)
    (output/'Actual_Track45_Plan.json').write_text(fig.to_json(), encoding='utf-8')
    (output/'Track45_Compact_Report.zip').write_bytes(top.report_zip(after))
    result = {'milestone': track.VERSION, 'source_rows': after['source_rows'],
              'imported_force_records': len(package.tables['forces']),
              'slab_rows': len(after['rows']), 'design_rows': after['design_rows'],
              'native_girder_count': sum(s['Kind'] == 'Girder' for s in after['supports']),
              'girder_flange_widths_m': sorted({2*s['half_width'] for s in after['supports'] if s['Kind'] == 'Girder'}),
              'all_source_and_section_rows_identical': True, 'all_summaries_and_faces_identical': True,
              'accepted_mechanics_reused': True, 'track_rebuild_seconds': seconds,
              'total_including_import_seconds': time.monotonic()-started,
              'tracks': distribution['tracks'].to_dict('records'),
              'area_m2': distribution['area_m2'], 'notes': distribution['notes'],
              'punching_status': after['punching']['status'], 'full_deck_acceptance': False,
              'code_exemption': False, 'actions_multiplier': 1.,
              'input_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [project, *exports]}}
    (output/'Actual_Verification.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--exports', type=Path, nargs=4, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.project, args.exports, args.output)
