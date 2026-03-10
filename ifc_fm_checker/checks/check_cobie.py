"""
Check 4: COBie Readiness
Verifies the minimum data required for a valid COBie export:
Facility, Floor, Space, Type, Component sheets.
Reference: COBie 2.4 / UK BIM Framework / ISO 19650-3.
"""

import ifcopenshell
from typing import Dict, Any
from ifc_fm_checker.utils import get_psets, get_all_props_including_type, prop_is_filled


def run(ifc_file) -> Dict[str, Any]:
    issues = []
    stats = {}
    sheet_scores = {}

    # -------------------------------------------------------
    # FACILITY sheet: project/site info
    # -------------------------------------------------------
    projects = ifc_file.by_type("IfcProject")
    facility_score = 100
    for proj in projects:
        name = getattr(proj, "Name", None)
        if not name or not name.strip():
            issues.append({
                "severity": "warning",
                "element": "IfcProject",
                "message": "IfcProject has no Name — COBie Facility.Name will be empty",
                "fix": "Set a project name in the authoring tool's project settings.",
            })
            facility_score -= 40
        desc = getattr(proj, "Description", None)
        if not desc:
            issues.append({
                "severity": "info",
                "element": "IfcProject",
                "message": "IfcProject has no Description — COBie Facility.Description will be empty",
                "fix": "Add a project description in the authoring tool settings.",
            })
            facility_score -= 10

    sheet_scores["Facility"] = max(0, facility_score)
    stats["projects"] = len(projects)

    # -------------------------------------------------------
    # FLOOR sheet: storeys must have names and elevations
    # -------------------------------------------------------
    storeys = ifc_file.by_type("IfcBuildingStorey")
    storey_issues = 0
    for storey in storeys:
        name = getattr(storey, "Name", None)
        elevation = getattr(storey, "Elevation", None)
        if not name or not name.strip():
            storey_issues += 1
            issues.append({
                "severity": "warning",
                "element": f"IfcBuildingStorey #{getattr(storey, 'GlobalId', '?')}",
                "message": "Storey has no Name — COBie Floor.Name will be empty",
                "fix": "Assign a name to every storey (e.g. 'Ground Floor', 'Level 01').",
            })
        if elevation is None:
            issues.append({
                "severity": "info",
                "element": f"Storey '{name or '?'}'",
                "message": "Storey elevation not set — COBie Floor.Elevation will be missing",
                "fix": "Set storey elevation in the authoring tool.",
            })

    floor_score = max(0, 100 - (storey_issues / max(len(storeys), 1) * 100))
    sheet_scores["Floor"] = int(floor_score)
    stats["storeys"] = len(storeys)

    # -------------------------------------------------------
    # SPACE sheet: spaces need name, description, area
    # -------------------------------------------------------
    spaces = ifc_file.by_type("IfcSpace")
    space_issues = 0

    for space in spaces:
        name = getattr(space, "Name", None)
        desc = getattr(space, "Description", None) or getattr(space, "LongName", None)
        if not name:
            space_issues += 2
        elif not desc:
            space_issues += 1

    space_score = max(0, 100 - (space_issues / max(len(spaces) * 2, 1) * 100))
    sheet_scores["Space"] = int(space_score)
    stats["spaces"] = len(spaces)

    if len(spaces) == 0:
        issues.append({
            "severity": "error",
            "element": "Model",
            "message": "No IfcSpace found — COBie Space sheet will be empty",
            "fix": "Add IfcSpace entities for each room/zone. Required for COBie compliance.",
        })
        sheet_scores["Space"] = 0

    # -------------------------------------------------------
    # TYPE sheet: equipment types need manufacturer + model
    # -------------------------------------------------------
    type_objects = ifc_file.by_type("IfcTypeObject")
    type_issues = 0
    for type_obj in type_objects:
        props = {}
        for pset in getattr(type_obj, "HasPropertySets", []):
            if pset.is_a("IfcPropertySet"):
                for prop in pset.HasProperties:
                    if hasattr(prop, "NominalValue") and prop.NominalValue:
                        props[prop.Name] = prop.NominalValue.wrappedValue

        manufacturer = props.get("Manufacturer") or props.get("Produttore")
        model = props.get("ModelReference") or props.get("ModelLabel")

        if not prop_is_filled(manufacturer):
            type_issues += 1
        if not prop_is_filled(model):
            type_issues += 1

    type_score = max(0, 100 - (type_issues / max(len(type_objects) * 2, 1) * 100))
    sheet_scores["Type"] = int(type_score)
    stats["type_objects"] = len(type_objects)

    if type_objects and type_issues > 0:
        pct = type_issues / (len(type_objects) * 2) * 100
        issues.append({
            "severity": "warning",
            "element": f"{len(type_objects)} IfcTypeObject(s)",
            "message": (
                f"Type objects missing Manufacturer/ModelReference data ({pct:.0f}% of fields empty) "
                "— COBie Type sheet will be incomplete"
            ),
            "fix": (
                "Fill Manufacturer and ModelReference in Type Properties of each family/type. "
                "In COBie, the Type sheet drives the asset register for the entire building lifetime."
            ),
        })

    # -------------------------------------------------------
    # COMPONENT sheet: instances need unique tags
    # -------------------------------------------------------
    components = []
    component_types = [
        "IfcFlowTerminal", "IfcFlowSegment", "IfcFlowFitting",
        "IfcDistributionControlElement", "IfcElectricAppliance",
        "IfcSanitaryTerminal", "IfcAirTerminal",
    ]
    for ct in component_types:
        try:
            components.extend(ifc_file.by_type(ct))
        except RuntimeError:
            pass  # type not in this schema version

    tags = set()
    duplicate_tags = []
    no_tag = 0

    for comp in components:
        tag = getattr(comp, "Tag", None) or getattr(comp, "Name", None)
        if not tag or not str(tag).strip():
            no_tag += 1
        else:
            tag_str = str(tag).strip()
            if tag_str in tags:
                duplicate_tags.append(tag_str)
            tags.add(tag_str)

    component_score = 100
    if components:
        if no_tag > 0:
            pct = no_tag / len(components) * 100
            component_score -= int(pct * 0.8)
            issues.append({
                "severity": "warning",
                "element": f"{no_tag} component(s)",
                "message": (
                    f"{no_tag} components ({pct:.0f}%) have no Tag — "
                    "COBie Component.TagNumber will be empty"
                ),
                "fix": (
                    "Assign unique Tag/Mark values to all equipment instances. "
                    "Tags must be unique per type — e.g. FCU-01, FCU-02, FCU-03."
                ),
            })
        if duplicate_tags:
            component_score -= 15
            issues.append({
                "severity": "warning",
                "element": f"{len(duplicate_tags)} duplicate tag(s)",
                "message": (
                    f"Duplicate Tag values found: {', '.join(set(duplicate_tags[:5]))} "
                    "— COBie requires unique component identifiers"
                ),
                "fix": "Ensure each equipment instance has a unique Tag/Mark value.",
            })

    component_score = max(0, component_score)
    sheet_scores["Component"] = component_score
    stats["components"] = len(components)

    # -------------------------------------------------------
    # Overall COBie score
    # -------------------------------------------------------
    weights = {"Facility": 0.15, "Floor": 0.15, "Space": 0.25, "Type": 0.25, "Component": 0.20}
    overall = sum(sheet_scores.get(k, 100) * w for k, w in weights.items())

    stats["sheet_scores"] = sheet_scores

    return {
        "name": "COBie Readiness",
        "score": int(overall),
        "issues": issues,
        "stats": stats,
        "description": (
            "Checks minimum data for a valid COBie export: "
            "Facility, Floor, Space, Type, Component sheets. "
            "Based on COBie 2.4 and UK BIM Framework."
        ),
    }
