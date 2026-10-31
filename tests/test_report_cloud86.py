"""Full-cell source fidelity and bounded allocations before Word generation."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

from concrete_pmm_pro.reporting.bg40_data import _json_signature, plain, source_signature
from concrete_pmm_pro.reporting.source_stream import plain_view, preparation_progress, checkpoint
from concrete_pmm_pro.reporting.bg40_word import _write_json
from concrete_pmm_pro.ui.bg40_report import default_metadata
from test_igird_reportcharts8 import calculated_state


@dataclass
class SourcePackage:
    table: pd.DataFrame
    records: list


def encoded(value, **options):
    return ''.join(json.JSONEncoder(ensure_ascii=False, **options).iterencode(plain_view(value)))


@pytest.mark.parametrize('sort_keys', [False, True])
@pytest.mark.parametrize('indent', [None, 2])
def test_lazy_json_matches_legacy_plain_bytes(sort_keys, indent):
    from concrete_pmm_pro.reporting.report_models import ReportMetadata
    frame = pd.DataFrame({'Case':['สะพาน', 'B', 'C'],
        'Result':[1.23456789012345, float('inf'), float('nan')],
        'nullable':pd.array([1, None, 2],dtype='Int64'),
        'trace':[{'first':[1,2]}, None, {'last':-1e-12}]})
    payload={'frame':frame, 'package':SourcePackage(frame,[frame, {'Status':'FAIL'}]),
        'metadata':ReportMetadata(report_title='橋'), 'NA':pd.NA,
        'numpy':[np.int64(2),np.float64('nan')], 'empty':[], 'empty_frame':pd.DataFrame(),
        'colliding_keys':{1:'replaced','1':'retained'}, 'tuple':('A',None)}
    options={'sort_keys':sort_keys,'indent':indent}
    assert encoded(payload,**options)==json.dumps(plain(payload),ensure_ascii=False,**options)


def test_source_hash_stream_never_materializes_dataframe_records_or_deepcopies_dataclasses():
    frame=pd.DataFrame({'Case':range(6000),'Value':np.arange(6000)/7.})
    package=SourcePackage(frame,[frame])
    expected=sha256(json.dumps(plain(package),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    with patch.object(pd.DataFrame,'to_dict',side_effect=AssertionError('Whole-table record list')), \
         patch.object(pd.DataFrame,'__deepcopy__',side_effect=AssertionError('Dataclass deepcopy')):
        actual=_json_signature(plain_view(package))
    assert actual==expected
    frame.iloc[-1,1]+=1
    assert _json_signature(plain_view(package))!=actual


def test_source_evidence_json_preserves_all_rows_and_legacy_format():
    data={'source':SourcePackage(pd.DataFrame({'x':range(3000),'Status':['FAIL']*3000}),[])}
    output=BytesIO()
    with ZipFile(output,'w') as archive:
        _write_json(archive,'Source.json',data,source_objects=True)
    with ZipFile(BytesIO(output.getvalue())) as archive:
        assert archive.read('Source.json')==json.dumps(plain(data),ensure_ascii=False,indent=2).encode()


def test_preparation_has_checkpoints_and_cancellation_releases_callback():
    events=[]
    with preparation_progress(lambda message,fraction:events.append((message,fraction))):
        checkpoint('Reading full source table',.04)
        encoded(pd.DataFrame({'x':range(3000)}))
    checkpoint('Must not reach previous callback',.05)
    assert events and events[0]==('Reading full source table',.04)
    def stop(*args):
        raise RuntimeError('Low headroom')
    with pytest.raises(RuntimeError,match='Low headroom'),preparation_progress(stop):
        encoded(pd.DataFrame({'x':[1]}))
    encoded(pd.DataFrame({'x':[1]}))


def test_full_slab_sources_still_invalidate_report_at_last_cell(calculated_state):
    state=dict(calculated_state)
    table=pd.DataFrame({'x':range(5000),'Result':np.ones(5000)})
    state['slab_shell55_large_source']=SourcePackage(table,[])
    metadata=default_metadata(state)
    before=source_signature(state,metadata)
    table.iloc[-1,1]=9.
    assert source_signature(state,metadata)!=before


def test_report_shares_read_only_table_storage_without_mutating_sources():
    from concrete_pmm_pro.reporting.bg40_data import Chapter
    source=pd.DataFrame({'x':range(5000),'y':np.ones(5000)})
    chapter=Chapter(1,'Complete source')
    chapter.table('Rows',source,'Analysis')
    table=chapter.tables[0].data
    assert np.shares_memory(source['y'].to_numpy(),table['y'].to_numpy())
    table.attrs['report_repeat_columns']=['x']
    assert source.attrs=={}
    assert len(table)==5000 and table.iloc[-1,0]==4999
