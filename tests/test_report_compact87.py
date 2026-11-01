"""Fast full-content currency and compact engineering content invariants."""
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
from unittest.mock import patch

from docx import Document
import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.reporting.source_digest import source_digest
from concrete_pmm_pro.reporting.compact_report import compact_rows, grouped_bar_trace
from concrete_pmm_pro.reporting.workflow_reports import build_workflow_report
from concrete_pmm_pro.reporting.bg40_word import build_bg40_word_report
from concrete_pmm_pro.reporting.bg40_print import prepare_print_figure
from concrete_pmm_pro.ui.bg40_report import build_complete_artifact, default_metadata
from test_igird_reportcharts8 import calculated_state
from test_word_report_export import _one_pixel_png


@dataclass
class Source:
    data: pd.DataFrame
    nested: dict


def test_full_hash_numeric_objects_nullable_nested_and_late_mutations():
    data = pd.DataFrame({'numeric':np.arange(20000)/7,
        'case':['ULS1']*20000, 'nullable':pd.array([None]*20000,dtype='Int64'),
        'nested':[{'trace':[1.,2.]}]*20000})
    source = Source(data, {'same': data, 'blob': b'x'*2000000})
    before = source_digest(source)
    assert source_digest(deepcopy(source)) == before
    with patch.object(pd.DataFrame,'to_dict',side_effect=AssertionError('Materialized rows')), \
         patch.object(pd.DataFrame,'__deepcopy__',side_effect=AssertionError('Deepcopy')):
        assert source_digest(source) == before
    for column,value in [('numeric',999.123456789),('case','FAIL'),('nullable',2),('nested',{'trace':[1.,3.]})]:
        old = data.iloc[-1][column]
        data.at[data.index[-1],column] = value
        assert source_digest(source) != before, column
        data.at[data.index[-1],column] = old
        assert source_digest(source) == before
    source.nested['blob'] = b'x'*1999999+b'y'
    assert source_digest(source) != before


def test_signature_typed_keys_order_boundaries_and_cycle():
    assert source_digest({'b':2,'a':1}) == source_digest({'a':1,'b':2})
    assert source_digest({1:2}) != source_digest({'1':2})
    assert source_digest(['ab','c']) != source_digest(['a','bc'])
    array=np.arange(20000).reshape(100,200)
    before=source_digest(array[:,::2])
    array[-1,-2] = -1
    assert source_digest(array[:,::2]) != before
    a=[]; a.append(a)
    with pytest.raises(ValueError, match='Cyclic'):
        source_digest(a)


def test_compact_preserves_worst_each_status_case_and_corresponding_actions():
    data=pd.DataFrame({'Case':['A']*20+['B']*20,
        'Status':['PASS']*18+['FAIL','REVIEW']+['PASS']*19+['FAIL'],
        'Station x (m)':range(40),'Utilization':np.arange(40)/30,
        'Tu':np.arange(40)*3., 'Vuy':np.arange(40)*7.})
    data.loc[2,'Utilization']=float('inf')
    source=data.copy(deep=True)
    result,note=compact_rows(data)
    assert len(result)<len(data) and '40' in note
    assert set(zip(data.Case,data.Status))==set(zip(result.Case,result.Status))
    assert {2,18,19,39}.issubset(set(result.index))
    pd.testing.assert_frame_equal(result, data.loc[result.index])
    pd.testing.assert_frame_equal(source,data)


def test_signed_actions_never_mix_load_case_components():
    data=pd.DataFrame({'Case Name':['ULS1']*30,'Mux':range(-15,15),'Tu':range(30),'Vuy':range(30,60)})
    result,note=compact_rows(data)
    assert set(result.index)=={0,29} and note
    pd.testing.assert_frame_equal(result,data.loc[[0,29]])
    unrelated=pd.DataFrame({'Geometry':range(30),'Value':range(30)})
    assert compact_rows(unrelated)[0] is unrelated


def test_bar_trace_grouping_keeps_identity_and_all_unique_properties():
    rows=pd.DataFrame({'Bar':range(1,21),'fy_MPa':[420]*10+[500]*10,'factor':[.7]*20})
    result=grouped_bar_trace(rows)
    assert len(result)==2
    assert result.iloc[0]['Bar']==', '.join(map(str,range(1,11)))
    assert result.iloc[1]['fy_MPa']==500


@pytest.mark.parametrize('kind',['deflection','slab_plan','slab_profile','punching_perimeters','punching'])
def test_compact_chart_layout_preserves_source_values_ranges_shapes_and_gates(kind):
    import plotly.graph_objects as go
    figure=go.Figure(go.Scatter(x=[0,1,2],y=[-1.,2.3456789,0.],name='FAIL source'))
    figure.update_layout(meta={'source_case':'ULS1','status':'FAIL'}, legend={'yref':'container','y':.02},
        xaxis_range=[-1,3],yaxis_range=[-2,4],
        annotations=[dict(text='I-girder CLs: G1', x=.5, y=0, yshift=-62, xref='paper', yref='paper')],
        shapes=[dict(type='rect',x0=0,x1=2,y0=-1,y1=1)])
    before=figure.to_json()
    presentation=prepare_print_figure(figure,{'kind':kind},compact=True)
    result=presentation.figure
    assert 'I-girder CLs: G1' in presentation.caption and not result.layout.annotations
    assert figure.to_json()==before
    assert result.data[0].to_plotly_json()==figure.data[0].to_plotly_json()
    assert result.layout.meta==figure.layout.meta
    assert result.layout.xaxis.range==figure.layout.xaxis.range
    assert result.layout.yaxis.range==figure.layout.yaxis.range
    assert result.layout.shapes==figure.layout.shapes
    assert result.layout.height==580 and result.layout.width==1200
    assert result.layout.legend.yref=='paper'  # negative container coordinates clip the legend


def test_default_skips_archive_keeps_all_equations_figures_and_source_status(calculated_state,monkeypatch):
    monkeypatch.setattr('concrete_pmm_pro.reporting.bg40_word.plotly_figure_to_png_bytes',
                        lambda *a,**k:(_one_pixel_png(),[]))
    metadata=default_metadata(calculated_state)
    report=build_workflow_report(calculated_state,metadata)
    full=Document(BytesIO(build_bg40_word_report(report,calculated_state)))
    with patch('concrete_pmm_pro.ui.bg40_report.build_evidence_zip',side_effect=AssertionError('Automatic archive')):
        artifact=build_complete_artifact(calculated_state,metadata,report)
    compact=Document(BytesIO(artifact['docx']))
    assert artifact['compact'] and artifact['evidence'] is None
    assert artifact['status']==report.status
    assert len(compact.tables)<len(full.tables)
    assert len(compact.inline_shapes)==len(full.inline_shapes)>0
    assert [x.text for x in compact._element.xpath('.//m:t')]==[x.text for x in full._element.xpath('.//m:t')]
    text='\n'.join(p.text for p in compact.paragraphs)
    for chapter in report.chapters:
        for calc in chapter.calculations:
            assert 'Result: '+calc.result in text
    assert 'optional source evidence' in text
