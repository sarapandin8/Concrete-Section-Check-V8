"""CSI bridge member-table import. Preserve every row and its source identity."""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
import json
import math
import re
import pandas as pd

VERSION = 'IGIRDER.CSIIMPORT2.auto-detect-v2'
SOURCE_TAG = 'CSP_CSI_SOURCE='
CSI_COLUMNS = ['Layout Line Distance','Girder Distance','ItemType','P','V2','V3','T','M2','M3']
APP_COLUMNS = ['Active','Station x (m)','Case Name','Mux','Vuy','Tu','Muy','Vux','Nu','Note']
FORCE_MAP = {'P':'Nu','V2':'Vuy','V3':'Vux','T':'Tu','M2':'Muy','M3':'Mux'}
ENVELOPE_NOTE = ('CSI Max/Min bounds: simultaneous Mu/Nu/Vu/Tu is not established by this table. '
    'Numerical screening is retained; use corresponding concurrent FEA actions for final acceptance.')

def _key(value):
    return re.sub(r'[^a-z0-9]','',str(value).casefold())

def _blank(value):
    return value is None or str(value).strip()=='' or bool(pd.isna(value))

def _number(value):
    if _blank(value) or isinstance(value,bool):
        raise ValueError('a finite numeric value is required')
    n=float(str(value).replace(',','').strip())
    if not math.isfinite(n):
        raise ValueError('a finite numeric value is required')
    return n

def is_csi_table(frame):
    keys={_key(c) for c in frame.columns}
    return {'p','v2','v3','t','m2','m3'}<=keys and bool(keys & {'girderdistance','layoutlinedistance','distance','station'})

def is_app_table(frame):
    keys={_key(c) for c in frame.columns}
    return bool(keys & {'casename','comboname','loadcase','outputcase','case','name'}) and bool(
        keys & {'stationxm','stationsm','station','s','sm','distance','distancem','x','xm','location','locationm'}) and bool(
        keys & {'mux','mx','muy','my','vuy','vy','vux','vx','nu','p','n','tu','t',
            'momentx','momenty','shearx','sheary','axial','axialforce','torsion'})

def read_tables(payload: bytes, filename: str):
    """Read worksheet headers explicitly; do not silently use the bridge-total sheet."""
    raw = ({'CSV':pd.read_csv(BytesIO(payload),header=None,encoding='utf-8-sig')}
        if filename.casefold().endswith('.csv') else pd.read_excel(BytesIO(payload),sheet_name=None,header=None))
    tables={}
    for name,grid in raw.items():
        for i in range(min(25,len(grid))):
            header=grid.iloc[i].tolist()
            keys={_key(c) for c in header if not _blank(c)}
            probe=pd.DataFrame(columns=[c for c in header if not _blank(c)])
            if {'p','v2','v3','t','m2','m3'}<=keys or is_app_table(probe):
                frame=grid.iloc[i+1:].copy()
                frame.columns=[str(c).strip() if not _blank(c) else f'Unnamed {j}' for j,c in enumerate(header)]
                frame.attrs['header_row']=i+1
                tables[name]=frame
                break
    return tables

@dataclass
class CsiImport:
    frame: pd.DataFrame
    errors: list[str]
    audit: pd.DataFrame
    counts: dict

