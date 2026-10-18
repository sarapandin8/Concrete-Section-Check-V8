"""Bounded per-Calculate response reuse; no interpolation or force rounding."""
from collections import OrderedDict
from .igird_flexure_development import SectionEquilibrium


class CachedSectionEquilibrium(SectionEquilibrium):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._responses=OrderedDict()

    def evaluate(self,c,**limits):
        key=(float(c),tuple((k,None if v is None else tuple(v)) for k,v in sorted(limits.items())))
        if key not in self._responses:
            self._responses[key]=super().evaluate(c,**limits)
            while len(self._responses)>8192:self._responses.popitem(last=False)
        self._responses.move_to_end(key)
        value=dict(self._responses[key])
        value['fps_MPa']=list(value['fps_MPa'])
        return value
