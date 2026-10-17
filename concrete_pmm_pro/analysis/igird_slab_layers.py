"""COVER38 physical slab layering; no resistance or engineering acceptance.

Each mat has transverse steel outside and longitudinal steel directly inside.
Crossed bars touch: c_long = c_trans + db_trans. Actual size/cover remain
inputs; unknown positions never become zero cover. Pure resolution is shared
by input views, analysis and JSON snapshots without running any solver.
"""
from collections.abc import Mapping
from copy import deepcopy
import math

VERSION='IGIRDER.COVER38'
RULE='transverse_outer_longitudinal_inner'
INTERFACE_KEY='beam_girder_interface_shear_settings'
ORDER_KEY='slab_layer_order'
PARAM_ORDER='deck_slab_layer_order'


def number(value):
    try:n=float(value) if not isinstance(value,bool) else float('nan')
    except (ValueError,TypeError):return None
    return n if math.isfinite(n) else None


def detail_from_state(state):
    raw=state.get(INTERFACE_KEY)
    if not isinstance(raw,Mapping):raw=(state.get('project_metadata') or {}).get(INTERFACE_KEY,{})
    return deepcopy(dict(raw.get('dowel_connection') or {})) if isinstance(raw,Mapping) else {}


def resolve(params,cfg=None):
    """Return effective parameters and explicit mat-centre coordinates.

    Stored cover snapshots never override the current transverse inputs.
    Coordinates in the ledger are depths below the slab TOP surface.
    """
    out=deepcopy(dict(params or {}));cfg=dict(cfg or {})
    active=cfg.get(ORDER_KEY)==RULE or out.get(PARAM_ORDER)==RULE
    if not active:return {'active':False,'parameters':out,'rows':[],'issues':[],'ready':True}
    out[PARAM_ORDER]=RULE;mesh=cfg.get('slab_transverse_mesh');explicit=isinstance(mesh,Mapping)
    rows=[];issues=[];t=number(out.get('Tslab_mm'));edges={}
    for face in ('top','bottom'):
        row=dict(mesh.get(face) or {}) if explicit else {}
        dt=number(row.get('Diameter_mm')) if explicit else number(out.get(f'deck_mesh_{face}_transverse_diameter_mm'))
        ct=number(row.get('Clear_cover_mm')) if explicit else number(out.get(f'deck_mesh_{face}_transverse_cover_mm'))
        dl=number(out.get(f'deck_long_rebar_{face}_diameter_mm'))
        out[f'deck_mesh_{face}_transverse_diameter_mm']=dt
        out[f'deck_mesh_{face}_transverse_cover_mm']=ct
        known=dt is not None and dt>0 and ct is not None and ct>=0
        cl=ct+dt if known else None
        out[f'deck_long_rebar_{face}_cover_mm']=cl
        trans=ct+dt/2 if known else None
        long=cl+dl/2 if known and dl is not None and dl>0 else None
        if not known:issues.append(face.title()+' slab transverse diameter / clear cover is missing; longitudinal position is unavailable.')
        if dl is not None and dl>0 and known:edges[face]=cl+dl
        elif known:edges[face]=ct+dt
        def depth(distance):
            return distance if face=='top' else t-distance if t is not None and distance is not None else None
        rows.append({'Layer':face.title(),'Transverse diameter (mm)':dt,'Input transverse cover (mm)':ct,
            'Longitudinal diameter (mm)':dl,'Auto longitudinal cover (mm)':cl,
            'Transverse centre below top (mm)':depth(trans),'Longitudinal centre below top (mm)':depth(long),
            'Layer order':'Transverse outside; longitudinal inside','Crossing clear gap (mm)':0. if long is not None else None})
    gap=t-sum(edges.values()) if t is not None and len(edges)==2 else None
    out['deck_mesh_inner_clear_gap_mm']=gap
    if t is None or t<=0:issues.append('Positive slab thickness is required for layer positions.')
    elif gap is not None and gap<0:issues.append('Top and bottom slab mats overlap through the slab thickness; revise physical size / cover / thickness.')
    for face,edge in edges.items():
        if t is not None and edge>=t:issues.append(face.title()+' slab mat does not fit the slab thickness.')
    return {'active':True,'parameters':out,'rows':rows,'issues':issues,'ready':not issues,
        'inner_clear_gap_mm':gap,'basis':'Crossed bars touch; no added interlayer gap. Geometry only, not code minimum-cover / anchorage acceptance.'}


def parameters(state,raw=None):
    return resolve(raw if raw is not None else state.get('section_parameters',{}),detail_from_state(state))['parameters']


def adopt(state,*,cfg=None,migrate=False):
    """Explicit input/load transaction. Never called by result review pages.

    Old complete mesh inputs adopt the requested new order on project load.
    Other presets and projects without a transverse mesh retain their layout.
    Prior longitudinal covers are retained as input provenance, not results.
    """
    params=dict(state.get('section_parameters') or {})
    if str(state.get('section_preset_key') or '')!='parametric_i_girder':return cfg
    current=deepcopy(cfg) if cfg is not None else detail_from_state(state)
    mesh=current.get('slab_transverse_mesh')
    if current.get(ORDER_KEY)!=RULE:
        if migrate and not (isinstance(mesh,Mapping) and any(isinstance(v,Mapping) and v for v in mesh.values())):return current
        current[ORDER_KEY]=RULE
        current.setdefault('layer_order_previous_longitudinal_covers_mm',
            {face:params.get(f'deck_long_rebar_{face}_cover_mm') for face in ('top','bottom')})
    resolved=resolve(params,current)
    state['section_parameters']=resolved['parameters']
    if cfg is None:
        raw=state.get(INTERFACE_KEY)
        if not isinstance(raw,Mapping):raw=(state.get('project_metadata') or {}).get(INTERFACE_KEY,{})
        interface={**dict(raw or {}),'dowel_connection':current}
        state[INTERFACE_KEY]=interface
        state['project_metadata']={**dict(state.get('project_metadata') or {}),INTERFACE_KEY:interface}
    return current