def prepare_csi_table(frame, *, sheet_name, case_name='ENV_ULS'):
    lookup={_key(c):c for c in frame.columns}
    if len(lookup) != len(frame.columns):
        return CsiImport(pd.DataFrame(columns=APP_COLUMNS),['Duplicate column names in CSI table.'],pd.DataFrame(),{})
    distance=lookup.get('girderdistance') or lookup.get('layoutlinedistance') or lookup.get('distance') or lookup.get('station')
    required={c:lookup.get(_key(c)) for c in FORCE_MAP}
    errors=[]
    if not distance or any(c is None for c in required.values()):
        return CsiImport(pd.DataFrame(columns=APP_COLUMNS),['CSI table requires a distance column and P, V2, V3, T, M2, M3.'],pd.DataFrame(),{})
    step_column=lookup.get('itemtype') or lookup.get('steptype')
    output_column=lookup.get('outputcase') or lookup.get('casename')
    rows=[]; audit=[]; occurrences={}; counts={}; unit_factors={c:1.0 for c in required}
    length_factor=1.0
    data=frame.copy(deep=True)
    if not data.empty:
        first=data.iloc[0]
        # A CSI units row is textual in the distance field. Validate all units;
        # never convert an unknown unit or malformed data row into zero.
        dunit=_key(first.get(distance))
        if dunit in {'m','mm','cm','ft','in'}:
            length_factor={'m':1.,'mm':.001,'cm':.01,'ft':.3048,'in':.0254}[dunit]
            for field,col in required.items():
                units = ({'kn':1.,'n':.001,'tonf':9.80665,'kip':4.4482216152605}
                    if field in {'P','V2','V3'} else
                    {'knm':1.,'nmm':1e-6,'nm':.001,'tonfm':9.80665,'kipft':1.3558179483314})
                unit=_key(first.get(col))
                if unit not in units:
                    errors.append(f'{sheet_name}: unsupported unit {first.get(col)!r} for {field}.')
                else:
                    unit_factors[field]=units[unit]
            data=data.iloc[1:]
    for index,raw in data.iterrows():
        if all(_blank(raw.get(c)) for c in [distance,*required.values()]):
            continue
        excel_row=int(index)+1  # read_tables retains the original zero-based row index
        step=str(raw.get(step_column) or 'Static').strip() if step_column and not _blank(raw.get(step_column)) else 'Static'
        if step.casefold() in {'max','min'}:
            step=step.title()
        elif step_column and step.casefold() not in {'static','step','last','single'}:
            errors.append(f'{sheet_name} row {excel_row}: unsupported ItemType / StepType {step!r}.')
        try:
            x=_number(raw.get(distance))*length_factor
            if x<0:
                raise ValueError('distance must be nonnegative')
            values={f:_number(raw.get(c))*unit_factors[f] for f,c in required.items()}
        except (ValueError,TypeError) as exc:
            errors.append(f'{sheet_name} row {excel_row}: {exc}; fill distance and all six force components.')
            continue
        base=str(raw.get(output_column)).strip() if output_column and not _blank(raw.get(output_column)) else str(case_name).strip()
        if not base:
            errors.append(f'{sheet_name} row {excel_row}: enter the FEA case / envelope name.')
            continue
        identity=(base,step,x)
        occurrence=occurrences.get(identity,0)+1
        occurrences[identity]=occurrence
        # Distinguish repeated source rows without assuming Before/After labels.
        # A set is just occurrence order at each source station, not a FEA case.
        case=f'{base} / {sheet_name} / {step} / set {occurrence}'
        source={'schema':VERSION,'sheet':str(sheet_name),'row':excel_row,'case':base,
            'step':step,'occurrence':occurrence,'distance_column':str(distance),
            'kind':'ENVELOPE' if step in {'Max','Min'} else 'UNVERIFIED',
            'layout_distance':None if 'layoutlinedistance' not in lookup or _blank(raw.get(lookup['layoutlinedistance'])) else str(raw.get(lookup['layoutlinedistance']))}
        note=SOURCE_TAG+json.dumps(source,ensure_ascii=False,separators=(',',':'))
        rows.append({'Active':True,'Station x (m)':x,'Case Name':case,
            **{target:values[field] for field,target in FORCE_MAP.items()},'Note':note})
        audit.append({'Source sheet':sheet_name,'Excel row':excel_row,'ItemType':step,'Row set':occurrence,
            'Station x (m)':x,'Case Name':case,**values})
        counts[step]=counts.get(step,0)+1
    return CsiImport(pd.DataFrame(rows,columns=APP_COLUMNS),errors,pd.DataFrame(audit),counts)

def source_info(row):
    note=str(row.get('Note') or '')
    if SOURCE_TAG not in note:
        return None
    try:
        return json.JSONDecoder().raw_decode(note.split(SOURCE_TAG,1)[1])[0]
    except (ValueError,TypeError):
        return {'kind':'UNVERIFIED','step':'UNKNOWN'}

