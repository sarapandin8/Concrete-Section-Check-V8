"""Full-content SHA256 for report currency, without scalar JSON encoding.

Numeric columns are hashed as bounded byte blocks. Object columns use bounded
pickle *encoding only* (never loading untrusted pickle). This includes every
cell, index, dtype and column identity. The per-call memo is discarded after
each signature: in-place edits must invalidate the next export check.
"""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from hashlib import sha256
import pickle
import struct

import numpy as np
import pandas as pd

from .source_stream import checkpoint

SCHEME = 'REPORT.COMPACT87/full-content-v1'
BLOCK_ROWS = 8192


def source_digest(value):
    memo = {}
    active = set()

    def digest(obj):
        cacheable = isinstance(obj, (pd.DataFrame, pd.Index)) or (
            is_dataclass(obj) and not isinstance(obj, type))
        key = id(obj)
        if cacheable and key in memo:
            return memo[key][1]
        if key in active:
            raise ValueError('Cyclic report source cannot be fingerprinted')
        active.add(key)
        h = sha256()

        def feed(tag, data=b''):
            h.update(tag)
            h.update(struct.pack('>Q', len(data)))
            h.update(data)

        try:
            if isinstance(obj, pd.DataFrame):
                feed(b'frame', digest(list(obj.columns)))
                feed(b'index', digest(obj.index))
                for i in range(obj.shape[1]):
                    checkpoint(f'Verifying full source table: {len(obj):,} rows, column {i+1}/{obj.shape[1]}', throttle=True)
                    feed(b'column', digest(obj.iloc[:, i]))
            elif isinstance(obj, (pd.Series, pd.Index)):
                feed(b'series' if isinstance(obj, pd.Series) else b'index', str(obj.dtype).encode())
                feed(b'name', digest(obj.name if not isinstance(obj, pd.MultiIndex) else obj.names))
                if isinstance(obj, pd.Series):
                    feed(b'index', digest(obj.index))
                if isinstance(obj.dtype, pd.CategoricalDtype):
                    feed(b'categories', digest(obj.dtype.categories))
                    feed(b'ordered', digest(obj.dtype.ordered))
                for start in range(0, len(obj), BLOCK_ROWS):
                    checkpoint()
                    block = obj.iloc[start:start+BLOCK_ROWS] if isinstance(obj, pd.Series) else obj[start:start+BLOCK_ROWS]
                    feed(b'block', digest(block.to_numpy()))
            elif isinstance(obj, np.ndarray):
                feed(b'array', repr((obj.shape, obj.dtype.str, obj.dtype.descr)).encode())
                # flat slicing bounds the extra allocation even for strided arrays.
                size = max(1, 1024*1024 // max(1, obj.dtype.itemsize))
                for start in range(0, obj.size, size if not obj.dtype.hasobject else BLOCK_ROWS):
                    checkpoint()
                    stop = start + (size if not obj.dtype.hasobject else BLOCK_ROWS)
                    block = obj.flat[start:stop]
                    feed(b'objects' if obj.dtype.hasobject else b'bytes',
                         pickle.dumps(block.tolist(), protocol=5) if obj.dtype.hasobject else block.tobytes())
            elif hasattr(obj, 'model_dump'):
                feed(b'model', digest(obj.model_dump(mode='json')))
            elif is_dataclass(obj) and not isinstance(obj, type):
                feed(b'dataclass', digest({f.name: getattr(obj, f.name) for f in fields(obj)}))
            elif isinstance(obj, Mapping):
                feed(b'mapping', str(len(obj)).encode())
                # Sort by typed key digest; do not collapse 1 and '1'.
                for kd, item in sorted(((digest(k), v) for k, v in obj.items()), key=lambda pair: pair[0]):
                    feed(b'key', kd)
                    feed(b'value', digest(item))
            elif isinstance(obj, (list, tuple)):
                feed(b'list' if isinstance(obj, list) else b'tuple', str(len(obj)).encode())
                for i, item in enumerate(obj):
                    if i % BLOCK_ROWS == 0:
                        checkpoint()
                    feed(b'item', digest(item))
            elif isinstance(obj, (bytes, bytearray, memoryview)):
                feed(b'blob', str(len(obj)).encode())
                for start in range(0, len(obj), 1024*1024):
                    checkpoint()
                    feed(b'block', obj[start:start+1024*1024])
            else:
                feed(b'scalar', pickle.dumps(obj, protocol=5))
            result = h.digest()
            if cacheable:
                memo[key] = (obj, result)  # retain object; prevent recycled ids
            return result
        finally:
            active.remove(key)

    return sha256(SCHEME.encode() + digest(value)).hexdigest()
