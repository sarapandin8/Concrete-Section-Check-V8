"""BG40 chapter structure backed by current production results only.

The reference document supplies the report structure, never design values,
material assumptions, load factors or an unbonded tendon model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

import pandas as pd

from .report_models import ReportMetadata

VERSION = 'REPORT.DEFAULT81'
REFERENCE = 'BG40_Final_Complete_R10.docx'
CHAPTERS = (
    'Design Criteria Design Loads and Load Combinations',
    'Structural System and Analysis Model',
    'Section Properties',
    'Prestress Losses',
    'Analysis Results',
    'ULS Flexural Design',
    'ULS Shear and Torsion Design',
    'SLS Stress Check',
    'Deflection Check',
    'Deck Slab Reinforcement and Punching Review',
)


def plain(value):
    from concrete_pmm_pro.ui.igird_sls53_results import _plain
    return _plain(value)


def frame(value):
    if isinstance(value, pd.DataFrame):
        return value.copy(deep=True)
    return pd.DataFrame(value) if isinstance(value, (list, tuple)) else pd.DataFrame()


def display(value):
    if value is None or value is pd.NA:
        return 'Not available'
    if isinstance(value, str) and value.strip().lower() in {'nan', '<na>', 'nat'}:
        return 'Not available'
    if isinstance(value, float):
        if math.isnan(value):
            return 'Not available'
        return f'{value:,.6g}'
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(plain(value), ensure_ascii=False)
    return str(value)


def pick(row, *keys):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def fields_table(mapping, columns=('Parameter', 'Value')):
    return pd.DataFrame([(str(k).replace('_', ' '), display(v)) for k, v in mapping.items()
                         if v is not None], columns=columns)


@dataclass
class Calculation:
    title: str
    formula: str
    substitution: str
    result: str
    reference: str


@dataclass
class EvidenceTable:
    title: str
    data: pd.DataFrame
    source: str


@dataclass
class Chapter:
    number: int
    title: str
    notes: list[str] = field(default_factory=list)
    tables: list[EvidenceTable] = field(default_factory=list)
    calculations: list[Calculation] = field(default_factory=list)
    figures: list[dict] = field(default_factory=list)
    status: str = 'NOT CALCULATED'

    def table(self, title, value, source):
        data = frame(value)
        if not data.empty:
            self.tables.append(EvidenceTable(title, data, source))


@dataclass
class CalculationReport:
    metadata: ReportMetadata
    code: str
    chapters: list[Chapter]
    sources: pd.DataFrame
    controls: pd.DataFrame
    signature: str
    status: str
    warnings: list[str]
    raw_tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    input_snapshot: dict = field(default_factory=dict)
    figure_audit: list[dict] = field(default_factory=list)


def source_signature(state, metadata=None, include_figures=True, include_appendices=True):
    """Include inputs AND complete output cells; navigation cannot refresh an artifact."""
    keys = {'section_preset_key', 'section_geometry', 'section_parameters', 'section_dimensions',
            'concrete_material', 'concrete_materials', 'rebar_materials', 'prestress_materials',
            'rebars', 'prestress_elements', 'project_metadata', 'project_name',
            'project_design_code', 'project_code_edition', 'design_code', 'code_edition',
            'analysis_mode_settings', 'serviceability_settings', 'beam_uls_loads_table',
            'beam_sls_loads_table', 'beam_girder_system_settings',
            'beam_girder_sls_auto_load_settings', 'igird_uls_member_bank',
            'igird_uls_active_member', 'igird_sls_active_member',
            'igird_flexure_development_settings', '_igird_sls53_runtime'}
    # Include calculation inputs/caches, excluding temporary view/widget keys.
    prefixes = ('girder_prestress_', 'girder_strand_', 'girder_code_loss_',
                'girder_tension_limit_', 'girder_sls_diagram_limit_profile_',
                'section_assembly_', 'slab_shell55_', 'result_summary_beam_girder_sls_')
    keys.update(k for k in state if str(k).startswith(prefixes))
    from concrete_pmm_pro.ui import analysis_page as ap, igird_member_results as mr
    from concrete_pmm_pro.serviceability import girder_deflect70 as deform
    from concrete_pmm_pro.io.girder_deflect70 import BANK_KEY, ERROR_KEY
    keys.update([ap._BEAM_ULS_MANUAL_CALC_CACHE_KEY, mr.CACHE_KEY,
                 deform.RESULT_KEY, deform.SETTINGS_KEY, BANK_KEY, ERROR_KEY])
    from .bg40_print import PRESENTATION_VERSION
    body = {'version': VERSION, 'metadata': plain(metadata), 'figures': include_figures,
            'presentation_profile': PRESENTATION_VERSION,
            'appendices': include_appendices,
            'state': {k: plain(state.get(k)) for k in sorted(keys)}}
    # Use the same bindings as Analysis for development, hoops and materials.
    from concrete_pmm_pro.ui.igird_uls_report import report_member_inputs
    from concrete_pmm_pro.ui import igird_sls53_results as stress
    from concrete_pmm_pro.analysis import slab_review68 as slab
    from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS
    route = ap._beam_uls_strength_route_from_state(state, is_bridge=True, is_building=False)
    body['uls_input_bindings'] = {member: {check: mr.result_hash(state, rows,
        check_name=check, route=route) for check in FRAME_KEYS}
        for member, rows in report_member_inputs(state).items()}
    body['stress_input_binding'] = stress.fingerprint(state)
    for name, engine in [('deflection', deform), ('slab', slab)]:
        try:
            body[name + '_input_binding'] = engine.fingerprint(state)
        except (ValueError, TypeError, KeyError) as exc:
            body[name + '_input_binding'] = type(exc).__name__ + ': ' + str(exc)
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _status(values):
    values = [str(v).upper() for v in values]
    if any('FAIL' in v for v in values):
        return 'FAIL'
    if any('BLOCK' in v for v in values):
        return 'SOURCE BLOCKED'
    if not values or any(v not in {'PASS', 'PREVIEW PASS', 'BELOW THRESHOLD', 'NOT REQUIRED'} for v in values):
        return 'REVIEW'
    return 'Preview PASS' if any('PREVIEW' in v for v in values) else 'PASS'


def _source_rows(rows, member):
    from concrete_pmm_pro.io.girder_csi_import import source_info
    records = []
    for row in rows.to_dict('records'):
        info = source_info(row) or {}
        records.append({'Member': member, 'File': info.get('source_file') or 'Manual input',
            'Sheet': info.get('sheet', ''), 'Excel row': info.get('row', ''),
            'Case': info.get('case') or row.get('Case Name', ''),
            'Step': info.get('step', ''), 'x (m)': row.get('Station x (m)'),
            'Source SHA256': info.get('source_sha256', ''),
            'Coupling': info.get('kind', 'Project input'),
            'Evidence': info.get('evidence', '')})
    return records


def _add_trace(chapter, trace, label):
    for row in trace.to_dict('records'):
        chapter.calculations.append(Calculation(
            title=f"{label} | {row.get('Step', 'Calculation')}",
            formula=str(pick(row, 'Equation / route', 'Equation / substitution') or ''),
            substitution=str(row.get('Substitution / units', '')),
            result=str(pick(row, 'Result / branch', 'Result') or ''),
            reference=str(row.get('Code basis', 'Stored calculation route'))))


def _flexure_trace(chapter, row, label):
    """Report the accepted force equilibrium, not the BG40 unbonded equation."""
    basis = str(row.get('Code basis') or 'Stored flexural result')
    chapter.calculations.extend([
        Calculation(label + ' | Force equilibrium',
            'φ(Cc + ΣFs − ΣTps) = Nu; Mr = φMn',
            f"Cc={display(row.get('Cc kN'))} kN; ΣFs={display(row.get('Ordinary steel force kN'))} kN; "
            f"ΣTps={display(row.get('Strand force kN'))} kN; Nu={display(row.get('Nu kN'))} kN",
            f"Residual={display(row.get('Force residual N'))} N; c={display(row.get('Neutral axis c mm'))} mm; "
            f"a={display(row.get('Stress block a mm'))} mm", basis),
        Calculation(label + ' | Factored resistance', 'Mr = φMn; D/C = |Mux| / Mr',
            f"Mr={display(row.get('φ value'))} × {display(row.get('Mn nominal kN-m'))} kN·m; "
            f"|Mux|={display(row.get('Demand kN-m'))} kN·m",
            f"φMn={display(row.get('φMn kN-m'))} kN·m; "
            f"D/C={display(pick(row, 'Utilization value', 'D/C value'))}; Status={row.get('Status', 'REVIEW')}", basis),
    ])
    details = {k: row[k] for k in ('Section basis', 'Method', 'Solver basis',
        'φ policy', 'Strain condition', 'Strain compatibility basis',
        'Development source status', 'Minimum flexure gate',
        'Secondary-axis flexure gate', 'Notes') if k in row}
    chapter.table(label + ' calculation route and acceptance gates', fields_table(details), basis)
    for key in ('Strand development trace', 'Ordinary bar development trace'):
        chapter.table(label + ' ' + key.lower(), row.get(key), 'Stored nominal-strength group forces')


def build_calculation_report(state, metadata=None):
    from concrete_pmm_pro.ui import analysis_page as ap
    from concrete_pmm_pro.ui.igird_uls_report import current_check_packages, report_member_inputs
    from concrete_pmm_pro.ui.igird_case_review import FRAME_KEYS, controlling_result, eligible_rows
    from concrete_pmm_pro.ui import igird_sls53_results as sls
    from concrete_pmm_pro.serviceability import girder_deflect70 as deform
    from concrete_pmm_pro.analysis import slab_review68 as deck

    metadata = metadata or ReportMetadata(project_name=state.get('project_name'))
    code = str(state.get('project_code_edition') or state.get('code_edition') or 'Design code edition not recorded')
    chapters = [Chapter(i + 1, title) for i, title in enumerate(CHAPTERS)]
    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10 = chapters
    raw, sources, controls, warnings = {}, [], [], []
    c1.status = c2.status = c3.status = 'INPUT DATA'
    c1.notes = ['Design criteria below belong to the active project. The BG40 reference supplies the chapter order and calculation presentation.',
        'Imported CSI load vectors retain their case, step, member and station. Forces are not recombined or factored again in this report.',
        'Force units are kN and kN·m; section dimensions are mm, material stresses MPa. Each result table retains its source units.']
    c1.table('1.1 Design criteria', fields_table({'Design code edition': code,
        'Project design code': state.get('project_design_code') or state.get('design_code'),
        'Report layout reference': REFERENCE,
        'Scope': 'Active I-girder section and current stored member results'}), 'Project setup')
    materials = []
    for kind, key in [('Concrete', 'concrete_material'), ('Reinforcement', 'rebar_material'), ('Prestress', 'prestress_material')]:
        value = state.get(key)
        if value is not None:
            for k, v in plain(value).items():
                if v is not None:
                    materials.append({'Material': kind, 'Parameter': k, 'Value': display(v)})
    for kind, collection, items in [('Reinforcement', 'rebar_materials', 'rebars'),
                                    ('Prestress', 'prestress_materials', 'prestress_elements')]:
        used = {x.get('material_name') for x in plain(state.get(items) or [])}
        for material in plain(state.get(collection) or []):
            if material.get('name') not in used:
                continue
            for key, value in material.items():
                if value is not None and not isinstance(value, (dict, list)):
                    materials.append({'Material': kind + ' ' + str(material.get('name')),
                                      'Parameter': key, 'Value': display(value)})
    params = state.get('section_parameters') or {}
    if 'deck_fc_MPa' in params:
        materials.append({'Material': 'Deck concrete', 'Parameter': 'fc_MPa', 'Value': display(params['deck_fc_MPa'])})
    c1.table('1.2 Material properties', materials, 'Active Materials and Section Builder')
    for key in ('load_combinations_table', 'load_combination_table', 'load_combinations'):
        c1.table('1.3 Recorded load combination definitions', state.get(key), key)
    if not any('combination definitions' in t.title for t in c1.tables):
        c1.notes.append('Combination factors and train dynamic factors are not defined by the imported force rows. Obtain their definitions from the source analysis model; no BG40 load factors are assumed.')
    c2.table('2.1 Structural system', fields_table({'Section preset': state.get('section_preset_name') or state.get('section_preset_key'),
        **(state.get('beam_girder_system_settings') or {}),
        **(state.get('girder_prestress_system_settings') or {})}), 'Section Builder and Prestress system inputs')
    c2.notes.append('This report records the application inputs. Source FEA mesh, boundary restraints and load-combination definitions require the corresponding source-model records.')
    c2.table('2.2 Strand layout', state.get('girder_strand_layout_table'), 'Prestress strand layout inputs')
    c3.table('3.1 Section dimensions and composite inputs', fields_table(params), 'Section Builder inputs; names include source units')
    geometry = state.get('section_geometry')
    if geometry is not None:
        from concrete_pmm_pro.geometry.summary import summarize_geometry
        from concrete_pmm_pro.core.models import SectionGeometry
        try:
            geometry = SectionGeometry.model_validate(geometry) if isinstance(geometry, dict) else geometry
            properties = summarize_geometry(geometry)
            c3.table('3.2 Gross properties of the Section Builder polygon', fields_table({
                'Area A (mm²)': properties.area_mm2, 'Centroid x (mm)': properties.centroid_x_mm,
                'Centroid y (mm)': properties.centroid_y_mm, 'Ix (mm⁴)': properties.ix_nmm4,
                'Iy (mm⁴)': properties.iy_nmm4, 'Ztop (mm³)': properties.z_top_mm3,
                'Zbottom (mm³)': properties.z_bottom_mm3}), 'Polygon integration; not transformed composite properties')
            c3.figures.append({'kind': 'section', 'title': 'Section Builder geometry and reinforcement'})
            c3.notes.extend(properties.warnings)
        except (ValueError, TypeError, AttributeError) as exc:
            c3.notes.append('Gross section properties unavailable: ' + str(exc))
    c4.notes = ['Prestress force states are recorded inputs used by the stage checks. The reference BG40 external/unbonded friction and anchor-set formulas are not applied to a pretensioned I-girder.',
        'Stored loss audits without an input fingerprint are listed for review and do not certify that losses are current.']
    c4.table('4.1 Stage effective prestress force states', state.get('girder_prestress_force_states_table'), 'Prestress force state inputs')
    for key, label in [('girder_prestress_code_loss_summary_table', '4.2 Recorded prestress loss summary'),
                       ('girder_prestress_code_loss_result_table', '4.3 Recorded loss components'),
                       ('girder_prestress_refined_loss_interval_table', '4.4 Recorded time intervals')]:
        data = frame(state.get(key))
        c4.table(label, data, str(state.get('girder_prestress_code_loss_result_basis') or 'Stored loss audit') + ' | input binding unverified')
        if not data.empty:
            raw[key] = data
    c4.status = 'REVIEW' if c4.tables else 'NOT CALCULATED'
    c5.notes.append('The complete source vector at a row is kept together. A table of governing results never constructs a new independent Vmax–Tmax combination.')
    members = report_member_inputs(state)
    for member, rows in members.items():
        raw['ULS input ' + member] = rows.copy()
        sources.extend(_source_rows(rows, member))
        columns = [k for k in ('Case Name', 'Station x (m)', 'Mux', 'Vuy', 'Tu', 'Muy', 'Vux', 'Nu') if k in rows]
        c5.table('5.1 ULS actions for ' + member, rows[columns], 'Loads ULS member bank; kN and kN·m')
    sls_inputs = frame(state.get('beam_sls_loads_table'))
    if not sls_inputs.empty:
        raw['SLS input'] = sls_inputs
        sources.extend(_source_rows(sls_inputs, 'SLS active member'))
        c5.table('5.2 SLS actions', sls_inputs[[c for c in ('Stage', 'Case Name', 'Station x (m)', 'N', 'Mx', 'My', 'V', 'T') if c in sls_inputs]], 'Active SLS Loads; kN and kN·m')
    c5.status = 'AVAILABLE' if members or not sls_inputs.empty else 'NOT CALCULATED'
    for check in FRAME_KEYS:
        chapter = c6 if check == 'Flexure' else c7
        packages = current_check_packages(state, check, member_rows=members)
        for missing in members.keys() - packages.keys():
            warnings.append(f'{missing}: {check} has no current stored result. Calculate it in Analysis.')
            controls.append({'Member': missing, 'Check': check, 'Case': '', 'x': '',
                             'D/C': None, 'Basis': '', 'Status': 'NOT CALCULATED'})
        for member, package in packages.items():
            result = package['result']
            data = result[FRAME_KEYS[check]]
            raw[check + ' ' + member] = data.copy()
            control = controlling_result(data, check)
            row = control['row'] or {}
            native_status = _status(eligible_rows(data, check).get('Status', pd.Series(dtype=str)))
            controls.append({'Member': member, 'Check': check, 'Case': row.get('Case', ''),
                'x': row.get('Governing x', ''), 'D/C': control['ratio'],
                'Basis': control['basis'], 'Status': native_status})
            label = f"{member} | {check} | {row.get('Case', '')} | x={row.get('Governing x', '')}"
            chapter.notes.append(f"{label}: {native_status}. Numerical control: {control['basis']} = {display(control['ratio'])}. "
                f"Failing rows: {control['failed_rows']}; rows requiring review: {control['review_rows']}.")
            compact = [k for k in ('Case', 'Governing x', 'Demand', 'Capacity', 'Utilization', 'Status') if k in data]
            if check == 'Shear + Torsion':
                compact = [k for k in ('Case', 'Governing x', 'Stress D/C value', 'Transverse D/C value', 'Longitudinal D/C value', 'Status') if k in data]
            chapter.table(check + ' along span for ' + member, data[compact], str(row.get('Code basis') or code))
            origin = {k: v for k, v in row.items() if k.startswith('Source ') or k in ('Concurrency basis', 'Code basis', 'φ policy')}
            chapter.table(check + ' governing source for ' + member, fields_table(origin), 'Original governing stored result row')
            if check == 'Flexure':
                _flexure_trace(chapter, row, label)
            elif check == 'Shear':
                _add_trace(chapter, ap._beam_uls_shear_calculation_trace_dataframe(row), label)
                if not any(t.title == 'Shear variable definitions' for t in chapter.tables):
                    chapter.table('Shear variable definitions', ap._beam_uls_shear_variable_definitions_dataframe(), 'Stored shear calculation route')
            elif check == 'Torsion':
                _add_trace(chapter, ap._beam_uls_torsion_calculation_trace_dataframe(row), label)
                if not any(t.title == 'Torsion variable definitions' for t in chapter.tables):
                    chapter.table('Torsion variable definitions', ap._beam_uls_torsion_variable_definitions_dataframe(), 'Stored torsion calculation route')
            else:
                from concrete_pmm_pro.ui.igird_combined_vt import calculation_trace
                _add_trace(chapter, calculation_trace(row), label)
                if not any(t.title == 'V–T variable definitions' for t in chapter.tables):
                    chapter.table('V–T variable definitions', _vt_definitions(), 'Stored code-based V–T route')
            chapter.figures.append({'kind': 'uls', 'check': check, 'member': member,
                'title': check + ' demand and resistance for ' + member})
    c6.notes.insert(0, 'Signed primary-axis flexure uses the stored developed sectional equilibrium and its actual φ policy. Strain-compatible bonded strand results are not replaced by the reference document unbonded-tendon model.')
    c7.notes.insert(0, 'The code-based shear, torsion and concurrent V–T results are the primary checks. Combined research composite models are outside this report acceptance scope.')
    for ch, checks in [(c6, {'Flexure'}), (c7, {'Shear', 'Torsion', 'Shear + Torsion'})]:
        ch.status = _status(r['Status'] for r in controls if r['Check'] in checks) if ch.tables else 'NOT CALCULATED'
    stress = sls.current(state)
    c8.notes.append('Compression is negative and tension positive. Stage and material-specific stored limits, force-content decisions and reference assumptions remain attached to each result.')
    if stress:
        c8.status = _status(r['Status'] for r in stress['checks'])
        summary = pd.DataFrame(stress['summary'])
        selected = ['Stage', 'Case Name', 'Station x (m)', 'Actual stress (MPa)', 'Limit stress (MPa)', 'Utilization', 'Status']
        c8.table('8.1 Governing stress by stage', summary[[c for c in selected if c in summary]], stress['code_label'] + ' | ' + stress['member'])
        raw['SLS stress checks'] = pd.DataFrame(stress['checks'])
        for stage, entry in stress['stages'].items():
            checks = pd.DataFrame(entry['checks'])
            checks['Point'] = (checks.get('Concrete component', pd.Series('', index=checks.index)).astype(str)
                               + ' ' + checks.get('Fiber', checks.get('Demand', pd.Series('', index=checks.index))).astype(str)).str.strip()
            selected = ['Case Name', 'Point', 'Station x (m)',
                        'Actual stress (MPa)', 'Limit stress (MPa)', 'Utilization', 'Status']
            c8.table(stage + ' stress checks', checks[[c for c in selected if c in checks]], entry['profile'])
            for case, data in entry['cases'].items():
                raw['SLS ' + stage + ' ' + case] = data['raw'].copy()
                for component in data['limits']:
                    c8.figures.append({'kind': 'stress', 'stage': stage, 'case': case,
                        'component': component, 'title': f"{stress['member']} | {stage} | {case} | {component}"})
            for row in entry['checks']:
                c8.calculations.append(Calculation(f"{stage} | {row.get('Case Name')} | {row.get('Controls', row.get('Demand'))}",
                    'Utilization = demand / matching applicable stress limit',
                    f"σ={display(row.get('Actual stress (MPa)', row.get('Actual stress')))} MPa; "
                    f"limit={display(row.get('Limit stress (MPa)', row.get('Limit')))} MPa; "
                    f"x={display(row.get('Station x (m)', row.get('Governing x')))}",
                    f"Utilization={display(row.get('Utilization'))}; {row.get('Status')}",
                    str(pick(row, 'Limit profile source', 'Limit basis', 'Limit profile') or stress['code_label'])))
            # Record the actual stress decomposition used at each governing cut.
            seen_stations = set()
            for row in entry['checks']:
                case = entry['cases'].get(str(row.get('Case Name')))
                if not case:
                    continue
                points = case['raw']
                x = row.get('Station x (m)')
                identity = (str(row.get('Case Name')), x)
                if identity in seen_stations:
                    continue
                seen_stations.add(identity)
                points = points.loc[points['Station x (m)'].eq(x)]
                fields = ['Station x (m)', 'Case Name', 'Basis', 'SLS force content',
                    'N (kN)', 'User Mx (kN-m)', 'Auto Mx (kN-m)', 'Mx (kN-m)',
                    'Pe stage (kN)', 'yps eff (mm)', 'Top service (MPa)', 'Top PS (MPa)',
                    'Top total (MPa)', 'Bottom service (MPa)', 'Bottom PS (MPa)',
                    'Bottom total (MPa)', 'Reference review']
                for record in points[[c for c in fields if c in points]].to_dict('records'):
                    c8.table(stage + f' stress components at x={x} m', fields_table(record),
                        'Stored station stress decomposition; prestress counted once')
    elif state.get(sls.RUNTIME_KEY) is not None:
        c8.status = 'STALE'
        warnings.append('SLS stress results are stale and have been excluded.')
    displacement = deform.current(state)
    c9.notes.append('Service WebTop Vert envelopes retain their exported signs and unit conversion. They are not attributed to a live-load-only case when the export does not provide that definition.')
    if displacement:
        c9.status = displacement['status']
        columns = ['Stage', 'Girder', 'x (m)', 'Demand (mm)', 'Limit (mm)', 'Utilization', 'Status']
        c9.table('9.1 Deflection and camber checks', displacement['summary'][columns], displacement['limit_basis'])
        for key in ('summary', 'curves', 'source_audit', 'service_audit'):
            raw['Deflection ' + key] = frame(displacement.get(key))
        origin = displacement.get('input_source') or {}
        for sheet in origin.get('girders', []):
            sources.append({'Member': sheet['girder'], 'File': origin.get('file_name', ''),
                'Sheet': sheet['girder'], 'Source SHA256': origin.get('file_sha256', ''),
                'Coupling': 'Scalar SLS displacement envelopes',
                'Evidence': 'WebTop Vert as exported; no LL-only attribution'})
        for stage in deform.STAGES:
            names = displacement['girders'] if stage == 'Service stage' else [None]
            for girder in names:
                c9.figures.append({'kind': 'deflection', 'stage': stage, 'girder': girder,
                                  'title': stage + ' deflection ' + (girder or 'current section')})
        for r in displacement['summary'].to_dict('records'):
            c9.calculations.append(Calculation(r['Stage'] + ' | ' + r['Girder'],
                'D/C = max |δ| / applicable stage limit',
                f"max |δ|={display(r['Demand (mm)'])} mm; limit={display(r['Limit (mm)'])} mm",
                f"D/C={display(r['Utilization'])}; {r['Status']}", str(r['Basis'])))
    elif state.get(deform.RESULT_KEY) is not None:
        c9.status = 'STALE'
        warnings.append('Deflection results are stale and have been excluded.')
    slab = deck.current(state)
    c10.notes.append('Local normal-shear D/C is a local index, not an actual critical-perimeter punching acceptance. A value below one does not close the physical-perimeter or full-deck review.')
    if slab:
        from concrete_pmm_pro.io.slab_shell_import import current_package
        bank = current_package(state)
        if bank:
            raw['Slab source tables'] = pd.DataFrame(bank.sources)
            for source in bank.sources:
                sources.append({'Member': 'Deck slab', 'File': source.get('File', ''),
                    'Sheet': source.get('Table', ''), 'Coupling': 'Native CSI shell source',
                    'Evidence': source.get('Use', ''), 'Source SHA256': ''})
            c10.table('10.0 Imported deck source tables', bank.sources, 'Complete CSI source package')
            c10.notes.append('Slab import package SHA256 set: ' + ', '.join(bank.signature))
        c10.status = slab['status']
        for key, title in [('summary', '10.1 Deck component checks'), ('mat_envelopes', '10.2 Four reinforcement mats'),
                           ('coverage', '10.3 Source coverage'), ('exclusion_counts', '10.4 Excluded source records')]:
            c10.table(title, slab.get(key), slab['version'])
            raw['Slab ' + key] = frame(slab.get(key))
        raw['Slab native check rows'] = frame(slab.get('rows'))
        screen = slab.get('punching_screen78')
        if screen:
            c10.table('10.5 Punching local index by case', screen['summary'], screen['code'] + ' | ' + screen['thickness_basis'])
            raw['Punching local source rows'] = screen['rows'].copy()
            c10.notes.extend([screen['scope'], *screen['geometry_issues']])
            c10.figures.append({'kind': 'punching', 'title': 'Punching local D/C in plan with actual thickness'})
            r = screen.get('governing') or {}
            c10.calculations.append(Calculation('Local index at governing native corner',
                'Local index = Qbound / (φ vmin dv); vmin = 0.063 √(fc [ksi]) [ksi]',
                f"Qbound={display(r.get('Q bound (kN/m)'))} kN/m; "
                f"φvmin dv={display(r.get('phi v dv (kN/m)'))} kN/m; "
                f"h={display(r.get('Thickness (mm)'))} mm; dv={display(r.get('dv (mm)'))} mm",
                f"Local D/C={display(r.get('Local D/C'))}; full punching acceptance: REVIEW",
                screen['code'] + ' | Derived local screening index; physical perimeter not inferred'))
        c10.status = 'FAIL' if 'FAIL' in str(c10.status).upper() else 'REVIEW'
    elif state.get(deck.RESULT_KEY) is not None:
        c10.status = 'STALE'
    sources_df = pd.DataFrame(sources).drop_duplicates() if sources else pd.DataFrame(columns=['Member', 'File', 'Sheet', 'Excel row', 'Case', 'Step', 'x (m)', 'Source SHA256', 'Coupling', 'Evidence'])
    for ch in chapters:
        for i, t in enumerate(ch.tables):
            raw[f'Chapter {ch.number} table {i+1} {t.title}'] = t.data.copy()
    controls_df = pd.DataFrame(controls, columns=['Member', 'Check', 'Case', 'x', 'D/C', 'Basis', 'Status'])
    result_status = _status([r['Status'] for r in controls] + [c8.status, c9.status])
    # Missing chapters and unresolved slab scope never become an issue-ready report.
    if result_status in {'PASS', 'Preview PASS'} and any(c.status in {'NOT CALCULATED', 'STALE', 'REVIEW'} for c in chapters):
        result_status = 'REVIEW'
    snapshot_keys = ('section_preset_key', 'section_geometry', 'section_parameters',
        'concrete_material', 'concrete_materials', 'rebar_materials', 'prestress_materials',
        'rebars', 'prestress_elements', 'girder_strand_layout_table',
        'girder_prestress_system_settings', 'girder_prestress_force_states_table',
        'girder_prestress_code_loss_settings', 'beam_girder_system_settings',
        'beam_girder_sls_auto_load_settings', 'beam_uls_loads_table', 'beam_sls_loads_table',
        'project_metadata', 'project_design_code', 'project_code_edition')
    report = CalculationReport(metadata, code, chapters, sources_df, controls_df,
        source_signature(state, metadata), result_status, list(dict.fromkeys(warnings)), raw,
        {key: plain(state.get(key)) for key in snapshot_keys if key in state})
    from .bg40_figures import add_figures
    return add_figures(report, state)


def _vt_definitions():
    from concrete_pmm_pro.ui.igird_combined_vt import variable_definitions
    return variable_definitions()


def build_report_figure(state, spec):
    """Reuse Analysis chart builders; no capacity/stress solver is called."""
    kind = spec['kind']
    if kind not in {'uls', 'stress', 'deflection', 'punching', 'section'}:
        from .bg40_figures import extra_figure
        return extra_figure(state, spec)
    if kind == 'uls':
        from concrete_pmm_pro.ui.igird_uls_report import make_current_report_figure
        return make_current_report_figure(state, check_name=spec['check'], member=spec['member'],
            code_label=str(state.get('project_code_edition') or state.get('code_edition') or 'Project code'))
    if kind == 'stress':
        from concrete_pmm_pro.ui.igird_sls53_results import current
        from concrete_pmm_pro.visualization.igird_sls53 import stress_figure
        r = current(state)
        return stress_figure(r['stages'][spec['stage']]['cases'][spec['case']], stage=spec['stage'],
            component=spec['component'], span_m=r['span_m'], context_label=r['member']) if r else None
    if kind == 'deflection':
        from concrete_pmm_pro.serviceability.girder_deflect70 import current
        from concrete_pmm_pro.visualization.girder_deflect70 import figure
        r = current(state)
        return figure(r, spec['stage'], spec.get('girder')) if r else None
    if kind == 'punching':
        from concrete_pmm_pro.analysis.slab_review68 import current
        from concrete_pmm_pro.visualization.slab_punching78 import figure
        r = current(state)
        return figure(r) if r else None
    if kind == 'section':
        from .bg40_figures import section
        return section(state)
    return None