def girder_ranking(tables):
    ranking=[]
    for name,frame in tables.items():
        if 'girder' not in name.casefold() or not is_csi_table(frame):
            continue
        imported=prepare_csi_table(frame,sheet_name=name)
        if imported.errors or imported.frame.empty:
            continue
        r={'Girder':name,'Rows':len(imported.frame),'Max rows':imported.counts.get('Max',0),'Min rows':imported.counts.get('Min',0)}
        for target,label in [('Mux','|M3| kN-m'),('Vuy','|V2| kN'),('Tu','|T| kN-m')]:
            r[label]=imported.frame[target].abs().max()
        ranking.append(r)
    return pd.DataFrame(ranking).sort_values('|M3| kN-m',ascending=False,kind='stable').reset_index(drop=True) if ranking else pd.DataFrame()

def source_cases(source):
    return {str(row.get('Case Name')):source_info(row) for _,row in source.iterrows() if source_info(row)}

def apply_source_gate(result,source):
    """Keep numeric screening and failure evidence; imported bounds cannot certify coupled checks."""
    sources=source_cases(source)
    if not sources or result is None or result.empty or 'Case' not in result:
        return result
    result=result.copy(deep=True)
    original_rows={(str(row.get('Case Name')),float(row.get('Station x (m)'))):row
        for _,row in source.iterrows() if source_info(row)}
    for i,row in result.iterrows():
        info=sources.get(str(row.get('Case')))
        if info is None:
            continue
        result.at[i,'Source ItemType']=info.get('step','UNKNOWN')
        result.at[i,'Source sheet']=info.get('sheet','UNKNOWN')
        result.at[i,'Source row set']=info.get('occurrence')
        exact_row=original_rows.get((str(row.get('Case')),float(row.get('Station x (m)',float('nan')))))
        if exact_row is not None:
            exact=source_info(exact_row)
            result.at[i,'Source Excel row']=exact.get('row')
            for field in ('Mux','Vuy','Tu','Muy','Vux','Nu'):
                unit='kN-m' if field in {'Mux','Tu','Muy'} else 'kN'
                result.at[i,f'Source {field} {unit}']=float(exact_row.get(field))
        result.at[i,'Source coupling']='ENVELOPE — REVIEW' if info.get('kind')=='ENVELOPE' else 'UNVERIFIED — REVIEW'
        note=ENVELOPE_NOTE if info.get('kind')=='ENVELOPE' else 'CSI source concurrency is unverified; use corresponding concurrent FEA actions for final acceptance.'
        result.at[i,'Notes']=str(row.get('Notes') or '')+' '+note
        for column in ('Status','Strength status','Stress status','Transverse status','Longitudinal status'):
            if str(row.get(column)).upper() in ({'PASS','BELOW THRESHOLD','NOT REQUIRED'} if column=='Status' else {'PASS'}):
                if column!='Status' or 'Numerical status' not in result.columns:
                    result.at[i,'Numerical '+column]=row.get(column)
                result.at[i,column]='REVIEW'
    return result

def append_errors(current, imported, *, current_is_csi):
    """Appending cannot reinterpret old axial signs or merge duplicate source paths."""
    errors=[]
    if not current.empty and not current_is_csi:
        axial=pd.to_numeric(current.get('Nu',pd.Series(dtype=float)),errors='coerce')
        if axial.isna().any() or axial.abs().gt(0).any():
            errors.append('Existing rows have a different or undeclared Nu convention. Replace rows, or first verify that the existing rows use raw CSI P signs.')
    combined=pd.concat([current,imported],ignore_index=True)
    if not combined.empty:
        # Legacy app imports contain numeric text; match stations by value so
        # an existing 2.0 and uploaded "2" cannot duplicate the same source path.
        keys=combined[['Case Name','Station x (m)']].copy()
        keys['Station x (m)']=pd.to_numeric(keys['Station x (m)'],errors='coerce')
        keys['Case Name']=keys['Case Name'].astype(str).str.strip().str.casefold()
        if keys.duplicated(['Case Name','Station x (m)']).any():
            errors.append('Append would repeat a Case Name / station. Replace this import, or enter a distinct FEA case / envelope name.')
    return errors
