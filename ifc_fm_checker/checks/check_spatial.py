"""
Check 1: Spatial Structure
Verifies that the model has a valid spatial hierarchy:
Site > Building > BuildingStorey > Space
and that all elements are contained in the hierarchy.
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.utils import get_parent_storey, get_entity_label


def run(ifc_file) -> Dict[str, Any]:
    """
    Returns:
        score (0–100): spatial structure completeness score
        issues: list of issue dicts
        stats: summary counts
    """
    issues = []
    stats = {}

    # --- 1. Check hierarchy presence ---
    sites = ifc_file.by_type("IfcSite")
    buildings = ifc_file.by_type("IfcBuilding")
    storeys = ifc_file.by_type("IfcBuildingStorey")
    spaces = ifc_file.by_type("IfcSpace")

    stats["sites"] = len(sites)
    stats["buildings"] = len(buildings)
    stats["storeys"] = len(storeys)
    stats["spaces"] = len(spaces)

    hierarchy_score = 100

    if not sites:
        issues.append({
            "severity": "warning",
            "element": "Model",
            "message": "No IfcSite found — spatial hierarchy incomplete",
            "fix": "Add a site entity as root of the spatial structure",
        })
        hierarchy_score -= 15

    if not buildings:
        issues.append({
            "severity": "error",
            "element": "Model",
            "message": "No IfcBuilding found — spatial hierarchy incomplete",
            "fix": "Add at least one IfcBuilding under IfcSite",
        })
        hierarchy_score -= 20

    if not storeys:
        issues.append({
            "severity": "error",
            "element": "Model",
            "message": "No IfcBuildingStorey found — cannot assign elements to floors",
            "fix": "Add IfcBuildingStorey entities (one per level)",
        })
        hierarchy_score -= 30

    if not spaces:
        issues.append({
            "severity": "warning",
            "element": "Model",
            "message": "No IfcSpace found — FM space assignment not possible",
            "fix": "Add IfcSpace entities for each room/zone. Required for CAFM area management.",
        })
        hierarchy_score -= 20

    # --- 2. Check element containment ---
    # All physical elements should be in IfcBuildingStorey
    element_types_to_check = [
        "IfcWall", "IfcSlab", "IfcColumn", "IfcBeam", "IfcDoor", "IfcWindow",
        "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
        "IfcDistributionControlElement", "IfcBuildingElementProxy",
    ]

    total_elements = 0
    uncontained = []

    for etype in element_types_to_check:
        elements = ifc_file.by_type(etype)
        for el in elements:
            total_elements += 1
            storey = get_parent_storey(el)
            if storey is None:
                uncontained.append(get_entity_label(el))

    stats["total_physical_elements"] = total_elements
    stats["uncontained_elements"] = len(uncontained)

    containment_score = 100
    if total_elements > 0:
        pct_uncontained = len(uncontained) / total_elements * 100
        containment_score = max(0, 100 - int(pct_uncontained * 1.5))

        if uncontained:
            # Report first 20 to avoid huge reports
            sample = uncontained[:20]
            more = len(uncontained) - 20 if len(uncontained) > 20 else 0
            msg = (
                f"{len(uncontained)} element(s) not contained in any "
                f"IfcBuildingStorey ({pct_uncontained:.1f}%)"
            )
            if more:
                msg += f" — showing first 20, {more} more"
            issues.append({
                "severity": "warning",
                "element": ", ".join(sample),
                "message": msg,
                "fix": (
                    "In Revit: use 'Room Bounding' on all elements. "
                    "In Archicad: verify zone boundaries. "
                    "Ensure elements are placed within a storey level."
                ),
            })

    # --- 3. Check spaces have names ---
    unnamed_spaces = []
    for space in spaces:
        name = getattr(space, "Name", None)
        if not name or not name.strip():
            unnamed_spaces.append(getattr(space, "GlobalId", "?"))

    stats["unnamed_spaces"] = len(unnamed_spaces)
    if unnamed_spaces:
        issues.append({
            "severity": "warning",
            "element": f"{len(unnamed_spaces)} IfcSpace(s)",
            "message": f"{len(unnamed_spaces)} spaces have no Name — CAFM cannot identify them",
            "fix": "Assign a meaningful name to every IfcSpace (room number or functional label)",
        })

    # --- 4. Check spaces have area ---
    spaces_no_area = []
    for space in spaces:
        has_area = False
        for rel in getattr(space, "IsDefinedBy", []):
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet"):
                    for prop in pdef.HasProperties:
                        if prop.Name in ("GrossFloorArea", "NetFloorArea") and \
                                hasattr(prop, "NominalValue") and prop.NominalValue:
                            if prop.NominalValue.wrappedValue:
                                has_area = True
        if not has_area:
            spaces_no_area.append(getattr(space, "Name", getattr(space, "GlobalId", "?")))

    stats["spaces_without_area"] = len(spaces_no_area)
    if spaces_no_area:
        pct = len(spaces_no_area) / max(len(spaces), 1) * 100
        issues.append({
            "severity": "info",
            "element": f"{len(spaces_no_area)} IfcSpace(s)",
            "message": f"{len(spaces_no_area)} spaces ({pct:.0f}%) have no GrossFloorArea in Pset_SpaceCommon",
            "fix": "Compute areas in the authoring tool and export to IFC with Pset_SpaceCommon.GrossFloorArea",
        })

    # --- Final score ---
    if total_elements == 0 and len(spaces) == 0:
        final_score = max(0, hierarchy_score)
    else:
        final_score = max(0, int((hierarchy_score * 0.4) + (containment_score * 0.6)))

    return {
        "name": "Spatial Structure",
        "score": final_score,
        "issues": issues,
        "stats": stats,
        "description": (
            "Verifies Site > Building > Storey > Space hierarchy and "
            "that all physical elements are assigned to a storey."
        ),
    }
