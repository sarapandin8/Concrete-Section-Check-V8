"""Portable, input-only slab shell tables inside a Project JSON.

The archive stores parsed CSI values at Python's round-trip float precision.
It contains no resistance results, reports, figures or uploaded workbook bytes.
"""
from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import date, datetime, time
import gzip
import hashlib
import json
import math
import re
import zlib

import numpy as np
import pandas as pd

from concrete_pmm_pro.io import slab_shell_import as source

VERSION = "SLAB.PROJECT74"
METADATA_KEY = "slab_shell_inputs74"
RESTORED_KEY = "slab_shell55_restored_from_project"
SCHEMA = "csp.slab-shell-inputs/1"
MAX_RAW_BYTES = 256 * 1024 * 1024
_DTYPES = {"object", "bool", "string", "str", "datetime64[ns]", "datetime64[us]"}
_DTYPES.update(f"{kind}{bits}" for kind in ("int", "uint", "float") for bits in (8, 16, 32, 64))


def _cell(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    for kind, cls in (("timestamp", pd.Timestamp), ("datetime", datetime), ("date", date), ("time", time)):
        if isinstance(value, cls):
            return {"$type": kind, "value": value.isoformat()}
    raise ValueError("Unsupported cell type in slab shell input tables")


def _object(value):
    if set(value) == {"$type", "value"}:
        converters = {"timestamp": pd.Timestamp, "datetime": datetime.fromisoformat,
            "date": date.fromisoformat, "time": time.fromisoformat}
        if value["$type"] in converters:
            return converters[value["$type"]](value["value"])
    return value


def _fingerprint(package):
    """Avoid recompressing an unchanged input bank on every sidebar rerun."""
    digest = hashlib.sha256()
    for name, frame in package.tables.items():
        digest.update(json.dumps([name, list(frame.columns), list(map(str, frame.dtypes))]).encode())
        digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes())
    digest.update(json.dumps([package.units, package.sources, package.notes, package.signature],
        sort_keys=True, ensure_ascii=False, default=_cell, allow_nan=False).encode())
    return digest.hexdigest()


def input_metadata(state):
    """Save the last imported bank; pending file-picker changes are not imports."""
    package = state.get(source.BANK_KEY)
    if not isinstance(package, source.ShellPackage) or not package.ready:
        return None
    fingerprint = _fingerprint(package)
    cached = getattr(package, "_project74_archive", None)
    if cached is not None and cached[0] == fingerprint:
        return deepcopy(cached[1])
    payload = {"tables": {name: {"columns": list(frame.columns),
        "dtypes": list(map(str, frame.dtypes)),
        "data": [[_cell(v) for v in row] for row in frame.itertuples(index=False, name=None)]}
        for name, frame in package.tables.items()},
        "units": package.units, "sources": package.sources, "notes": package.notes,
        "signature": list(package.signature)}
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=_cell).encode()
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("Slab shell input package exceeds the supported Project JSON size")
    archive = {"schema": SCHEMA, "encoding": "gzip+base64", "raw_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "payload": base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode("ascii")}
    package._project74_archive = (fingerprint, deepcopy(archive))
    return archive


def restore(archive):
    """Decode and revalidate inputs before any currently open project is changed."""
    if archive is None:
        return None
    try:
        if not isinstance(archive, dict) or archive.get("schema") != SCHEMA:
            raise ValueError("unsupported schema")
        if archive.get("encoding") != "gzip+base64":
            raise ValueError("unsupported encoding")
        size = archive.get("raw_bytes")
        if type(size) is not int or not 0 < size <= MAX_RAW_BYTES:
            raise ValueError("invalid decoded size")
        encoded = archive.get("payload")
        if not isinstance(encoded, str) or len(encoded) > (MAX_RAW_BYTES + 1024) * 4 // 3:
            raise ValueError("invalid encoded payload")
        compressed = base64.b64decode(encoded, validate=True)
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = decoder.decompress(compressed, size + 1)
        if len(raw) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("truncated or inconsistent compressed data")
        if hashlib.sha256(raw).hexdigest() != archive.get("sha256"):
            raise ValueError("input checksum mismatch")
        payload = json.loads(raw, object_hook=_object)
        if not isinstance(payload, dict) or set(payload) != {"tables", "units", "sources", "notes", "signature"}:
            raise ValueError("invalid input structure")
        tables, units = payload["tables"], payload["units"]
        if not isinstance(tables, dict) or not isinstance(units, dict) or set(tables) != set(units):
            raise ValueError("table/unit correspondence is incomplete")
        specs = {s.key: s for s in (*source.SPECS, *source.OPTIONAL_SPECS)}
        frames = {}
        for name, table in tables.items():
            if name not in specs or not isinstance(table, dict):
                raise ValueError("unrecognized input table")
            columns, dtypes, data = table["columns"], table["dtypes"], table["data"]
            if (not isinstance(columns, list) or not all(isinstance(c, str) and c for c in columns)
                    or len(columns) != len(set(columns)) or not set(specs[name].columns).issubset(columns)):
                raise ValueError(name + ": required columns are missing or repeated")
            if not isinstance(dtypes, list) or len(dtypes) != len(columns) or any(d not in _DTYPES for d in dtypes):
                raise ValueError(name + ": unsupported column types")
            if not isinstance(data, list) or any(not isinstance(row, list) or len(row) != len(columns) for row in data):
                raise ValueError(name + ": malformed records")
            if not isinstance(units[name], dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in units[name].items()):
                raise ValueError(name + ": invalid units")
            frames[name] = pd.DataFrame({c: pd.Series([row[i] for row in data], dtype=dtypes[i])
                for i, c in enumerate(columns)})
        signature = payload["signature"]
        if not isinstance(signature, list) or not signature or any(not isinstance(s, str) or not re.fullmatch("[0-9a-f]{64}", s) for s in signature):
            raise ValueError("missing source workbook identities")
        if not isinstance(payload["sources"], list) or any(not isinstance(s, dict) for s in payload["sources"]):
            raise ValueError("invalid source table inventory")
        if not isinstance(payload["notes"], list) or any(not isinstance(n, str) for n in payload["notes"]):
            raise ValueError("invalid import notes")
        package = source.ShellPackage(tables=frames, units=units, sources=payload["sources"],
            notes=payload["notes"], signature=tuple(signature))
        source._validate(package)
        if not package.ready:
            missing = [s.title for s in package.missing]
            raise ValueError("; ".join(package.errors + missing) or "no slab force records")
        package._project74_archive = (_fingerprint(package), deepcopy(archive))
        return package
    except (ValueError, TypeError, KeyError, AttributeError, binascii.Error, zlib.error, OverflowError) as exc:
        raise ValueError("Saved slab shell inputs are invalid: " + str(exc)) from exc
