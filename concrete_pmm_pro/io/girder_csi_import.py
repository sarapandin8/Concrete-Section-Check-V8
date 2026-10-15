"""CSI bridge member-table import. Preserve every row and its source identity."""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
import csv
import hashlib
import json
import math
import re
import pandas as pd

VERSION = 'IGIRDER.CSIIMPORT14.source-vectors-v2'
SOURCE_TAG = 'CSP_CSI_SOURCE='
CSI_COLUMNS = ['Layout Line Distance','Girder Distance','ItemType','P','V2','V3','T','M2','M3']
APP_COLUMNS = ['Active','Station x (m)','Case Name','Mux','Vuy','Tu','Muy','Vux','Nu','Note']
FORCE_MAP = {'P':'Nu','V2':'Vuy','V3':'Vux','T':'Tu','M2':'Muy','M3':'Mux'}
LENGTH_FACTORS = {'m':1.,'mm':.001,'cm':.01,'ft':.3048,'in':.0254}
FORCE_FACTORS = {'kn':1.,'n':.001,'tonf':9.80665,'kip':4.4482216152605}
MOMENT_FACTORS = {'knm':1.,'nmm':1e-6,'nm':.001,'tonfm':9.80665,'kipft':1.3558179483314}
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


def _distance_column(lookup):
    return next((lookup[key] for key in ('girderdistance','layoutlinedistance','distance','station') if key in lookup), None)


def _has_units_row(frame, lookup):
    if frame.empty:
        return False
    first = frame.iloc[0]
    distance = _distance_column(lookup)
    if distance and _key(first.get(distance)) in LENGTH_FACTORS:
        return True
    # Native CSI labels a separate row with Text / Unitless even when a
    # distance unit is unsupported. Keep it out of member grouping, then
    # report its unsupported units rather than silently assuming SI.
    return any(key in lookup and _key(first.get(lookup[key])) in {'text','unitless'}
        for key in ('bridgeobj','girder','sectcutnum','casetype','outputcase'))


def _json_cell(value):
    if _blank(value):
        return None
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


@dataclass
class MemberTable:
    name: str
    frame: pd.DataFrame
    bridge_object: str = ''
    girder: str = ''


def split_member_tables(frame, *, sheet_name):
    """Partition by physical source member, retaining units and source indices.

    Native bridge-object exports put many girders in a single worksheet.
    Existing app-column CSVs may also contain a Girder bank column.
    Worksheets without that column retain the legacy worksheet-as-member route.
    """
    lookup = {_key(c): c for c in frame.columns}
    girder_column = lookup.get('girder')
    if girder_column is None:
        return [MemberTable(str(sheet_name), frame.copy(deep=True))]
    bridge_column = lookup.get('bridgeobj') or lookup.get('bridgeobject')
    has_units = (is_csi_table(frame) or is_native_bridge_table(frame)) and _has_units_row(frame, lookup)
    data = frame.iloc[1:] if has_units else frame
    keys = {}
    for index, row in data.iterrows():
        if all(_blank(v) for v in row):
            continue
        bridge = '' if bridge_column is None or _blank(row.get(bridge_column)) else str(row[bridge_column]).strip()
        girder = '' if _blank(row.get(girder_column)) else str(row[girder_column]).strip()
        keys.setdefault((bridge, girder), []).append(index)
    result = []
    for (bridge, girder), indices in keys.items():
        selected = ([frame.index[0]] if has_units else []) + indices
        part = frame.loc[selected].copy(deep=True)
        part.attrs = dict(frame.attrs)
        name = ' / '.join(v for v in (bridge, girder or '[missing Girder]') if v)
        result.append(MemberTable(name, part, bridge, girder))
    return result

def is_csi_table(frame):
    keys={_key(c) for c in frame.columns}
    return {'p','v2','v3','t','m2','m3'}<=keys and bool(keys & {'girderdistance','layoutlinedistance','distance','station'})

