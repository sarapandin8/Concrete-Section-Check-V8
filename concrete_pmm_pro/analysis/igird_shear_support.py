"""Physical bearing coordinates; geometry alone never grants a shear exception."""
from collections.abc import Mapping
import math

SETTINGS_KEY = "igird_shear_support_settings"


def support_settings(state):
    raw = state.get(SETTINGS_KEY)
    if not isinstance(raw, Mapping):
        raw = (state.get("project_metadata") or {}).get(SETTINGS_KEY)
    raw = raw if isinstance(raw, Mapping) else {}
    def number(key):
        try:
            value = float(raw.get(key, 0.0))
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and value >= 0 else None
    return {"locations_confirmed": bool(raw.get("locations_confirmed", False)),
        "offset_reference": str(raw.get("offset_reference", "centerline")),
        "left_offset_m": number("left_offset_m"), "right_offset_m": number("right_offset_m"),
        "left_bearing_length_mm": number("left_bearing_length_mm"),
        "right_bearing_length_mm": number("right_bearing_length_mm"),
        "note": str(raw.get("note") or "")}


def support_basis(state, *, span_m):
    """Resolve CL / inside face independently; unknown bearing length stays unknown.

    Article 5.7.3.2 also requires reaction, loading and end-region detailing
    evidence. This release retains every original row, including the overhang
    on the outer side of each bearing; it does not adopt that exception.
    """
    settings = support_settings(state)
    result = {"status": "UNCONFIRMED", "supports": [], "near_support_exception": False,
        "note": "Bearing locations are unconfirmed; physical beam/strand cut ends are not internal support faces."}
    if not settings["locations_confirmed"]:
        return result
    left, right = settings["left_offset_m"], settings["right_offset_m"]
    reference = settings["offset_reference"]
    if not math.isfinite(span_m) or span_m <= 0 or left is None or right is None or left + right >= span_m or reference not in {"centerline", "inside_face"}:
        return {**result, "status": "INVALID", "note": "Bearing offsets/reference are invalid for the physical beam length."}
    supports = []
    for side, position, length, direction in (
        ("Left", left, settings["left_bearing_length_mm"], 1.0),
        ("Right", span_m - right, settings["right_bearing_length_mm"], -1.0),
    ):
        half = length / 2000.0 if length is not None and length > 0 else None
        cl = position if reference == "centerline" else (position - direction * half if half is not None else None)
        face = position if reference == "inside_face" else (position + direction * half if half is not None else None)
        outer = cl - direction * half if cl is not None and half is not None else None
        if any(v is not None and not 0 <= v <= span_m for v in (cl, face, outer)):
            return {**result, "status": "INVALID", "note": "A bearing footprint extends outside the physical beam."}
        supports.append({"side": side, "centerline_x_m": cl, "inside_face_x_m": face,
            "outer_face_x_m": outer, "length_mm": length if half is not None else None})
    if all(s["inside_face_x_m"] is not None for s in supports) and supports[0]["inside_face_x_m"] >= supports[1]["inside_face_x_m"]:
        return {**result, "status": "INVALID", "note": "The internal bearing faces overlap or are reversed."}
    ready = all(s["inside_face_x_m"] is not None for s in supports)
    return {**result, "status": "FACES KNOWN" if ready else "BEARING LENGTH REQUIRED", "supports": supports,
        "note": ("Internal faces are known; supplemental face+dv sections are audit locations. " if ready else
            "The bearing centerlines are known, but the internal faces require the bearing lengths along the beam. ") +
            "Every original force row remains checked; the Article 5.7.3.2 near-support exception is not adopted."}
