"""
Check: MEP System Assignment
Verifies that MEP elements are assigned to at least one IfcSystem
via IfcRelAssignsToGroup.

Without IfcSystem assignment a CAFM cannot know which plant or circuit
an asset belongs to — the most common FM data gap in Italian IFC models.
"""

from typing import Any, Dict, List, Set

from ifc_fm_checker.utils import get_entity_label


# MEP types whose system assignment is verified
MEP_TYPES = [
    "IfcFlowTerminal",
    "IfcFlowSegment",
    "IfcFlowFitting",
    "IfcEnergyConversionDevice",
    "IfcFlowMovingDevice",
    "IfcFlowStorageDevice",
    "IfcFlowController",
    "IfcDistributionControlElement",
]

# Unassigned critical types get "error" severity; others get "warning"
CRITICAL_MEP_TYPES = {"IfcFlowMovingDevice", "IfcEnergyConversionDevice"}


def run(ifc_file, **kwargs) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []

    # --- Collect all MEP elements (IFC2X3/IFC4 safe) ---
    mep_elements = []
    for mep_type in MEP_TYPES:
        try:
            mep_elements.extend(ifc_file.by_type(mep_type))
        except RuntimeError:
            pass  # type not in this schema version

    if not mep_elements:
        return {
            "name": "MEP System Assignment",
            "score": 100,
            "issues": [{
                "severity": "info",
                "element": "Model",
                "message": "No MEP elements found — system assignment check skipped",
                "fix": "If this is an architectural-only model, this check does not apply.",
            }],
            "stats": {"total_mep_elements": 0},
            "description": (
                "Verifies that MEP elements are assigned to at least one IfcSystem "
                "via IfcRelAssignsToGroup. Without system assignment a CAFM cannot "
                "determine which plant or circuit an asset belongs to."
            ),
        }

    # --- Build set of element IDs that have at least one system assignment ---
    assigned_ids: Set[int] = set()
    try:
        for system in ifc_file.by_type("IfcSystem"):
            for rel in ifc_file.get_inverse(system):
                if rel.is_a("IfcRelAssignsToGroup"):
                    for obj in rel.RelatedObjects:
                        assigned_ids.add(obj.id())
    except Exception:
        pass

    # --- Classify each element ---
    unassigned_by_type: Dict[str, List] = {}
    assigned_count = 0

    for element in mep_elements:
        if element.id() in assigned_ids:
            assigned_count += 1
        else:
            etype = element.is_a()
            unassigned_by_type.setdefault(etype, []).append(element)

    # --- Build one issue per unassigned type ---
    for etype, elements in unassigned_by_type.items():
        pct = len(elements) / len(mep_elements) * 100
        severity = "error" if etype in CRITICAL_MEP_TYPES else "warning"
        sample = [get_entity_label(e) for e in elements[:3]]
        more = len(elements) - 3 if len(elements) > 3 else 0
        element_str = ", ".join(sample) + (f" and {more} more" if more else "")
        issues.append({
            "severity": severity,
            "element": element_str,
            "message": (
                f"[×{len(elements)}] {etype} not assigned to any IfcSystem "
                f"({pct:.0f}% of {len(mep_elements)} MEP elements)"
            ),
            "fix": (
                "In Revit MEP: assign elements to a mechanical, electrical, or piping system. "
                "In IFC export settings: enable 'Export MEP systems as IfcSystem'. "
                "Without this, CAFM cannot determine which plant or circuit the asset belongs to."
            ),
        })

    score = int(assigned_count / len(mep_elements) * 100)

    return {
        "name": "MEP System Assignment",
        "score": score,
        "issues": issues,
        "stats": {
            "total_mep_elements": len(mep_elements),
            "assigned_elements": assigned_count,
            "unassigned_elements": len(mep_elements) - assigned_count,
        },
        "description": (
            "Verifies that MEP elements are assigned to at least one IfcSystem "
            "via IfcRelAssignsToGroup. Without system assignment a CAFM cannot "
            "determine which plant or circuit an asset belongs to."
        ),
    }