def is_native_bridge_table(frame):
    """Recognize incomplete native exports before app-column alias mapping."""
    keys={_key(c) for c in frame.columns}
    return ('bridgeobjectgirderforces' in _key(frame.attrs.get('source_table',''))
        or bool(keys & {'bridgeobj','bridgeobject'} and keys & {'girder','loctype','sectcutnum'}))

def is_app_table(frame):
    keys={_key(c) for c in frame.columns}
    return bool(keys & {'casename','comboname','loadcase','outputcase','case','name'}) and bool(
        keys & {'stationxm','stationsm','station','s','sm','distance','distancem','x','xm','location','locationm'}) and bool(
        keys & {'mux','mx','muy','my','vuy','vy','vux','vx','nu','p','n','tu','t',
            'momentx','momenty','shearx','sheary','axial','axialforce','torsion'})

def read_tables(payload: bytes, filename: str):
    """Read worksheet headers explicitly; do not silently use the bridge-total sheet."""
    if filename.casefold().endswith('.csv'):
        records = list(csv.reader(payload.decode('utf-8-sig').splitlines(keepends=True)))
        # A native TABLE title has fewer cells than the header/data records.
        # csv.reader preserves those records without pandas inferring a width
        # from the first title row and rejecting the actual table.
        raw = {'CSV': pd.DataFrame(records)}
    else:
        raw = pd.read_excel(BytesIO(payload), sheet_name=None, header=None)
    tables={}
    for name,grid in raw.items():
        for i in range(min(25,len(grid))):
            header=grid.iloc[i].tolist()
            keys={_key(c) for c in header if not _blank(c)}
            probe=pd.DataFrame(columns=[c for c in header if not _blank(c)])
            if {'p','v2','v3','t','m2','m3'}<=keys or is_app_table(probe) or is_native_bridge_table(probe):
                frame=grid.iloc[i+1:].copy()
                frame.columns=[str(c).strip() if not _blank(c) else f'Unnamed {j}' for j,c in enumerate(header)]
                frame.attrs['header_row']=i+1
                frame.attrs['source_sheet']=str(name)
                frame.attrs['source_sha256']=hashlib.sha256(payload).hexdigest()
                frame.attrs['source_table']=next((str(v).strip() for row in grid.iloc[:i].values
                    for v in row if not _blank(v) and str(v).strip().upper().startswith('TABLE:')), '')
                tables[name]=frame
                break
    return tables

@dataclass
class CsiImport:
    frame: pd.DataFrame
    errors: list[str]
    audit: pd.DataFrame
    counts: dict

