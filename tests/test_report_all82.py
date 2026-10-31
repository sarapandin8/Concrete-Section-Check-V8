"""Shared report routing, source fidelity, stale exclusion and no hidden solves."""
from contextlib import ExitStack
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile
import json
import re
import pandas as pd
import pytest
from docx import Document
from concrete_pmm_pro.reporting.bg40_data import build_report_figure,source_signature
from concrete_pmm_pro.reporting.workflow_reports import build_workflow_report,workflow_key,stored_sources
from concrete_pmm_pro.ui.bg40_report import ARTIFACT_KEY,artifact_is_current,build_complete_artifact,default_metadata
from concrete_pmm_pro.state.dirty_state import LAST_ANALYSIS_HASH_KEY,mark_analysis_current
from qa.build_report_all82_samples import column,beam,crossbeam
from tests.test_word_report_export import _one_pixel_png


def no_solvers():
    stack=ExitStack()
    for target in (
        'concrete_pmm_pro.ui.analysis_page._beam_uls_calculate_selected_check',
        'concrete_pmm_pro.ui.analysis_page._girder_full_length_sls_stage_rows',
        'concrete_pmm_pro.ui.analysis_page._column_pier_combined_vt_check_dataframe',
        'concrete_pmm_pro.analysis.pmm_solver.run_rc_pmm_solver',
        'concrete_pmm_pro.analysis.capacity_check.check_uls_demands_against_rc_pmm',
        'concrete_pmm_pro.serviceability.stress.run_elastic_sls_stress_check',
        'concrete_pmm_pro.analysis.crossbeam_uls.run_crossbeam_uls_flexure',
        'concrete_pmm_pro.analysis.crossbeam_uls_shear.run_crossbeam_uls_shear',
        'concrete_pmm_pro.analysis.crossbeam_uls_torsion.run_crossbeam_uls_torsion',
        'concrete_pmm_pro.analysis.crossbeam_uls_combined_vt.run_crossbeam_uls_combined_vt',
        'concrete_pmm_pro.analysis.crossbeam_sls_transfer.run_crossbeam_transfer_stress',
        'concrete_pmm_pro.analysis.crossbeam_sls_transfer.run_crossbeam_service_stress',
        'concrete_pmm_pro.analysis.crossbeam_sls_deflection.run_crossbeam_deflection_camber'):
        stack.enter_context(patch(target,side_effect=AssertionError('Report cannot solve')))
    return stack


@pytest.fixture(scope='module')
def calculated():
    states={'column':column(),'building_beam':beam('building_beam'),'bridge_beam':beam('bridge_beam'),
        'railway_u':beam('railway_u'),'crossbeam_cip':crossbeam(),'crossbeam_segmental':crossbeam(True)}
    for state in states.values(): mark_analysis_current(state,workspace='Analysis fixture')
    return states


@pytest.mark.parametrize('kind,preset,expected',[
    ('column_pier_pmm','parametric_i_girder','column'),('portal_frame_crossbeam','parametric_i_girder','crossbeam'),
    ('building_beam_girder','rectangle','building_beam'),('building_beam_girder','parametric_i_girder','building_beam'),('beam_girder','rectangle','bridge_beam'),
    ('beam_girder','railway_u_girder','railway_u'),('beam_girder','parametric_i_girder','i_girder')])
def test_active_workflow_owns_report(kind,preset,expected):
    assert workflow_key({'analysis_mode_settings':{'member_type':kind},'section_preset_key':preset})==expected


