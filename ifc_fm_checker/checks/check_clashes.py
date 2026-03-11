"""
Check 6: Geometric Clash Detection
Detects geometric clashes between building elements using axis-aligned bounding boxes (AABB).
"""

from typing import Any, Dict, List, Optional, Tuple

from ifc_fm_checker.utils import get_entity_label, get_parent_storey

# Element types to skip (non-physical or spatial containers)
_SKIP_TYPES = frozenset([
    "IfcOpeningElement",
    "IfcSpace",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
])

# Element types that legitimately touch each other — skip same-type pairs
_SAME_TYPE_SKIP = frozenset([
    "IfcCovering",
    "IfcWall",
    "IfcSlab",
    "IfcRailing",
    "IfcStair",
    "IfcRamp",
])


def run(ifc_file, tolerance_cm: float = 0.0, **kwargs) -> Dict[str, Any]:
    """
    Detect geometric clashes using AABB intersection.

    Args:
        ifc_file: Open ifcopenshell file object.
        tolerance_cm: Clearance tolerance in cm. Each AABB is expanded by
                      tolerance_cm/2 on each side before the overlap test.

    Returns:
        Standard check dict with name, score, issues, stats, description.
    """
    # Verify geometry engine availability
    try:
        import ifcopenshell.geom as _geom
        settings = _geom.settings()
    except (ImportError, AttributeError):
        return {
            "name": "Clash Detection",
            "score": 100,
            "issues": [{
                "severity": "warning",
                "element": "Model",
                "message": "Geometry engine unavailable — clash detection skipped",
                "fix": "Install ifcopenshell with geometry support to enable clash detection.",
            }],
            "stats": {
                "total_elements_checked": 0,
                "clash_count": 0,
                "same_type_filtered": 0,
                "tolerance_cm": tolerance_cm,
            },
            "description": (
                "Detects geometric clashes between building elements using "
                "axis-aligned bounding boxes (AABB)."
            ),
        }

    # Convert tolerance from cm to model units
    tolerance_model = _cm_to_model_units(ifc_file, tolerance_cm)

    # Collect AABBs for all physical elements with geometry
    element_bboxes: List[Dict[str, Any]] = []
    for element in ifc_file.by_type("IfcProduct"):
        if any(element.is_a(skip) for skip in _SKIP_TYPES):
            continue
        try:
            shape = _geom.create_shape(settings, element)
            verts = shape.geometry.verts
            if not verts:
                continue
            bbox = _compute_aabb(verts)
            if bbox is None:
                continue
            element_bboxes.append({
                "element": element,
                "bbox": bbox,
                "label": get_entity_label(element),
                "storey": get_parent_storey(element) or "Unknown",
            })
        except Exception:
            continue  # element has no geometry or geometry cannot be created

    total_checked = len(element_bboxes)
    issues: List[Dict[str, Any]] = []
    same_type_filtered = 0

    # Minimum overlap volume threshold: 1 cm³ converted to model units³
    unit_scale = 1.0
    try:
        import ifcopenshell.util.unit as _unit
        _us = _unit.calculate_unit_scale(ifc_file)
        if _us and _us > 0:
            unit_scale = _us
    except Exception:
        pass
    min_volume_model = (1e-6) / (unit_scale ** 3)  # 1 cm³ = 1e-6 m³

    # Pairwise AABB clash detection — O(n²), acceptable for typical BIM models
    for i in range(total_checked):
        for j in range(i + 1, total_checked):
            a = element_bboxes[i]
            b = element_bboxes[j]

            el_a = a["element"]
            el_b = b["element"]
            type_a = el_a.is_a()
            type_b = el_b.is_a()

            # Skip same-type pairs for types that legitimately touch
            if type_a == type_b and type_a in _SAME_TYPE_SKIP:
                if _aabbs_overlap(a["bbox"], b["bbox"], tolerance_model):
                    same_type_filtered += 1
                continue

            if not _aabbs_overlap(a["bbox"], b["bbox"], tolerance_model):
                continue

            # Check overlap volume exceeds minimum threshold
            overlap_vol = _aabb_overlap_volume(a["bbox"], b["bbox"])
            if overlap_vol < min_volume_model:
                continue

            t1 = a["bbox"]
            t2 = b["bbox"]
            clash_data = {
                "id1": el_a.GlobalId,
                "type1": type_a,
                "name1": getattr(el_a, "Name", None) or "",
                "id2": el_b.GlobalId,
                "type2": type_b,
                "name2": getattr(el_b, "Name", None) or "",
                "storey1": a["storey"],
                "storey2": b["storey"],
                "overlap_volume_m3": round(overlap_vol * (unit_scale ** 3), 8),
                "bbox1": {"xmin": t1[0], "ymin": t1[1], "zmin": t1[2],
                          "xmax": t1[3], "ymax": t1[4], "zmax": t1[5]},
                "bbox2": {"xmin": t2[0], "ymin": t2[1], "zmin": t2[2],
                          "xmax": t2[3], "ymax": t2[4], "zmax": t2[5]},
            }
            issues.append({
                "severity": "error",
                "element": f"{a['label']} vs {b['label']}",
                "message": (
                    f"Clash detected between {type_a} #{el_a.id()} "
                    f"and {type_b} #{el_b.id()}"
                ),
                "fix": "Review and resolve geometric overlap in authoring tool",
                "clash_data": clash_data,
            })

    clash_count = len(issues)
    score = max(0, 100 - clash_count * 5)

    return {
        "name": "Clash Detection",
        "score": score,
        "issues": issues,
        "clashes": [i["clash_data"] for i in issues[:50]],
        "stats": {
            "total_elements_checked": total_checked,
            "clash_count": clash_count,
            "same_type_filtered": same_type_filtered,
            "tolerance_cm": tolerance_cm,
        },
        "description": (
            "Detects geometric clashes between building elements using "
            "axis-aligned bounding boxes (AABB). "
            "Score = max(0, 100 − clash_count × 5). "
            "Informational only — does not affect the FM Readiness score."
        ),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cm_to_model_units(ifc_file, tolerance_cm: float) -> float:
    """Convert tolerance from cm to model coordinate units."""
    if tolerance_cm == 0.0:
        return 0.0
    try:
        import ifcopenshell.util.unit as ifc_unit
        # calculate_unit_scale returns meters-per-model-unit (e.g. 0.001 for mm)
        unit_scale = ifc_unit.calculate_unit_scale(ifc_file)
        if unit_scale and unit_scale > 0:
            return (tolerance_cm / 100.0) / unit_scale
    except Exception:
        pass
    return tolerance_cm / 100.0  # fallback: assume model units are meters


def _compute_aabb(
    verts,
) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Compute an AABB from a flat vertex list [x1,y1,z1, x2,y2,z2, ...]."""
    if len(verts) < 3:
        return None
    xs = verts[0::3]
    ys = verts[1::3]
    zs = verts[2::3]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _aabb_overlap_volume(
    bbox1: Tuple[float, float, float, float, float, float],
    bbox2: Tuple[float, float, float, float, float, float],
) -> float:
    """Compute the volume of the AABB intersection. Returns 0.0 if no overlap."""
    ox = min(bbox1[3], bbox2[3]) - max(bbox1[0], bbox2[0])
    oy = min(bbox1[4], bbox2[4]) - max(bbox1[1], bbox2[1])
    oz = min(bbox1[5], bbox2[5]) - max(bbox1[2], bbox2[2])
    if ox <= 0 or oy <= 0 or oz <= 0:
        return 0.0
    return ox * oy * oz


def _aabbs_overlap(
    bbox1: Tuple[float, float, float, float, float, float],
    bbox2: Tuple[float, float, float, float, float, float],
    tolerance_model: float = 0.0,
) -> bool:
    """
    Check if two AABBs overlap, with optional tolerance expansion.

    Each AABB is expanded by tolerance_model/2 on each side before testing,
    so elements within tolerance_model distance are also flagged.
    """
    min1x, min1y, min1z, max1x, max1y, max1z = bbox1
    min2x, min2y, min2z, max2x, max2y, max2z = bbox2
    t = tolerance_model / 2.0  # expansion per side per AABB
    return (
        (min1x - t) < (max2x + t) and (max1x + t) > (min2x - t) and
        (min1y - t) < (max2y + t) and (max1y + t) > (min2y - t) and
        (min1z - t) < (max2z + t) and (max1z + t) > (min2z - t)
    )
