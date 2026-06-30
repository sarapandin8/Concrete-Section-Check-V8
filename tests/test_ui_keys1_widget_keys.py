from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

_WIDGETS_REQUIRING_EXPLICIT_KEYS = {"button", "download_button"}
_SOURCE_PATHS = [Path("app.py"), *Path("concrete_pmm_pro/ui").glob("*.py")]


def _widget_calls() -> list[tuple[Path, ast.Call]]:
    calls: list[tuple[Path, ast.Call]] = []
    for path in _SOURCE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _WIDGETS_REQUIRING_EXPLICIT_KEYS:
                    calls.append((path, node))
    return calls


def _key_keyword(call: ast.Call) -> ast.keyword | None:
    return next((keyword for keyword in call.keywords if keyword.arg == "key"), None)


def test_buttons_and_download_buttons_have_explicit_keys() -> None:
    missing = [f"{path}:{call.lineno}:{call.func.attr}" for path, call in _widget_calls() if _key_keyword(call) is None]

    assert missing == []


def test_literal_button_and_download_keys_are_unique() -> None:
    key_locations: dict[str, list[str]] = defaultdict(list)
    for path, call in _widget_calls():
        key_keyword = _key_keyword(call)
        assert key_keyword is not None
        value = key_keyword.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            key_locations[value.value].append(f"{path}:{call.lineno}:{call.func.attr}")

    duplicates = {key: locations for key, locations in key_locations.items() if len(locations) > 1}
    assert duplicates == {}