@pytest.mark.parametrize('name',['column','building_beam','bridge_beam','railway_u','crossbeam_cip','crossbeam_segmental'])
def test_complete_word_preserves_template_equations_source_gates_and_all_figures(calculated,name,monkeypatch):
    state=deepcopy(calculated[name]); meta=default_metadata(state)
    state.update(report_include_figures=False,report_include_appendices=False,report_max_table_rows=1)
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',lambda *a,**k:(_one_pixel_png(),[]))
    before=source_signature(state,meta); binding=state[LAST_ANALYSIS_HASH_KEY]
    with no_solvers():
        report=build_workflow_report(state,meta); artifact=build_complete_artifact(state,meta,report)
    assert source_signature(state,meta)==before and state[LAST_ANALYSIS_HASH_KEY]==binding
    doc=Document(BytesIO(artifact['docx']))
    assert len(doc.inline_shapes)==sum(len(c.figures) for c in report.chapters)>0
    assert doc._element.xpath('.//m:oMath')
    assert all(x['status']=='EMBEDDED' for x in artifact['figures'])
    header='\n'.join(p.text for p in doc.sections[0].header.paragraphs)
    assert report.workflow_label in header and 'Precast I-Girder' not in header
    from concrete_pmm_pro.reporting.bg40_template import ROOT
    with ZipFile(BytesIO(artifact['docx'])) as actual,ZipFile(ROOT/'BG40_R10_Template.docx') as original:
        assert actual.read('word/styles.xml')==original.read('word/styles.xml')
        assert actual.read('word/theme/theme1.xml')==original.read('word/theme/theme1.xml')
    with ZipFile(BytesIO(artifact['evidence'])) as evidence:
        assert evidence.read('Calculation_Report_BG40.docx')==artifact['docx']
        assert not json.loads(evidence.read('Provenance.json'))['solver_recalculation']
        assert json.loads(evidence.read('StoredResultSnapshot.json'))


@pytest.mark.parametrize('name',['column','building_beam','bridge_beam','railway_u','crossbeam_cip','crossbeam_segmental'])
def test_stale_results_are_excluded_without_refreshing_analysis_binding(calculated,name):
    state=deepcopy(calculated[name]); binding=state[LAST_ANALYSIS_HASH_KEY]
    state['concrete_materials']=[{'name':'changed C99','fc_MPa':99.}]
    with no_solvers(): report=build_workflow_report(state)
    assert report.status=='STALE' and state[LAST_ANALYSIS_HASH_KEY]==binding
    assert not any(c.calculations or c.figures for c in report.chapters[5:9])


def test_crossbeam_section_edit_invalidates_strength_and_stress_but_not_external_displacement(calculated):
    state=deepcopy(calculated['crossbeam_cip']); parameters=state['crossbeam_seclib1_definitions'][0]['Parameters']
    name=next(iter(parameters)); parameters[name]=float(parameters[name])*1.1
    with no_solvers(): report=build_workflow_report(state)
    assert report.controls.iloc[:6].Status.eq('STALE').all()
    assert not report.controls.iloc[6:].Status.eq('STALE').any()


def test_beam_preserves_cases_values_and_failures(calculated):
    state=deepcopy(calculated['bridge_beam']); report=build_workflow_report(state)
    assert report.status=='FAIL'
    pd.testing.assert_frame_equal(report.raw_tables['Flexure full station results'],state['_beam_girder_uls_manual_calculation_cache']['Flexure']['flexure_preview_df'])
    with no_solvers(): fig=build_report_figure(state,report.chapters[5].figures[0])
    assert set(fig.layout.meta['source_cases'].values())=={'ULS sample A','ULS sample B'}
    assert fig.layout.meta['combined_vector_created'] is False


def test_missing_checks_and_diagnostic_outputs_never_become_design_pass():
    state={'analysis_mode_settings':{'member_type':'beam_girder'},'crossbeam_ptloss_advanced_qa_result_v1':{'status':'PASS','rows':[{'value':999}]}}
    assert 'crossbeam_ptloss_advanced_qa_result_v1' not in stored_sources(state)
    report=build_workflow_report(state)
    assert report.status=='REVIEW' and report.chapters[5].status=='NOT CALCULATED' and report.warnings