def prepare_csi_table(frame, *, sheet_name, case_name='ENV_ULS', source_name='',
                      source_mode='unverified', concurrency_confirmed=False, evidence='', allow_blank_step=False):
    lookup={_key(c):c for c in frame.columns}
    if len(lookup) != len(frame.columns):
        return CsiImport(pd.DataFrame(columns=APP_COLUMNS),['Duplicate column names in CSI table.'],pd.DataFrame(),{})
    distance=_distance_column(lookup)
    required={c:lookup.get(_key(c)) for c in FORCE_MAP}
    errors=[]
    if not distance or any(c is None for c in required.values()):
        return CsiImport(pd.DataFrame(columns=APP_COLUMNS),['CSI table requires a distance column and P, V2, V3, T, M2, M3.'],pd.DataFrame(),{})
    step_column=lookup.get('steptype') or lookup.get('itemtype')
    output_column=lookup.get('outputcase') or lookup.get('casename')
    girder_column=lookup.get('girder')
    bridge_column=lookup.get('bridgeobj') or lookup.get('bridgeobject')
    location_column=lookup.get('loctype')
    section_cut_column=lookup.get('sectcutnum')
    case_type_column=lookup.get('casetype')
    native_bridge_table = is_native_bridge_table(frame)
    if native_bridge_table:
        native_columns = [('BridgeObj',bridge_column),('Girder',girder_column),
            ('SectCutNum',section_cut_column),('LocType',location_column),
            ('OutputCase',output_column),('CaseType',case_type_column),
            ('StepType',lookup.get('steptype'))]
        missing = [name for name,column in native_columns if column is None]
        if missing:
            return CsiImport(pd.DataFrame(columns=APP_COLUMNS),
                [f'{sheet_name}: native Bridge Object Girder Forces is missing '+', '.join(missing)+'.'],pd.DataFrame(),{})
    step_number_column=lookup.get('stepnum') or lookup.get('stepnumber') or lookup.get('time')
    control_column=lookup.get('correspondence') or lookup.get('controllingresponse')
    rows=[]; audit=[]; occurrences={}; counts={}; unit_factors={c:1.0 for c in required}
    length_factor=1.0
    data=frame.copy(deep=True)
    source_units={str(distance):'m', **{str(col):'kN' if f in {'P','V2','V3'} else 'kN-m' for f,col in required.items()}}
    units_basis='Legacy SI table without a units row'
    if _has_units_row(data, lookup):
        first=data.iloc[0]
        # A CSI units row is textual in the distance field. Validate all units;
        # never convert an unknown unit or malformed data row into zero.
        dunit=_key(first.get(distance))
        if dunit not in LENGTH_FACTORS:
            errors.append(f'{sheet_name}: unsupported distance unit {first.get(distance)!r}.')
        else:
            length_factor=LENGTH_FACTORS[dunit]
        source_units={str(c):_json_cell(first.get(c)) for c in frame.columns}
        units_basis='Declared CSI units row'
        for field,col in required.items():
            units = FORCE_FACTORS if field in {'P','V2','V3'} else MOMENT_FACTORS
            unit=_key(first.get(col))
            if unit not in units:
                errors.append(f'{sheet_name}: unsupported unit {first.get(col)!r} for {field}.')
            else:
                unit_factors[field]=units[unit]
        data=data.iloc[1:]
    elif native_bridge_table:
        errors.append(f'{sheet_name}: native Bridge Object Girder Forces requires the declared units row.')
    member_keys=set()
    for _,raw in data.iterrows():
        if all(_blank(v) for v in raw):
            continue
        member_keys.add(tuple('' if c is None or _blank(raw.get(c)) else str(raw[c]).strip()
            for c in (bridge_column,girder_column)))
    if len(member_keys)>1:
        return CsiImport(pd.DataFrame(columns=APP_COLUMNS),
            [*errors,f'{sheet_name}: multiple BridgeObj / Girder members. Split by physical member before mapping forces.'],pd.DataFrame(),{})
    for index,raw in data.iterrows():
        if all(_blank(value) for value in raw):
            continue
        excel_row=int(index)+1  # read_tables retains the original zero-based row index
        member_fields={name:('' if col is None or _blank(raw.get(col)) else str(raw[col]).strip())
            for name,col in [('bridge_object',bridge_column),('girder',girder_column),
                ('location_type',location_column),('case_type',case_type_column)]}
        incomplete=False
        for field,col in [('BridgeObj',bridge_column),('Girder',girder_column),
                ('LocType',location_column),('SectCutNum',section_cut_column),('CaseType',case_type_column),
                ('StepType',lookup.get('steptype') if native_bridge_table else None)]:
            if col is not None and _blank(raw.get(col)) and not (field == 'StepType' and allow_blank_step):
                errors.append(f'{sheet_name} row {excel_row}: missing {field} source identity.')
                incomplete=True
        if girder_column is not None and output_column is not None and _blank(raw.get(output_column)):
            errors.append(f'{sheet_name} row {excel_row}: missing OutputCase source identity.')
            incomplete=True
        if incomplete:
            continue
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
        step_number = str(raw.get(step_number_column)).strip() if step_number_column and not _blank(raw.get(step_number_column)) else ''
        control = str(raw.get(control_column)).strip() if control_column and not _blank(raw.get(control_column)) else ''
        identity=(member_fields['bridge_object'],member_fields['girder'],base,
            member_fields['case_type'],step,step_number,control,member_fields['location_type'],x)
        occurrence=occurrences.get(identity,0)+1
        occurrences[identity]=occurrence
        # Distinguish repeated source rows without assuming Before/After labels.
        # A set is just occurrence order at each source station, not a FEA case.
        identity_label = ' / '.join(v for v in (source_name,member_fields['bridge_object'],
            member_fields['girder'],base,member_fields['case_type'],sheet_name,step,member_fields['location_type'],
            ('step '+step_number) if step_number else '', ('control '+control) if control else '') if v)
        case=f'{identity_label} / set {occurrence}'
        verified = bool(concurrency_confirmed and str(evidence).strip()) and (
            source_mode == 'correspondence' or (source_mode == 'static' and step not in {'Max','Min'}))
        source={'schema':VERSION,'sheet':str(sheet_name),'row':excel_row,'case':base,
            'step':step,'occurrence':occurrence,'distance_column':str(distance),
            'kind':'CONCURRENT' if verified else ('ENVELOPE' if step in {'Max','Min'} else 'UNVERIFIED'),
            'source_file':source_name, 'source_mode':source_mode, 'concurrency_confirmed':verified,
            'evidence':str(evidence).strip(), 'step_number':step_number, 'control':control,
            'layout_distance':None if 'layoutlinedistance' not in lookup or _blank(raw.get(lookup['layoutlinedistance'])) else str(raw.get(lookup['layoutlinedistance']))}
        original={str(c):_json_cell(raw.get(c)) for c in frame.columns}
        source.update({**member_fields,
            'section_cut':None if section_cut_column is None else _json_cell(raw.get(section_cut_column)),
            'raw_fields':original,'units':source_units,'units_basis':units_basis,
            'length_factor_to_m':length_factor,'force_factors_to_kN_kNm':unit_factors,
            'source_sha256':str(frame.attrs.get('source_sha256') or ''),
            'table':str(frame.attrs.get('source_table') or ''),'header_row':frame.attrs.get('header_row')})
        note=SOURCE_TAG+json.dumps(source,ensure_ascii=False,separators=(',',':'))
        rows.append({'Active':True,'Station x (m)':x,'Case Name':case,
            **{target:values[field] for field,target in FORCE_MAP.items()},'Note':note})
        audit.append({**original,'Source sheet':sheet_name,'Excel row':excel_row,'Source StepType':step,'Row set':occurrence,
            'Station x (m)':x,'Case Name':case,
            **{target:values[field] for field,target in FORCE_MAP.items()},
            'Distance unit':source_units.get(str(distance)),
            **{f'{field} unit':source_units.get(str(col)) for field,col in required.items()},
            'Source coupling':source['kind'],'Source SHA256':source['source_sha256']})
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
        for member in split_member_tables(frame,sheet_name=name):
            imported=prepare_csi_table(member.frame,sheet_name=name)
            if imported.errors or imported.frame.empty:
                continue
            r={'Girder':member.name,'Rows':len(imported.frame),'Max rows':imported.counts.get('Max',0),'Min rows':imported.counts.get('Min',0)}
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
    formatted_rows={}
    source_rows=[row for _,row in source.iterrows()]
    for (case,x),source_row in original_rows.items():
        formatted_rows.setdefault((case,f'{x:.3f} m'),[]).append(source_row)
    for i,row in result.iterrows():
        info=sources.get(str(row.get('Case')))
        if info is None:
            continue
        result.at[i,'Source ItemType']=info.get('step','UNKNOWN')
        result.at[i,'Source sheet']=info.get('sheet','UNKNOWN')
        result.at[i,'Source row set']=info.get('occurrence')
        # Strength producers use Governing x; flexure uses Station x (m).
        # Both are physical member stations. Supplemental interpolated rows
        # without an exact source match retain only the series-level basis.
        station=row.get('Station x (m)',row.get('Governing x',float('nan')))
        try:
            exact_row=original_rows.get((str(row.get('Case')),_number(station)))
        except (ValueError,TypeError):
            exact_row=None
        if exact_row is None and 'Station x (m)' not in result.columns:
            # Existing strength tables display rounded metres. Only physical
            # LOAD STATION rows can use that label for source matching; a
            # nearby interpolated critical row must never inherit a source cut.
            kind=str(row.get('Station type') or 'LOAD STATION').upper()
            case=str(row.get('Case'))
            label=str(station).strip()
            if kind == 'LOAD STATION':
                ordinal=row.get('Source row')
                try:
                    number=_number(ordinal)
                    candidate=source_rows[int(number)] if number.is_integer() and 0<=number<len(source_rows) else None
                except (ValueError,TypeError):
                    candidate=None
                if candidate is not None and str(candidate.get('Case Name')) == case and f'{float(candidate.get("Station x (m)")):.3f} m' == label:
                    exact_row=candidate
                else:
                    candidates=formatted_rows.get((case,label),[])
                    if len(candidates)==1:
                        exact_row=candidates[0]
        if exact_row is not None:
            exact=source_info(exact_row)
            result.at[i,'Source Excel row']=exact.get('row')
            result.at[i,'Source station x (m)']=float(exact_row.get('Station x (m)'))
            for field,label in [('bridge_object','BridgeObj'),('girder','Girder'),
                    ('section_cut','SectCutNum'),('location_type','LocType'),('case_type','CaseType')]:
                if field in exact:
                    result.at[i,'Source '+label]=exact[field]
            result.at[i,'Source OutputCase']=exact.get('case','')
            result.at[i,'Source StepType']=exact.get('step','')
            if exact.get('source_sha256'):
                result.at[i,'Source SHA256']=exact['source_sha256']
            for field in ('Mux','Vuy','Tu','Muy','Vux','Nu'):
                unit='kN-m' if field in {'Mux','Tu','Muy'} else 'kN'
                from concrete_pmm_pro.io.csi_force_reference import RUNTIME_KEY, ULS_MAP, trace_columns
                reference = exact_row.get(RUNTIME_KEY)
                raw_field = next(f for f, target in ULS_MAP.items() if target == field)
                original = reference['original_actions'][raw_field] if isinstance(reference, dict) else exact_row.get(field)
                result.at[i,f'Source {field} {unit}']=float(original)
            for field, value in trace_columns(exact_row).items():
                if field not in result:
                    result[field] = None
                result.at[i,field] = value
        result.at[i,'Source file']=info.get('source_file','')
        if info.get('kind') == 'CONCURRENT' and info.get('concurrency_confirmed') and info.get('evidence'):
            result.at[i,'Source coupling']='CONCURRENT — DECLARED'
            result.at[i,'Concurrency basis']=info['evidence']
            continue
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


def tag_app_source(frame, *, source_name, sheet_name, source_mode='unverified',
                   concurrency_confirmed=False, evidence=''):
    """Keep legacy tags; untagged app-column uploads need a recorded vector basis."""
    result=frame.copy(deep=True)
    for i,row in result.iterrows():
        existing=source_info(row)
        if existing is not None:
            continue  # Renaming an existing bound cannot promote its acceptance.
        case=str(row.get('Case Name') or '')
        bound=bool(re.search(r'(?:^|[/ _])(?:max|min)(?:$|[/ _])',case,re.I))
        verified=bool(concurrency_confirmed and str(evidence).strip()) and (
            source_mode=='correspondence' or (source_mode=='static' and not bound))
        info={'schema':VERSION,'kind':'CONCURRENT' if verified else ('ENVELOPE' if bound else 'UNVERIFIED'),
            'source_file':source_name,'sheet':sheet_name,'case':case,'step':'App','source_mode':source_mode,
            'concurrency_confirmed':verified,'evidence':str(evidence).strip(),'row':int(i)+1}
        result.at[i,'Note']=SOURCE_TAG+json.dumps(info,separators=(',',':'))+' '+str(row.get('Note') or '')
    return result
