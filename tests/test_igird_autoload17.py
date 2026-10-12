from io import BytesIO
from pathlib import Path
from concrete_pmm_pro.ui.girder_csi_import import _native_preview, _upload_signature
from concrete_pmm_pro.io.girder_csi_import import FORCE_MAP, source_info, read_tables

FILE = Path(__file__).resolve().parents[1]/'qa/fixtures/CSiBridge_Bridge_Object_Girder_Forces_CSIIMPORT14.xlsx'
class Upload(BytesIO):
    def __init__(self,data,name): super().__init__(data); self.name=name
def native(): return Upload(FILE.read_bytes(),FILE.name)

def test_every_native_force_goes_to_its_own_physical_member():
    frame,errors=_native_preview([native()])
    assert not errors and len(frame)==640 and frame.Girder.nunique()==2
    for _,row in frame.iterrows():
        info=source_info(row)
        assert row.Girder==info['bridge_object']+' / '+info['girder']
        assert all(row[target]==float(info['raw_fields'][source]) for source,target in FORCE_MAP.items())
        assert info['kind']=='ENVELOPE' and not info['concurrency_confirmed']
    assert frame.Nu.ne(0).all()

def test_duplicate_files_and_invalid_force_block_entire_native_batch():
    _,errors=_native_preview([native(),native()]);assert errors
    table=read_tables(FILE.read_bytes(),FILE.name)['Bridge Object Girder Forces']
    table.iloc[1,table.columns.get_loc('P')]='bad'
    _,errors=_native_preview([native(),Upload(table.to_csv(index=False).encode(),'invalid.csv')])
    assert errors

def test_legacy_format_retains_explicit_mapping():
    assert _native_preview([Upload(b'Case Name,Station x (m),Mux,Vuy,Tu,Muy,Vux,Nu\nC1,1,10,2,3,0,0,0\n','legacy.csv')]) is None

def test_file_signature_detects_new_bytes_and_ignores_batch_order():
    a=native();b=Upload(b'other','other.csv')
    assert _upload_signature([a,b])==_upload_signature([b,a])
    assert _upload_signature([a])!=_upload_signature([Upload(a.getvalue()+b' ',a.name)])
