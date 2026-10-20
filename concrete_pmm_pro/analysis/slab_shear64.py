"""Reuse accepted AASHTO63 checks and add explicit punching areas."""
import hashlib,json
from concrete_pmm_pro.analysis import slab_aashto63 as base
from concrete_pmm_pro.analysis import slab_punching64 as punching

VERSION='SLAB.SHEAR64'
RESULT_KEY='slab_shell55_shear64_result'
VIEWS=base.VIEWS
AXES=base.AXES


def fingerprint(state):
    original=base.fingerprint(state)
    if original is None:return None
    return hashlib.sha256(json.dumps({'version':VERSION,'base':original,'punching':punching.signature(state)},sort_keys=True).encode()).hexdigest()


def current(state):
    result=state.get(RESULT_KEY)
    try:valid=isinstance(result,dict) and result.get('fingerprint')==fingerprint(state) and result.get('version')==VERSION
    except ValueError:return None
    return result if valid else None


def calculate(state,*,progress=None,reuse=None):
    accepted=reuse if isinstance(reuse,dict) and reuse.get('version')==base.VERSION and reuse.get('fingerprint')==base.fingerprint(state) else None
    if accepted is None:accepted=base.calculate(state,progress=progress)
    if progress:progress(.93,'Checking loaded-area punching perimeters…')
    p=punching.calculate(accepted,punching.config(state))
    return {**accepted,'version':VERSION,'fingerprint':fingerprint(state),'base_result':accepted,
        'punching':p,'status':'REVIEW REQUIRED','base_reused':reuse is accepted,
        'scope':'AASHTO LRFD 2020 component checks: existing one-way shear and reinforcement checks, plus isolated rectangular loaded-area punching normal force (5.12.8.6). Punching moment transfer, local support paths and full shell interaction remain separate. No missing patch or demand is invented; overall deck acceptance remains REVIEW REQUIRED.'}


def map_adapter(result,view):
    return base.map_adapter(result,view)