def test_full_source_cells_invalidate_artifact_but_navigation_does_not(calculated):
    state=deepcopy(calculated['bridge_beam']); meta=default_metadata(state)
    state[ARTIFACT_KEY]={'signature':source_signature(state,meta)}
    state['girder_selected_tab']='Another view'; assert artifact_is_current(state,meta)
    data=state['_beam_girder_uls_manual_calculation_cache']['Shear']['shear_check_df']
    data.iloc[-1,data.columns.get_loc('Status')]='FAIL after source correction'
    assert not artifact_is_current(state,meta)


def test_column_vt_failure_controls_report_instead_of_package_version_label():
    from tests.test_column_pier_vt_report1 import _stored_vt_state
    state=_stored_vt_state(); data=state['column_pier_combined_vt_result_df']; data.loc[data.index[0],'Status']='FAIL'
    mark_analysis_current(state,workspace='Analysis fixture')
    with no_solvers(): report=build_workflow_report(state)
    assert report.status=='FAIL' and report.chapters[6].status=='FAIL' and report.controls.Status.eq('FAIL').any()


def test_module_pmm_binding_detects_rebar_edit_after_another_analysis_marked_project_current(calculated):
    from concrete_pmm_pro.analysis.preflight import build_analysis_input_from_session_state
    from concrete_pmm_pro.analysis.runtime import analysis_input_hash
    state=deepcopy(calculated['column'])
    state['rc_pmm_result_input_hash']=analysis_input_hash(build_analysis_input_from_session_state(state),'Standard')
    assert build_workflow_report(state).chapters[5].status!='STALE'
    state['rebars'][0]=state['rebars'][0].model_copy(update={'diameter_mm':32.})
    mark_analysis_current(state,workspace='A different Analysis command')
    with no_solvers(): report=build_workflow_report(state)
    assert report.chapters[5].status=='STALE'
    assert not report.chapters[5].calculations and not report.chapters[5].figures


def test_module_sls_binding_detects_changed_limit_after_another_analysis_marked_project_current(calculated):
    from concrete_pmm_pro.analysis.runtime import serviceability_input_hash
    from concrete_pmm_pro.ui import analysis_page as ap
    state=deepcopy(calculated['column'])
    state['serviceability_settings']=state['serviceability_summary'].settings
    with patch.object(ap.st,'session_state',state):
        model=ap._serviceability_analysis_input_from_session()
        settings=ap._serviceability_settings_from_session()
    state['serviceability_summary_hash']=serviceability_input_hash(model,settings,[],True)
    assert build_workflow_report(state).chapters[7].status!='STALE'
    state['serviceability_settings']=settings.model_copy(update={'concrete_compression_limit_ratio':.3})
    mark_analysis_current(state,workspace='A different Analysis command')
    with no_solvers(): report=build_workflow_report(state)
    assert report.chapters[7].status=='STALE' and not report.chapters[7].calculations


def test_wide_word_tables_repeat_case_and_physical_station_in_every_panel():
    from concrete_pmm_pro.reporting.bg40_word import _table
    data=pd.DataFrame([{'Case':'ULS A','Station x (m)':x,**{f'Value {i}':i+x for i in range(12)}} for x in (1.,2.)])
    data.attrs['report_repeat_columns']=['Case','Station x (m)']
    document=Document()
    _table(document,data,'Stored station checks','Analysis')
    assert len(document.tables)>1
    for item in document.tables:
        assert [c.text for c in item.rows[0].cells[:2]]==['Case','Station x (m)']
        assert [r.cells[1].text for r in item.rows[1:]]==['1','2']


def test_explicitly_excluded_diagram_boundary_does_not_replace_real_governing_calculation():
    from concrete_pmm_pro.reporting.workflow_reports import governing,scalars
    rows=pd.DataFrame([{'Status':'REVIEW','Station type':'DIAGRAM BOUNDARY','Notes':'It is excluded from governing torsion decisions.','D/C value':float('nan')},
        {'Status':'PASS','Station type':'LOAD STATION','Notes':'Scoped production check','D/C value':.8,'Capacity kN-m':42.}])
    assert governing(rows)['Capacity kN-m']==42.
    assert 'Undefined' not in scalars({'Real zero':0.,'Undefined':float('nan')})


