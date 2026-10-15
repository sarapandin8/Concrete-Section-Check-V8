"""Input-only CSI component collection, captured by the existing ULS import.

This is source data, not fitted origins, joint actions or strength results.
Component envelopes remain envelopes even when a Girder row has a declared
correspondence contract. Matching three component states requires more than
the presence of three worksheets.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path

import pandas as pd

from .girder_csi_import import is_csi_table, prepare_csi_table, read_tables, source_info, split_member_tables
from concrete_pmm_pro.analysis.csi_component_equilibrium import _component

KEY = "csi_component_force_sources"
VERSION = "IGIRDER.INPUT30.component-inputs"
MAX_ROWS = 100_000


def missing_named_tables(payload, filename, parsed_tables):
    """Recognized component sheets with broken headers must not disappear."""
    if str(filename).casefold().endswith('.csv'):
        return []
    with pd.ExcelFile(BytesIO(payload)) as book:
        return [(name, identity[0]) for name in book.sheet_names
            if (identity := _component(name)) is not None and name not in parsed_tables]


def capture(payload: bytes, filename: str, *, source_mode="unverified",
            concurrency_confirmed=False, evidence="") -> dict:
    """Normalize all supported component rows without changing the load bank.

    A malformed component table invalidates this complete source collection;
    the ordinary Girder importer still owns its own import eligibility.
    """
    digest = hashlib.sha256(payload).hexdigest()
    errors, records = [], []
    parsed_tables=read_tables(payload, filename)
    errors.extend(name+": component force headers could not be identified" for name,_ in
        missing_named_tables(payload,filename,parsed_tables))
    for sheet, table in parsed_tables.items():
        if not is_csi_table(table):
            continue
        for member in split_member_tables(table, sheet_name=sheet):
            identity = _component(member.girder or sheet)
            if identity is None:
                continue
            kind, family, label = identity
            parsed = prepare_csi_table(member.frame, sheet_name=sheet,
                case_name=Path(filename).stem, source_name=filename + " [" + digest[:8] + "]",
                source_mode=source_mode, concurrency_confirmed=concurrency_confirmed, evidence=evidence)
            errors.extend(parsed.errors)
            for row in json.loads(parsed.frame.to_json(orient="records", double_precision=15)):
                records.append({"component": kind, "family": family, "member": label,
                    "bridge": member.bridge_object, "sheet": sheet, **row})
                if len(records) > MAX_ROWS:
                    errors.append(f"Component source exceeds {MAX_ROWS:,} rows; retain the original export separately.")
                    return {"filename": filename, "sha256": digest, "records": [], "errors": errors}
    # Girder-only exports are ordinary Loads files, not component bundles.
    if not any(row["component"] in {"beam", "slab"} for row in records):
        records = []
    return {"filename": filename, "sha256": digest, "records": [] if errors else records,
        "errors": list(dict.fromkeys(errors))}


def collection(sources) -> dict:
    """Keep one ordered input dataset per byte identity; never merge cases."""
    positions, retained = {}, []
    for source in sources:
        if source.get("records") or source.get("errors"):
            if source["sha256"] in positions:
                retained[positions[source["sha256"]]]=deepcopy(source)
            else:
                positions[source["sha256"]]=len(retained)
                retained.append(deepcopy(source))
    return {"version": VERSION, "sources": retained}


def saved(state: Mapping) -> dict:
    metadata = state.get("project_metadata") or {}
    raw = metadata.get(KEY, {}) if isinstance(metadata, Mapping) else {}
    if not isinstance(raw, Mapping) or raw.get("version") != VERSION:
        return {"version": VERSION, "sources": []}
    return deepcopy(dict(raw))


def overview(bundle: Mapping, *, active_loads=None) -> list[dict]:
    """Report what is available; do not assert vector sums or force origins."""
    active_hashes = set()
    for row in pd.DataFrame(active_loads if active_loads is not None else []).to_dict("records"):
        info = source_info(row) or {}
        if info.get("source_sha256"):
            active_hashes.add(info["source_sha256"])
    result = []
    for source in bundle.get("sources", []):
        groups = {}
        for row in source.get("records", []):
            info = source_info(row) or {}
            key = (row.get("bridge", ""), row.get("member", ""), str(info.get("case", "")))
            group = groups.setdefault(key, {"parts": set(), "rows": 0, "static": True, "states": set()})
            group["parts"].add(row.get("component"))
            group["rows"] += 1
            step = str(info.get("step", "")).casefold()
            single = (info.get("source_mode") == "static" and info.get("kind") == "CONCURRENT"
                and step not in {"max", "min"} and (step == "static" or bool(info.get("step_number"))))
            group["static"] = group["static"] and single
            group["states"].add((step, str(info.get("step_number", "")), str(info.get("control", ""))))
        for (bridge, member, case), group in groups.items():
            parts = group["parts"]
            complete = parts == {"girder", "beam", "slab"}
            single = group["static"] and len(group["states"]) == 1
            result.append({"File": source["filename"], "Bridge": bridge, "Girder": member,
                "Case": case, "Components": " / ".join(p.title() for p in ("girder", "beam", "slab") if p in parts),
                "Rows": group["rows"], "Input state": "Single-state source" if single else "State pairing required",
                "Complete components": complete, "Matches active Loads file": source["sha256"] in active_hashes,
                "Use": "Source inputs only — origins / component cuts / external loads still require a model"})
        if source.get("errors"):
            result.append({"File": source["filename"], "Rows": 0, "Input state": "Source incomplete",
                "Complete components": False, "Matches active Loads file": source["sha256"] in active_hashes,
                "Use": "; ".join(source["errors"])})
    return result


def fingerprint(bundle: Mapping) -> str:
    return hashlib.sha256(json.dumps(bundle, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
