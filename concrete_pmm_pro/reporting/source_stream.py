"""Bounded JSON views of complete report sources, with legacy byte semantics.

Only pass these views to JSONEncoder.iterencode (_one_shot=False). They borrow
source objects for a synchronous read-only export; they are not a result cache.
DataFrames produce one record at a time, and dataclasses are never deep-copied.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields, is_dataclass
import math
from time import monotonic

import numpy as np
import pandas as pd

_PROGRESS = ContextVar('report_source_progress', default=None)


@contextmanager
def preparation_progress(callback):
    token = _PROGRESS.set([callback, 0., 'Preparing stored report sources', .02])
    try:
        yield
    finally:
        _PROGRESS.reset(token)


def checkpoint(message=None, fraction=None, *, throttle=False):
    context = _PROGRESS.get()
    if context is None or context[0] is None:
        return
    now = monotonic()
    if message is not None:
        context[2] = message
    if fraction is not None:
        context[3] = fraction
    if (message is None or throttle) and now-context[1] < 1.:
        return
    context[1] = now
    context[0](context[2], context[3])


class _Sequence(list):
    def __init__(self, source):
        self.source = source

    def __len__(self):
        return len(self.source)

    def __iter__(self):
        for i, value in enumerate(self.source):
            if i % 1024 == 0:
                checkpoint()
            yield plain_view(value)


class _Records(_Sequence):
    def __iter__(self):
        columns = list(self.source.columns)
        for i, row in enumerate(self.source.itertuples(index=False, name=None)):
            if i % 1024 == 0:
                checkpoint()
            # pandas to_dict('records') boxes nullable missing cells as None.
            values = (None if v is pd.NA else v for v in row)
            yield plain_view(dict(zip(columns, values)))


class _Mapping(dict):
    def __init__(self, source):
        self.source = source
        # Preserve the legacy str(key) collision rule: the last value wins.
        self.keys_by_text = {str(key): key for key in source}

    def __len__(self):
        return len(self.keys_by_text)

    def items(self):
        for i, (text, key) in enumerate(self.keys_by_text.items()):
            if i % 1024 == 0:
                checkpoint()
            yield text, plain_view(self.source[key])


def plain_view(value):
    """Same values as igird_sls53_results._plain without eager record lists."""
    if isinstance(value, pd.DataFrame):
        return {'columns': list(value.columns), 'rows': _Records(value)}
    if hasattr(value, 'model_dump'):
        return plain_view(value.model_dump(mode='json'))
    if is_dataclass(value) and not isinstance(value, type):
        return plain_view({field.name: getattr(value, field.name) for field in fields(value)})
    if isinstance(value, Mapping):
        return _Mapping(value)
    if isinstance(value, (list, tuple)):
        return _Sequence(value)
    if isinstance(value, np.generic):
        return plain_view(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is pd.NA:
        return '<NA>'
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)
