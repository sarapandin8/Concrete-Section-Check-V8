"""Reproduce FLEXDEP1 on the supplied 20 m JSON without changing project inputs.

Run: python qa/igird_flexdep1_verify.py --out /absolute/output/directory
Optional --input MODEL.json and --deck-mm 250 (explicit QA comparison only).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from concrete_pmm_pro.io.project_io import project_from_json, apply_project_to_session_state
from concrete_pmm_pro.ui import analysis_page as a
from concrete_pmm_pro.analysis.igird_flexure_development import RESULT_VERSION, development_settings


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def verify(input_path: Path, out: Path, deck_mm: float | None = None):
    state = {}
    input_bytes = input_path.read_bytes()
    apply_project_to_session_state(project_from_json(input_bytes.decode()), state)
    if deck_mm is not None:
        state['section_parameters'] = {**state['section_parameters'], 'Tslab_mm': deck_mm}
    geometry_before = state['section_geometry'].model_dump()
    route = a._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    demand, construction, _ = a._beam_uls_construction_demand_from_state(state)
    prep, composite, _ = a._beam_uls_final_composite_preparation(state)
    assert composite is not None
    final = a._active_beam_uls_demand_dataframe_from_session(state)
    out.mkdir(parents=True, exist_ok=True)
    summary = {'version': RESULT_VERSION, 'input': input_path.name,
        'input_sha256': hashlib.sha256(input_bytes).hexdigest(),
        'code': 'AASHTO LRFD 9th Edition (2020)',
        'deck_mm': prep.deck_thickness_mm, 'effective_width_mm': prep.effective_width_mm,
        'qa_deck_override': deck_mm, 'development_settings': development_settings(state),
        'construction_factors_confirmed': demand.factors_ready, 'stages': {}}
    for stage, source_state, source in [('construction', state, construction), ('final', composite, final)]:
        started = time.perf_counter()
        result, messages = a._beam_uls_flexure_preview_dataframe(source_state, source,
            strength_route=route, prestress_force_stage=stage, full_span_capacity=True,
            use_aashto_solver=True, apply_girder_development=True)
        seconds = time.perf_counter() - started
        expected = source.assign(__x=pd.to_numeric(source['Station x (m)'])).sort_values(['Case Name', '__x'], kind='stable')
        assert len(result) == len(source)
        assert result['Station x (m)'].tolist() == expected['__x'].tolist()
        assert result['Nu kN'].tolist() == pd.to_numeric(expected['Nu']).tolist()
        valid = result[result['Force residual N'].notna()]
        assert valid['Force residual N'].abs().max() < .021
        assert (valid['φMn kN-m'] <= valid['Full-development reference φMn kN-m'] * 1.000001).all()
        groups, bars = [], []
        for _, row in result.iterrows():
            for item in row.get('Strand development trace', []) or []:
                if 'fps_used_MPa' in item:
                    assert 0 <= item['fps_used_MPa'] <= item['fpx_limit_MPa'] + 1e-8
                groups.append({'Case': row['Case'], 'Station x (m)': row['Station x (m)'],
                    'Nu kN': row['Nu kN'], 'Numerical status': row['Numerical status'], **item})
            for item in row.get('Ordinary bar development trace', []) or []:
                bars.append({'Case': row['Case'], 'Station x (m)': row['Station x (m)'], **item})
        columns = [c for c in result.columns if c not in ('Strand development trace', 'Ordinary bar development trace')]
        result[columns].to_csv(out / f'{stage}_stations.csv', index=False)
        pd.DataFrame(groups).to_csv(out / f'{stage}_strand_groups.csv', index=False)
        pd.DataFrame(bars).to_csv(out / f'{stage}_ordinary_bars.csv', index=False)
        (out / f'{stage}_trace.json').write_text(json.dumps(clean_json(result.to_dict('records')), indent=2, ensure_ascii=False, allow_nan=False))
        selected = result[result['Station x (m)'].isin([0,.5,1,2,5,7,8.5,10,19,19.5,20])]
        summary['stages'][stage] = {'seconds': seconds, 'rows': len(result),
            'max_abs_force_residual_N': valid['Force residual N'].abs().max(),
            'status_counts': result['Status'].value_counts().to_dict(),
            'numerical_status_counts': result['Numerical status'].value_counts().to_dict(),
            'station_samples': selected[[c for c in ['Station x (m)', 'Nu kN', 'Demand kN-m',
                'φMn kN-m','Mn nominal kN-m','φ value','Strand force kN','Utilization value',
                'Numerical status','Status'] if c in result]].to_dict('records'),
            'messages': messages}
        print(stage, len(result), f'{seconds:.3f}s', 'max residual', f"{valid['Force residual N'].abs().max():.6g}N", flush=True)
    assert state['section_geometry'].model_dump() == geometry_before
    assert input_path.read_bytes() == input_bytes
    (out / 'benchmark.json').write_text(json.dumps(clean_json(summary), indent=2, ensure_ascii=False, allow_nan=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT / 'qa/fixtures/I_Girder_20m.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--deck-mm', type=float)
    args = parser.parse_args()
    verify(args.input.resolve(), args.out.resolve(), args.deck_mm)
