"""Recover physical slab thickness, CSI axes and straight-bridge steel directions.

All geometry is reconstructed from the imported native tables. Forces remain
at the shell midsurface; the only transformation is a change of coordinate axes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from concrete_pmm_pro.io.slab_shell_import import ShellPackage


class GeometryError(ValueError):
    pass


def unit(vector):
    vector = np.asarray(vector, dtype=float)
    length = np.linalg.norm(vector)
    if not np.isfinite(length) or length < 1e-10:
        raise GeometryError("Zero or non-finite axis reference vector")
    return vector / length


def inverse_quad(points, point):
    """Invert the bilinear parent map; tolerate CSI's rounded mesh coordinates."""
    points, point = np.asarray(points), np.asarray(point)
    uv = np.array([.5, .5])
    for _ in range(16):
        s, r = uv
        weights = np.array([(1-s)*(1-r), s*(1-r), s*r, (1-s)*r])
        jacobian = np.column_stack(((1-r)*(points[1]-points[0])+r*(points[2]-points[3]),
            (1-s)*(points[3]-points[0])+s*(points[2]-points[1])))
        step = np.linalg.lstsq(jacobian, point-weights@points, rcond=None)[0]
        uv += step
        if np.linalg.norm(step) < 1e-11:
            break
    s, r = uv
    weights = np.array([(1-s)*(1-r), s*(1-r), s*r, (1-s)*r])
    if np.linalg.norm(weights@points-point) > 2e-5 or np.min(uv) < -1e-5 or np.max(uv) > 1+1e-5:
        raise GeometryError("Mesh corner does not lie within its planar parent Area (20 μm export tolerance)")
    return weights


def local_axes(points, typical, advanced, coordinates):
    normal = unit(np.cross(points[1]-points[0], points[3]-points[0]))
    if any(np.dot(np.cross(points[(i+1)%4]-points[i],points[(i+2)%4]-points[(i+1)%4]),normal)<=1e-10 for i in range(4)):
        raise GeometryError("Parent Area must be a convex, consistently ordered quadrilateral")
    if abs(np.dot(points[2]-points[0], normal)) > 2e-5:
        raise GeometryError("Warped parent Areas are outside this planar-shell route")
    if abs(normal[2]) < .9:
        raise GeometryError("Top Slab is not a near-horizontal deck")
    if str(typical.get("AdvanceAxes", "")).casefold() == "yes":
        if advanced is None:
            raise GeometryError("Missing advanced shell axes")
        if str(advanced.get("PlCoordSys", "GLOBAL")).upper() != "GLOBAL":
            raise GeometryError("Advanced axes in non-GLOBAL coordinate systems are not supported")
        option = str(advanced.get("PlOption1", "")).casefold()
        if option == "two joints":
            reference = coordinates[advanced["PlVecJt2"]]-coordinates[advanced["PlVecJt1"]]
        elif option == "user vector":
            reference = np.array([advanced[f"PlVec{c}"] for c in "XYZ"], dtype=float)
        elif option in {"coordinate direction", "coordinate directions"}:
            reference = np.eye(3)["XYZ".index(str(advanced["CoordDir1"]).upper())]
            if np.linalg.norm(np.cross(reference, normal)) < 1e-8:
                reference = np.eye(3)["XYZ".index(str(advanced["CoordDir2"]).upper())]
        else:
            raise GeometryError(f"Unsupported advanced axis option: {option}")
        projected = unit(reference-normal*np.dot(reference, normal))
        plane = str(advanced.get("LocalPlane", "")).replace("-", "")
        if plane == "31":
            e1, e2 = projected, unit(np.cross(normal, projected))
        elif plane == "32":
            e2, e1 = projected, unit(np.cross(projected, normal))
        else:
            raise GeometryError(f"Unsupported shell local plane: {plane}")
    else:
        # CSI's local 2 axis is in the 3-Z plane; horizontal shells use +Y.
        projected = np.array([0., 0., 1.])-normal*normal[2]
        if np.linalg.norm(projected) < 1e-8:
            projected = np.array([0., 1., 0.])
        e2 = unit(projected)
        e1 = unit(np.cross(e2, normal))
    angle = math.radians(float(typical["Angle"]))
    first = math.cos(angle)*e1+math.sin(angle)*e2
    second = -math.sin(angle)*e1+math.cos(angle)*e2
    return first, second, normal


def _station_directions(flags, parents, coordinates):
    """Derive longitudinal direction from bridge station progression, not PCA."""
    needed = {"BridgeObj", "BOSpan", "StartSta", "EndSta"}
    if not needed.issubset(flags.columns):
        raise GeometryError("Bridge flags require BridgeObj, BOSpan, StartSta and EndSta to infer steel directions")
    rows = []
    for row in flags.to_dict("records"):
        area = str(row["Area"])
        p = np.array([coordinates[parents[area][f"Joint{i}"]] for i in range(1, 5)])
        size = (np.linalg.norm(np.cross(p[1]-p[0], p[2]-p[0]))+
                np.linalg.norm(np.cross(p[2]-p[0], p[3]-p[0])))/2
        station = (float(row["StartSta"])+float(row["EndSta"]))/2
        if not math.isfinite(station) or size <= 0:
            raise GeometryError(f"Area {area}: invalid station or zero parent area")
        rows.append({"Area": area, "Bridge": row["BridgeObj"], "Span": row["BOSpan"],
            "Station": station, "Weight": size, **dict(zip("XYZ", p.mean(axis=0)))})
    frame = pd.DataFrame(rows)
    directions = {}
    for (bridge, span), subset in frame.groupby(["Bridge", "Span"]):
        stations, centres = [], []
        for s, group in subset.groupby("Station"):
            stations.append(s)
            centres.append(np.average(group[list("XYZ")].to_numpy(), axis=0, weights=group["Weight"]))
        stations, centres = np.array(stations), np.array(centres)
        if len(stations) < 2 or np.ptp(stations) <= 1e-6:
            raise GeometryError(f"{bridge} / {span}: at least two bridge-station sections are required")
        design = np.column_stack((np.ones(len(stations)), stations-stations.mean()))
        coefficients = np.linalg.lstsq(design, centres, rcond=None)[0]
        if np.max(np.linalg.norm(design@coefficients-centres, axis=1)) > .01:
            raise GeometryError(f"{bridge} / {span}: curved or varying-width deck needs an explicit alignment model; this release supports straight decks")
        direction = unit(coefficients[1])
        across = unit(np.cross(np.array([0.,0.,1.]),direction))
        widths=[]
        for _, group in subset.groupby("Station"):
            corners=np.array([coordinates[parents[a][f"Joint{i}"]] for a in group['Area'] for i in range(1,5)])
            widths.append(float(np.ptp(corners@across)))
        if np.ptp(widths)>.01:
            raise GeometryError(f"{bridge} / {span}: variable deck width needs an explicit alignment model")
        for area in subset["Area"]:
            directions[area] = direction
    return directions