def test_resistance_arithmetic_is_distinct_from_source_detailing_or_scope_gate():
    from concrete_pmm_pro.reporting.workflow_reports import equations
    from concrete_pmm_pro.reporting.bg40_data import Chapter
    chapter=Chapter(7,'Shear')
    equations(chapter,{'Demand kN':100.,'φVn kN':200.,'Governing D/C value':.9,'Status':'REVIEW'},'Shear | Case A','Source code')
    result=chapter.calculations[0].result
    assert 'Resistance ratio=0.5' in result and 'Source governing utilization=0.9' in result and 'Stored status: REVIEW' in result


def test_torsion_with_common_moment_capacity_column_uses_torque_equation():
    from concrete_pmm_pro.reporting.workflow_reports import equations
    from concrete_pmm_pro.reporting.bg40_data import Chapter
    chapter=Chapter(7,'Torsion')
    equations(chapter,{'Check':'Torsion','Demand kN-m':20.,'Capacity kN-m':40.,'phiTn kN-m':40.,'Status':'PASS'},'Torsion | Case A','Source code')
    assert chapter.calculations[0].formula=='D/C = |Tu| / φTn'


def test_additional_stage_summary_does_not_erase_existing_sls_failure(calculated):
    state=deepcopy(calculated['bridge_beam'])
    state['serviceability_summary']=state['serviceability_summary'].model_copy(update={'overall_status':'FAIL'})
    state['result_summary_beam_girder_sls_stage_summary_df']=pd.DataFrame([{'Stage':'Transfer stage','Case Name':'TR','Status':'PASS','Utilization':.1}])
    mark_analysis_current(state,workspace='Analysis fixture')
    with no_solvers(): report=build_workflow_report(state)
    assert report.chapters[7].status=='FAIL' and report.status=='FAIL'


def test_cip_combined_charts_do_not_invent_physical_segment_joints(calculated):
    state=deepcopy(calculated['crossbeam_cip']); report=build_workflow_report(state)
    specs=[s for s in report.chapters[6].figures if s.get('plot_check')=='Shear + Torsion']
    assert {s['component'] for s in specs}=={'stress','transverse','longitudinal'}
    with no_solvers():
        for spec in specs:
            chart=build_report_figure(state,spec)
            labels=[str(a.text) for a in chart.layout.annotations]+[str(t.name) for t in chart.data]
            assert not any(('Physical joint' in label and 'REVIEW' in label) or re.match(r'J\d+ REVIEW',label) for label in labels)


def test_non_i_chapter_breaks_use_original_heading_property_without_empty_break_paragraphs(calculated,monkeypatch):
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',lambda *a,**k:(_one_pixel_png(),[]))
    state=deepcopy(calculated['column'])
    artifact=build_complete_artifact(state,default_metadata(state))
    doc=Document(BytesIO(artifact['docx']))
    from docx.oxml.ns import qn
    assert not any(b.get(qn('w:type'))=='page' for b in doc._element.xpath('.//w:br'))
    assert doc._element.xpath('.//w:pageBreakBefore')


def test_crossbeam_print_keeps_centered_endpoint_labels_inside_plot_without_mutating_source():
    import plotly.graph_objects as go
    from concrete_pmm_pro.reporting.bg40_print import prepare_print_figure
    source=go.Figure(go.Scatter(x=[0.,10.,20.],y=[1.,2.,3.],text=['Left','Middle','Right'],
        mode='markers+text',textposition='bottom center'))
    source.update_xaxes(range=[0.,20.])
    printed=prepare_print_figure(source,{'kind':'workflow82','plot':'crossbeam','title':'Stored stress'}).figure
    assert tuple(printed.data[0].textposition)==('bottom right','bottom center','bottom left')
    assert source.data[0].textposition=='bottom center'
    assert tuple(printed.data[0].x)==tuple(source.data[0].x)
    assert tuple(printed.data[0].y)==tuple(source.data[0].y)