@dataclass
class SlabGeometry:
    corners: pd.DataFrame
    elements: dict[str, np.ndarray]
    parent_axes: dict[str, dict]


def recover(package: ShellPackage) -> SlabGeometry:
    if not package.ready:
        raise GeometryError("Import validation is incomplete")
    tables = package.tables
    flags = tables["flags"].loc[tables["flags"]["CompType"].astype(str).str.strip().str.casefold().eq("top slab")]
    slab_ids = set(flags["Area"])
    coordinates = {r["Joint"]: np.array([r[f"Global{c}"] for c in "XYZ"], dtype=float)
        for r in tables["joints"].to_dict("records")}
    for row in tables["nodes"].to_dict("records"):
        point = np.array([row[f"Global{c}"] for c in "XYZ"], dtype=float)
        if row["JointElem"] in coordinates and np.linalg.norm(coordinates[row["JointElem"]]-point) > 2e-5:
            raise GeometryError(f"Joint {row['JointElem']}: original and analysis coordinates conflict")
        coordinates[row["JointElem"]] = point
    parents = tables["parents"].set_index("Area").to_dict("index")
    thicknesses = tables["thickness"].set_index("Area").to_dict("index")
    typical = tables["axes"].set_index("Area").to_dict("index")
    advanced = tables.get("advanced", pd.DataFrame(columns=["Area"])).set_index("Area").to_dict("index")
    directions = _station_directions(flags, parents, coordinates)
    points_by_area, axes = {}, {}
    for area in slab_ids:
        p = np.array([coordinates[parents[area][f"Joint{i}"]] for i in range(1, 5)])
        e1, e2, e3 = local_axes(p, typical[area], advanced.get(area), coordinates)
        up = e3 * (1 if e3[2] > 0 else -1)
        long = unit(directions[area]-up*np.dot(directions[area], up))
        transverse = unit(np.cross(up, long))
        rotation = np.array([[np.dot(long, e1), np.dot(long, e2)],
                             [np.dot(transverse, e1), np.dot(transverse, e2)]])
        axes[area] = {"rotation": rotation, "normal_sign": 1 if e3[2] > 0 else -1,
            "long": long.tolist(), "transverse": transverse.tolist(), "up": up.tolist(),
            "local1": e1.tolist(), "local2": e2.tolist(), "local3": e3.tolist()}
        points_by_area[area] = p
    rows, elements = [], {}
    for element in tables["elements"].to_dict("records"):
        area = element["AreaObject"]
        if area not in slab_ids:
            continue
        elem = element["AreaElem"]
        ids = [element[f"ElemJt{i}"] for i in range(1, 5)]
        if any(not j for j in ids) or len(set(ids)) != 4:
            raise GeometryError(f"Element {elem}: this release requires four distinct mesh corners")
        q = np.array([coordinates[j] for j in ids])
        if np.linalg.norm(np.cross(q[1]-q[0], q[3]-q[0])) < 1e-10:
            raise GeometryError(f"Element {elem}: degenerate shell")
        elements[elem] = q
        corners = np.array([thicknesses[area][f"Thick{i}"] for i in range(1, 5)])
        for joint, xyz in zip(ids, q):
            weights = inverse_quad(points_by_area[area], xyz)
            rows.append({"Area": area, "AreaElem": elem, "Joint": joint,
                "X (m)": xyz[0], "Y (m)": xyz[1], "Z (m)": xyz[2],
                "Thickness (mm)": float(weights@corners*1000)})
    return SlabGeometry(pd.DataFrame(rows), elements, axes)


def steel_axis_forces(frame, axes):
    """Transform both tensors; reversing local 3 also reverses moment sign."""
    result = frame.copy()
    for area, indices in result.groupby("Area").groups.items():
        rotation = axes[area]["rotation"]
        sign = axes[area]["normal_sign"]
        for stem, cols, out in (("N", ["F11", "F22", "F12"], ["Nx", "Ny", "Nxy"]),
                                ("M", ["M11", "M22", "M12"], ["Mx", "My", "Mxy"])):
            values = result.loc[indices, cols].to_numpy(dtype=float)
            tensor = np.array([[values[:, 0], values[:, 2]], [values[:, 2], values[:, 1]]]).transpose(2, 0, 1)
            target = rotation@tensor@rotation.T
            if stem == "M":
                target *= sign
            result.loc[indices, out] = target[:, [0, 1, 0], [0, 1, 1]]
        result.loc[indices, ["Vx", "Vy"]] = (sign*rotation@result.loc[indices, ["V13", "V23"]].to_numpy().T).T
    return result
